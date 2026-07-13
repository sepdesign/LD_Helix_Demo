# Integrating LaunchDarkly into Helix Health Group

This guide walks through taking an application with **no feature management** and progressively adding LaunchDarkly capabilities: basic flag evaluation, real-time listeners, targeted rollouts, configuration-driven features (Number/String/JSON flags), AI Config, and client-side (browser) evaluation with the JavaScript SDK.

---

## The Starting Point: Without LaunchDarkly

Most teams control feature visibility using environment variables or hardcoded configuration. The Helix services were no different.

### Python

```python
# config.py: the DIY approach
import os

FEATURES = {
    "auto_scribe_enabled": os.getenv("ENABLE_AUTO_SCRIBE", "false").lower() == "true",
    "maternity_pathway":   os.getenv("ENABLE_MATERNITY", "false").lower() == "true",
}

# main.py
@app.post("/encounter")
async def encounter(request: Request):
    if FEATURES["auto_scribe_enabled"]:
        return await run_ai_coding_pipeline(transcript)
    return run_manual_coding_workflow(transcript)
```

### Go

```go
// config.go
var featureFlags = map[string]bool{
    "maternityPathway": os.Getenv("ENABLE_MATERNITY") == "true",
}

// handler.go
func featureHandler(w http.ResponseWriter, r *http.Request) {
    enabled := featureFlags["maternityPathway"]
    // ...
}
```

### Java

```java
// application.properties
feature.maternity.enabled=${ENABLE_MATERNITY:false}

// FeatureController.java
@Value("${feature.maternity.enabled}")
private boolean maternityEnabled;

@GetMapping("/feature")
public Map<String, Object> getFeature() {
    return Map.of("enabled", maternityEnabled);
}
```

---

## Why This Breaks Down

| Problem | DIY (env var flags) | With LaunchDarkly |
|---|---|---|
| Change a flag value | Redeploy the service | Toggle in dashboard, live in seconds |
| Target specific users | Not possible | Individual + rule-based targeting |
| Instant browser updates | Page reload or service restart | Server-Sent Events, no reload |
| Evaluate a flag in the browser | Ship rules to the client, or call your backend | Client-side JS SDK: evaluated values only, never rules |
| Audit trail | None | Who changed what, when, and why |
| Tune a runtime parameter | Redeploy to change a constant | Number/String/JSON flag, changed live |
| AI model/prompt control | Hardcoded string constants | Change from dashboard, no deploy |
| Rollback under incident | Revert commit, deploy | Toggle the flag off |

---

## Integration Steps

### Step 1: Sign Up and Get Your SDK Key

1. Create a free trial at [launchdarkly.com/start-trial](https://launchdarkly.com/start-trial/)
2. Go to **Organization settings → Environments → Test**
3. Copy your **Server-side SDK key** (starts with `sdk-`)
4. Also copy your **Client-side ID** for any browser-side evaluations
5. Store both in your `.env` file, never commit them

```env
LD_SERVER_SDK_KEY="sdk-your-key-here"
LD_CLIENT_SIDE_ID="your-client-side-id"
```

> The server-side SDK key is secret. The client-side ID is safe to expose in browser code.

---

### Step 2: Install the SDK

#### Python

```bash
pip install launchdarkly-server-sdk==9.8.0
```

For AI Config support, also install the AI SDK:

```bash
pip install launchdarkly-server-sdk-ai==0.6.0
pip install anthropic==0.40.0
```

#### Go

```bash
go get github.com/launchdarkly/go-server-sdk/v7
go get github.com/launchdarkly/go-sdk-common/v3
go get github.com/joho/godotenv   # optional: load .env file
```

#### Java (Maven `pom.xml`)

```xml
<dependency>
    <groupId>com.launchdarkly</groupId>
    <artifactId>launchdarkly-java-server-sdk</artifactId>
    <version>7.5.0</version>
</dependency>
<dependency>
    <groupId>io.github.cdimascio</groupId>
    <artifactId>dotenv-java</artifactId>
    <version>3.0.0</version>
</dependency>
```

---

### Step 3: Initialize the Client

Initialize **once at application startup** and reuse the instance. The SDK maintains a persistent streaming connection to LaunchDarkly and caches flag values locally.

#### Python

```python
import ldclient
from ldclient import Config
import os

# Initialize once at startup
ldclient.set_config(Config(os.environ["LD_SERVER_SDK_KEY"]))
ld = ldclient.get()

# Optional: wait for the SDK to receive the full flag payload
# ld.wait_for_initialization(5)
```

#### Go

```go
import (
    ld    "github.com/launchdarkly/go-server-sdk/v7"
    "time"
)

// Initialize once, blocks until connected or timeout
client, err := ld.MakeClient(os.Getenv("LD_SERVER_SDK_KEY"), 5*time.Second)
if err != nil {
    log.Fatalf("LaunchDarkly failed to initialize: %v", err)
}
defer client.Close()
```

#### Java (Spring Boot `@Configuration`)

```java
import com.launchdarkly.sdk.server.LDClient;
import io.github.cdimascio.dotenv.Dotenv;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import javax.annotation.PreDestroy;

@Configuration
public class LdConfig {

    @Bean
    public LDClient ldClient() {
        // Load .env relative to the project root
        Dotenv dotenv = Dotenv.configure().directory("../").load();
        String sdkKey = dotenv.get("LD_SERVER_SDK_KEY");
        return new LDClient(sdkKey);
    }

    @PreDestroy
    public void shutdown(LDClient ldClient) throws Exception {
        ldClient.close();
    }
}
```

---

### Step 4: Create Your First Flag in the Dashboard

1. Log in to [app.launchdarkly.com](https://app.launchdarkly.com)
2. Go to **Features → Flags → Create flag**
3. Name: `Part 1: Helix Auto-Scribe` | Key: `helix-auto-scribe` | Type: **Boolean**
4. Default variation: **false** (safe default: off)
5. Save the flag

> The flag **key** in the dashboard must exactly match the string you use in your code.

---

### Step 5: Wrap Your Feature with a Flag Evaluation

Replace the environment variable check with a LaunchDarkly flag evaluation. Every evaluation requires a **Context**: the who being evaluated.

#### Python

```python
from ldclient import Context

# Before (DIY):
if os.getenv("ENABLE_AUTO_SCRIBE") == "true":
    run_ai_coding()

# After (LaunchDarkly):
context = (
    Context.builder(user_key)
    .set("department", department)
    .set("role", role)
    .build()
)

enabled = ld.bool_variation("helix-auto-scribe", context, False)

if enabled:
    run_ai_coding()    # new path, controlled by LD flag
else:
    run_manual_form()  # old path, safe default
```

#### Go

```go
import ldcontext "github.com/launchdarkly/go-sdk-common/v3/ldcontext"

// Before (DIY):
if featureFlags["maternityPathway"] { ... }

// After (LaunchDarkly):
ctx := ldcontext.NewBuilder(userID).
    SetString("department", department).
    SetString("role", role).
    Build()

enabled, _ := client.BoolVariation("helix-maternity-pathway", ctx, false)
```

#### Java

```java
import com.launchdarkly.sdk.LDContext;

// Before (DIY):
if (maternityEnabled) { ... }

// After (LaunchDarkly):
LDContext ctx = LDContext.builder(userId)
        .set("role", role)
        .set("department", department)
        .build();

boolean enabled = ldClient.boolVariation("helix-maternity-pathway", ctx, false);
```

---

### Step 6: Get the Evaluation Reason (Go)

`BoolVariation` returns the value. `BoolVariationDetail` returns the value **and the reason**: which targeting rule matched, or whether it fell through to the default.

```go
detail, err := client.BoolVariationDetail(
    "helix-maternity-pathway",
    ctx,
    false,
)

// detail.Value: the flag value (true / false)
// detail.Reason.Kind: EvaluationReasonKind:
//                             TARGET_MATCH  (individual target matched)
//                             RULE_MATCH    (a targeting rule matched)
//                             FALLTHROUGH   (no rules matched, using default)
//                             OFF           (flag is disabled)
// detail.Reason.RuleIndex: which rule index matched (for RULE_MATCH)
```

Surface `detail.Reason.Kind` in your API response to show users and your team exactly why they are getting a particular experience.

---

### Step 7: Add a Real-Time Flag Listener (No Page Reload)

The LD server-side SDK maintains a streaming connection to LaunchDarkly. When a flag changes, a callback fires on the **server side** in milliseconds, no polling required. Pair this with Server-Sent Events to push the change to every connected browser instantly.

#### Register a flag change listener (Python)

```python
import asyncio
import json

_sse_queues: list[asyncio.Queue] = []
_SYSTEM_CTX = Context.builder("helix-system").build()

def _on_flag_change(event) -> None:
    """Fires in a background thread when the flag value changes."""
    payload = json.dumps({
        "flag":  "helix-auto-scribe",
        "value": event.current_value,
    })
    loop = asyncio.get_event_loop()
    for q in _sse_queues:
        loop.call_soon_threadsafe(q.put_nowait, payload)

ld.get_flag_tracker().add_flag_value_change_listener(
    "helix-auto-scribe",
    _SYSTEM_CTX,
    _on_flag_change,
)
```

#### Stream changes to the browser via SSE (Python + FastAPI)

```python
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator

@app.get("/events")
async def sse_events():
    queue: asyncio.Queue = asyncio.Queue()
    _sse_queues.append(queue)

    async def generate() -> AsyncGenerator[str, None]:
        # Send current flag state immediately on connect
        current = ld.bool_variation("helix-auto-scribe", _SYSTEM_CTX, False)
        yield f"data: {json.dumps({'flag': 'helix-auto-scribe', 'value': current})}\n\n"

        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"  # prevents proxy/browser timeout
        finally:
            _sse_queues.remove(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

#### Listen from the browser (JavaScript)

```javascript
const es = new EventSource("http://localhost:8000/events");

es.onmessage = (event) => {
    const { flag, value } = JSON.parse(event.data);
    if (flag === "helix-auto-scribe") {
        // Panel appears or hides with no page reload
        document.getElementById("auto-scribe-panel").hidden = !value;
    }
};
```

**Result:** Toggle the flag in the LaunchDarkly dashboard. Every connected browser updates in under one second, with no page refresh.

---

### Step 8: Automate Rollback (turn a flag off from code)

Once a flag is wired in, you can flip it without a deployment, manually in the dashboard, or programmatically so a monitor can roll back for you.

**Option A: REST API (token-based, used in this demo).** Turn the flag off with a semantic-patch call. The token is an API access token (**Account settings → Authorization → Access tokens**) with write access to the Test environment, kept in `LD_API_TOKEN`:

```bash
curl -X PATCH "https://app.launchdarkly.com/api/v2/flags/default/helix-auto-scribe" \
  -H "Authorization: $LD_API_TOKEN" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d '{"environmentKey":"test","instructions":[{"kind":"turnFlagOff"}]}'
```

Swap `turnFlagOff` → `turnFlagOn` to release it again. The project key is `default` unless you created a custom project.

**Option B: Flag trigger (no token).** A trigger gives an external system its own webhook URL that turns the flag off, with no API token required. In the dashboard: open `helix-auto-scribe` → **Settings** → **Triggers** → **Add trigger** → **Generic trigger** → **Turn flag off**. LaunchDarkly generates one complete, unguessable URL and shows it only once. Copy the whole thing and POST to it from your monitoring system. (You don't construct this URL by appending a token to a base path; LD issues the entire URL.)

**In production:** wire either approach into PagerDuty, Datadog, or any alerting system. When an error-rate threshold is breached, the monitor flips the flag automatically with no human in the loop.

---

### Step 9: Add Context Attributes for Targeting

The more attributes you put on your context, the more precise your targeting rules can be. Add whatever attributes are meaningful for your rollout decisions.

#### Python

```python
context = (
    Context.builder(user_key)
    .set("department",    "maternity")
    .set("role",          "attending")
    .set("hospitalTier",  "level1")
    .set("hasBirthCenter", True)
    .build()
)
```

#### Go

```go
ctx := ldcontext.NewBuilder(userID).
    SetString("department",   "maternity").
    SetString("role",         "attending").
    SetString("hospitalTier", "level1").
    SetBool("hasBirthCenter", true).
    Build()
```

#### Java

```java
LDContext ctx = LDContext.builder(userId)
        .set("department",    "maternity")
        .set("role",          "attending")
        .set("hospitalTier",  "level1")
        .build();
```

---

### Step 10: Configure Targeting Rules in the Dashboard

Open `helix-maternity-pathway` in LaunchDarkly and set up the following. No code changes required.

**Individual targets**: specific user keys bypass all rules:
- `dr.chen@helixhealth.org` → `true`
- `mary.johnson@helixhealth.org` → `true`

**Rules**: evaluated in order, first match wins:

| Rule | Conditions | Serve |
|---|---|---|
| 1 | `department` is `maternity` AND `role` is `attending` | `true` |
| 2 | `department` is `maternity` AND `role` is `charge_nurse` | `true` |
| 3 | `hospitalTier` is `level1` AND `hasBirthCenter` is `true` | `true` |
| Default | (all others) | `false` |

Future rollout stages (opening to more departments, more roles, all hospitals) are dashboard changes, not code changes.

---

### Step 11: Configuration as a Flag (Java)

Flags aren't only on/off switches. They can carry a value your code reads at runtime. Here a developer has built a blood-pressure alert, but the threshold it fires at is a LaunchDarkly **Number** flag (`helix-bp-alert-threshold`) that the clinical team owns. The alert logic stays in code; the parameter moves to the dashboard.

```java
import com.launchdarkly.sdk.LDContext;

LDContext ctx = LDContext.builder("helix-clinical-platform").build();

// helix-bp-alert-threshold is a NUMBER flag (default 140 mmHg).
// intVariation reads its current value at request time.
int threshold = ldClient.intVariation("helix-bp-alert-threshold", ctx, 140);

boolean alert = reading >= threshold;   // the alert logic lives in code
```

Change `helix-bp-alert-threshold` in the dashboard and call this again. The new threshold is used instantly, with no redeploy. The clinical team can re-tune a clinical parameter as guidelines evolve without ever filing an engineering ticket. Beyond Number flags, the same idea works with String and JSON flags to drive richer configuration.

---

### Step 12: Integrate AI Config (AgentControl)

AI Config lets you control your LLM's model name and system prompt from the LaunchDarkly dashboard. Change either one and the next API call picks it up, with no deployment required.

**Install the AI SDK:**

```bash
pip install launchdarkly-server-sdk-ai==0.6.0
```

**Create an AI Config in the dashboard:**

1. Go to **Agents → Configs → Create config**
2. Name: `Helix Clinical AI` | Key: `helix-clinical-ai`
3. Add three variations (model + system prompt each):
   - **HELIX-SCRIBE-ED**: `claude-haiku-4-5-20251001`, ED coding instructions
   - **HELIX-SCRIBE-OB**: `claude-sonnet-4-5-20251001`, OB coding instructions
   - **HELIX-PARENT**: `claude-sonnet-4-5-20251001`, parent guidance instructions
4. Add targeting rules: `department = ob` → Variation 2, `department = maternity-parent` → Variation 3, default → Variation 1
5. Enable the config

**Integrate in Python:**

```python
from ldai.client import LDAIClient, AIConfig
import anthropic

# Wrap the existing LD client, one extra line
ai_client = LDAIClient(ld)

anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Build a context: the department attribute routes to the right AI variation
context = (
    Context.builder(user_key)
    .set("department", "ed")          # → HELIX-SCRIBE-ED (Haiku)
    # .set("department", "ob")         # → HELIX-SCRIBE-OB (Sonnet)
    # .set("department", "maternity-parent")  # → HELIX-PARENT (Sonnet)
    .build()
)

# One call: model name and system prompt come from the LD dashboard
ai_config, tracker = ai_client.config(
    "helix-clinical-ai",
    context,
    AIConfig(enabled=False),          # safe fallback if flag is off
)

if not ai_config.enabled:
    return {"error": "AI feature is currently disabled"}

# Extract model and prompt from the LD config
model_name = (
    ai_config.model.name
    if ai_config.model and ai_config.model.name
    else "claude-haiku-4-5-20251001"  # fallback model
)
system_prompt = next(
    (m.content for m in (ai_config.messages or []) if m.role == "system"),
    "You are a clinical coding assistant. Return valid JSON only.",
)

# Call Anthropic: model and prompt are fully LD-controlled
response = anthropic_client.messages.create(
    model=model_name,
    max_tokens=1024,
    system=system_prompt,
    messages=[{"role": "user", "content": clinical_transcript}],
)

# Track usage back to LaunchDarkly for AI cost + reliability monitoring
tracker.track_success()
tracker.track_tokens(
    input_tokens=response.usage.input_tokens,
    output_tokens=response.usage.output_tokens,
)
```

**What you can now do from the LD dashboard without touching code:**
- Swap `claude-haiku-4-5-20251001` to `claude-sonnet-4-5-20251001` for ED (more accurate, higher cost)
- Tighten the OB prompt after a coding audit finding
- Add a fourth AI persona for a new specialty
- A/B test two prompt variants and measure accuracy differences

---

### Step 13: Add the Client-Side SDK (Browser)

Everything above runs a **server-side** SDK: your Python, Go, or Java process holds the full ruleset and evaluates flags for any context. Sometimes you also want the **browser itself** to evaluate a flag, to show or hide UI the instant a flag changes without a round trip to your backend. That is the **client-side (JavaScript) SDK**, and it uses a different credential on purpose.

**Two key types, and why it matters.** The server SDK key can read your entire flag configuration, including targeting rules, so it must never reach a browser. The **client-side ID** is different: a browser initialised with it can only ever receive **evaluated values for the single context it sends**, never the rules. That is the security boundary, and it is why a flag has to be explicitly marked *available to client-side SDKs* before the browser can see it.

| | Server SDK key | Client-side ID |
|---|---|---|
| Used by | Python / Go / Java / Node backends | Browser JavaScript, mobile |
| Can read | The full ruleset, any context | Evaluated values for one context |
| Safe in a browser? | **Never** | Yes, it is designed to be public |
| Flag must be marked client-side available? | No | Yes |

**Get the client-side ID to the browser without hardcoding it.** Serve it from your backend, read from the same `.env`, so the ID stays out of git:

```python
# main.py (FastAPI). The server SDK key and other secrets never leave the server.
@app.get("/client-config")
def client_config():
    return {"clientSideId": os.environ["LD_CLIENT_SIDE_ID"]}
```

**Load the SDK with no build step** (ES module from a CDN) and evaluate:

```html
<script>
  const LD_DEFAULT = false;   // fallback shown before ready, and if LD is unreachable
  const context = { kind: 'user', key: 'user-123', department: 'maternity', role: 'attending' };

  async function initLD() {
    const { clientSideId } = await (await fetch('/client-config')).json();
    const LDClient = await import('https://cdn.jsdelivr.net/npm/launchdarkly-js-client-sdk@3.9.3/+esm');

    const client = LDClient.initialize(clientSideId, context, {
      streaming: true,           // open the SDK's own stream for live updates
      evaluationReasons: true,   // so variationDetail() returns the reason
    });

    // Before ready, variation() returns the default you pass (that is the "flicker").
    // waitForInitialization() blocks until the real value is available.
    await client.waitForInitialization(5);

    const detail = client.variationDetail('my-flag', LD_DEFAULT);
    console.log(detail.value, detail.reason.kind);   // e.g. true  FALLTHROUGH

    // Live updates pushed by LaunchDarkly over the SDK's own stream, no reload:
    client.on('change:my-flag', (newValue) => render(newValue));

    // What the browser actually holds: evaluated values only, never rules.
    console.log(client.allFlags());   // { "my-flag": true, ... }
  }
</script>
```

**Design for these on the client:**

- **The ready race.** `initialize()` returns immediately; the real value arrives a moment later. Either `await waitForInitialization()` (no flicker, slower first paint) or render right away and update on the `ready` / `change` event (fast paint, a brief flicker from default to real value). Choose per element.
- **A safe default.** Always pass a default to `variation()`. If LaunchDarkly is unreachable, the browser serves that default while your server-side path keeps working.
- **Mark the flag client-side available.** In the flag's **Settings**, check **"SDKs using Client-side ID"**, or the browser cannot see it.
- **Never expose the server SDK key** or any server secret to the browser. Only the client-side ID belongs there.

---

## Verifying Your Integration

After each step, confirm the integration is working end-to-end.

```bash
# 1. Confirm the Python service is up and LD SDK is initialized
curl http://localhost:8000/health
# Expected: {"status": "ok", "sdk_initialized": true, ...}

# 2. Confirm flag evaluation works (Python)
curl -X POST http://localhost:8000/code-encounter \
  -H "Content-Type: application/json" \
  -d '{"transcript": "Patient presents with chest pain.", "department": "ed", "userId": "test-provider"}'

# 3. Confirm targeting + evaluation reason works (Go)
curl "http://localhost:8001/feature?userId=dr.alvarez@helixhealth.org&department=maternity&role=attending"
# Expected: {"enabled": true, "reason": "RULE_MATCH", ...}

curl "http://localhost:8001/feature?userId=dr.reed@helixhealth.org&department=emergency&role=attending"
# Expected: {"enabled": false, "reason": "FALLTHROUGH", ...}

# 4. Confirm the config-driven alert works (Java)
curl "http://localhost:8002/lab-check?value=135"
# Expected: {"flag": "helix-bp-alert-threshold", "value": 135, "threshold": 140, "alert": false}

# 5. Confirm the client-side ID is served to the browser (Part 5)
curl http://localhost:8000/client-config
# Expected: {"clientSideId": "..."}  (safe to expose; never returns the server SDK key)
```

---

## Capability Summary

| LaunchDarkly Capability | Helix Implementation | Benefit |
|---|---|---|
| Feature flag release | `helix-auto-scribe` wraps AI coding panel | Deploy anytime; release when confident |
| Real-time listener | SSE stream: flag change → browser update | No page reload, no polling |
| REST API rollback | PATCH the flag off via the LD API | Seconds to remediate, not hours |
| Context-based targeting | Department attribute drives the Maternity Pathway | Precise rollout without code changes |
| Evaluation reason | Go SDK returns `RULE_MATCH` / `FALLTHROUGH` | Explain exactly why a user got a result |
| Configuration as a flag | Java reads a Number flag for a clinical alert threshold | Non-engineers tune real behaviour, no redeploy |
| AI Config | Model + prompt per clinical persona | Iterate on AI without deployments |
| Client-side evaluation | Browser JS SDK evaluates with the client-side ID | Flags in the browser; only values, never rules, are exposed |

---

## Further Reading

- [LaunchDarkly Python SDK docs](https://docs.launchdarkly.com/sdk/server-side/python)
- [LaunchDarkly Go SDK docs](https://docs.launchdarkly.com/sdk/server-side/go)
- [LaunchDarkly Java SDK docs](https://docs.launchdarkly.com/sdk/server-side/java)
- [LaunchDarkly JavaScript (client-side) SDK docs](https://docs.launchdarkly.com/sdk/client-side/javascript)
- [AI Config (AgentControl) docs](https://docs.launchdarkly.com/home/ai-configs)
- [REST API: update a flag](https://docs.launchdarkly.com/tag/feature-flags#operation/patchFeatureFlag)
- [Custom roles & access tokens](https://docs.launchdarkly.com/home/account/api)
