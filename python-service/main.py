"""
Helix Health Group — Clinical Platform API (Python / FastAPI)
=============================================================
Covers:
  Part 1  — helix-auto-scribe feature flag, SSE instant listener, flag trigger webhook
  Extra   — helix-clinical-ai AI Config (agent mode) via Anthropic Claude:
              • ED mode   : fast ICD-10 + CPT auto-coding from clinical transcripts
              • OB mode   : thorough obstetric coding
              • Parent mode: warm newborn guidance ("my baby at 2am")

Run:
  pip install -r requirements.txt
  python main.py
"""

import os
import json
import asyncio
import re
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

import ldclient
from ldclient import Config, Context
from ldai.client import LDAIClient, AIConfig

import anthropic

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
# Load .env from parent directory (project root)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# ---------------------------------------------------------------------------
# LaunchDarkly initialisation
# Replace "LD_SERVER_SDK_KEY" with your Test environment server-side SDK key
# if you are not using the .env file.
# ---------------------------------------------------------------------------
ldclient.set_config(Config(os.environ["LD_SERVER_SDK_KEY"]))
ld = ldclient.get()
ai_client = LDAIClient(ld)

# ---------------------------------------------------------------------------
# Anthropic client
# Replace "ANTHROPIC_API_KEY" with your key if not using .env.
# ---------------------------------------------------------------------------
anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Helix Health Group — Clinical Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Part 1: SSE flag-change listener
#
# The LD SDK fires _on_flag_change() in a background thread whenever the
# helix-auto-scribe flag value changes for our system context.  We push
# that event onto an asyncio.Queue so every connected SSE client gets it
# immediately — no polling, no page reload required.
# ---------------------------------------------------------------------------
_sse_queues: list[asyncio.Queue] = []
_flag_state: dict = {"helix-auto-scribe": False}

# A generic "system" context used only to register the flag listener.
# Real per-user evaluation happens in the targeting endpoints.
_SYSTEM_CTX = Context.builder("helix-system").build()


def _on_flag_change(event) -> None:
    """Callback fired by the LD SDK when helix-auto-scribe changes."""
    new_value = event.current_value
    _flag_state["helix-auto-scribe"] = new_value
    payload = json.dumps({"flag": "helix-auto-scribe", "value": new_value})
    try:
        loop = asyncio.get_event_loop()
        for q in _sse_queues:
            loop.call_soon_threadsafe(q.put_nowait, payload)
    except Exception:
        pass


ld.get_flag_tracker().add_flag_value_change_listener(
    "helix-auto-scribe",   # flag key — create this boolean flag in LD first
    _SYSTEM_CTX,
    _on_flag_change,
)


# ---------------------------------------------------------------------------
# GET /events   — Server-Sent Events stream
# ---------------------------------------------------------------------------
@app.get("/events")
async def sse_events():
    """
    Browser connects here once.  When helix-auto-scribe is toggled in the
    LaunchDarkly dashboard the UI updates instantly — no reload needed.
    """
    queue: asyncio.Queue = asyncio.Queue()
    _sse_queues.append(queue)

    async def generate() -> AsyncGenerator[str, None]:
        # Send current flag state immediately so the UI is in sync on connect
        current = ld.bool_variation("helix-auto-scribe", _SYSTEM_CTX, False)
        yield f"data: {json.dumps({'flag': 'helix-auto-scribe', 'value': current})}\n\n"

        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive comment — prevents proxy/browser from closing the stream
                    yield ": keepalive\n\n"
        finally:
            _sse_queues.remove(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# POST /ld-trigger   — Flag trigger webhook (Part 1: Remediate)
#
# In the LaunchDarkly dashboard:
#   Flag > Settings > Triggers > Add trigger > Generic trigger
#   Copy the generated URL, then POST to it from monitoring/curl to turn
#   the flag OFF.  LD propagates the change; the SDK listener fires above.
#
# This endpoint is informational — it can log the incoming trigger payload
# so you can see it in action during the demo.
# ---------------------------------------------------------------------------
@app.post("/ld-trigger")
async def ld_trigger(request: Request):
    """Receives a copy of the trigger payload for demo logging purposes."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    print(f"[TRIGGER] Received flag trigger payload: {body}")
    return {"status": "received"}


# ---------------------------------------------------------------------------
# POST /code-encounter   — AI Auto-Scribe (Extra Credit: AI Config)
#
# Receives a clinical transcript and returns structured ICD-10 + CPT codes.
# The LD AI Config "helix-clinical-ai" controls:
#   • Which Claude model is used  (Haiku for ED speed, Sonnet for OB depth)
#   • The system prompt / instructions  (specialty-specific coding guidance)
# Switching department context → different AI Config variation fires.
# ---------------------------------------------------------------------------
@app.post("/code-encounter")
async def code_encounter(request: Request):
    """
    Body (JSON):
      transcript  : str  — raw clinical encounter text
      userId      : str  — provider identifier
      department  : str  — "ed" | "ob"
      role        : str  — "attending" | "resident" | "charge_nurse"

    The "department" attribute routes to the correct AI Config variation:
      department=ed  → HELIX-SCRIBE-ED  (Haiku, ED coding prompt)
      department=ob  → HELIX-SCRIBE-OB  (Sonnet, OB coding prompt)
    """
    body = await request.json()
    transcript = body.get("transcript", "")
    user_key = body.get("userId", "provider-default")
    department = body.get("department", "ed")

    # Build context — the "department" attribute is the targeting key in LD
    context = (
        Context.builder(user_key)
        .set("department", department)
        .set("role", body.get("role", "attending"))
        .build()
    )

    # Fetch AI Config from LaunchDarkly
    # Create "helix-clinical-ai" as an AI Config in the LD Agents section
    ai_config, tracker = ai_client.config("helix-clinical-ai", context, AIConfig(enabled=False))

    if not ai_config.enabled:
        return {"error": "AI coding feature is currently disabled", "codes": []}

    model_name = (ai_config.model.name if ai_config.model and ai_config.model.name
                  else "claude-haiku-4-5-20251001")
    system_prompt = next(
        (m.content for m in (ai_config.messages or []) if m.role == "system"),
        ("You are a clinical coding assistant. Extract ICD-10 and CPT codes "
         "from the encounter transcript. Return valid JSON only."),
    )

    try:
        response = anthropic_client.messages.create(
            model=model_name,
            max_tokens=1024,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": (
                    f"Clinical encounter transcript:\n\n{transcript}\n\n"
                    "Return a JSON object with these exact keys:\n"
                    "  diagnosis       : string (primary diagnosis)\n"
                    "  icd10_codes     : array of {code, description}\n"
                    "  cpt_codes       : array of {code, description}\n"
                    "  complexity      : string — low | moderate | high\n"
                    "  coding_notes    : string (brief rationale)\n"
                    "Return JSON only. No markdown fences."
                ),
            }],
        )

        tracker.track_success()
        tracker.track_tokens(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        content = response.content[0].text.strip()
        # Strip any accidental markdown fences Claude might add
        content = re.sub(r"^```json\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        result = json.loads(content)

        return {
            "success": True,
            "department": department,
            "model_used": model_name,
            "result": result,
            "tokens": {
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
            },
        }

    except Exception as exc:
        return {"success": False, "error": str(exc), "codes": []}


# ---------------------------------------------------------------------------
# POST /parent-connect   — Newborn guidance AI ("my baby at 2am")
#
# Patient-facing endpoint.  Uses the same helix-clinical-ai AI Config but
# with a "maternity-parent" department context, which routes to the warm,
# empathetic Parent Connect variation (Claude Sonnet).
#
# If the flag is OFF (e.g. after a trigger fires), falls back gracefully
# to directing the parent to the 24/7 nurse line.
# ---------------------------------------------------------------------------
@app.post("/parent-connect")
async def parent_connect(request: Request):
    """
    Body (JSON):
      message  : str — parent's description of their newborn's symptoms
      userId   : str — patient/parent identifier
    """
    body = await request.json()
    message = body.get("message", "")
    user_key = body.get("userId", "parent-default")

    context = (
        Context.builder(user_key)
        .set("department", "maternity-parent")
        .set("patient_type", "postpartum")
        .build()
    )

    ai_config, tracker = ai_client.config("helix-clinical-ai", context, AIConfig(enabled=False))

    if not ai_config.enabled:
        return {
            "response": (
                "Our AI care assistant is temporarily unavailable. "
                "Please call our 24/7 nurse line at 1-800-HELIX-RN for immediate guidance."
            ),
            "escalate": False,
            "model_used": None,
        }

    model_name = (ai_config.model.name if ai_config.model and ai_config.model.name
                  else "claude-sonnet-4-5-20251001")
    system_prompt = next(
        (m.content for m in (ai_config.messages or []) if m.role == "system"),
        ("You are HELIX-PARENT, a compassionate care assistant for new parents. "
         "Provide evidence-based guidance in plain, reassuring language. "
         "Always recommend calling 911 or going to the ED for emergencies. "
         "Never diagnose — guide parents on when to seek care."),
    )

    try:
        response = anthropic_client.messages.create(
            model=model_name,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": message}],
        )

        tracker.track_success()
        tracker.track_tokens(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        content = response.content[0].text
        # Simple escalation heuristic — flag if response suggests emergency action
        escalate = any(
            word in content.lower()
            for word in ["911", "emergency room", "er immediately", "call 911", "go to the ed"]
        )

        return {
            "response": content,
            "escalate": escalate,
            "model_used": model_name,
        }

    except Exception as exc:
        return {"error": str(exc), "escalate": False}


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "sdk_initialized": ld.is_initialized(),
        "flag_state": _flag_state,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
