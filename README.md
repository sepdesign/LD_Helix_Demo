# Helix Health Group — LaunchDarkly SE Demo

A multi-service clinical platform demonstrating LaunchDarkly across **Python**, **Go**, and **Java** — covering feature flag releases, real-time rollback, context-based targeting, multi-context evaluation, AI Config via AgentControl, and Experimentation.

---

## The Scenario

**Helix Health Group** operates 47 hospitals across 12 states — Level I trauma centers through dedicated birth centers — on a single unified clinical platform.

Three engineering teams are shipping simultaneously:

| Team | Service | SDK | Assignment Coverage |
|------|---------|-----|---------------------|
| Clinical AI team | `python-service` | Python + LD AI SDK | Part 1: Release & Remediate + Extra: AI Config |
| Patient Access team | `go-service` | Go | Part 2: Targeting |
| Analytics team | `java-service` | Java (Spring Boot) | Part 2: Multi-context + Experimentation |

The `frontend/index.html` is a single-file clinical dashboard — no build step, open directly in Chrome.

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.10+ | `python --version` |
| Go | 1.21+ | `go version` |
| Java | 17+ | `java -version` |
| Maven | 3.6+ | `mvn -version` |
| Chrome | Any | For the frontend |

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/helix-health-ld-demo.git
cd helix-health-ld-demo
```

### 2. Configure credentials

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Your Anthropic API key — https://console.anthropic.com
ANTHROPIC_API_KEY="sk-ant-api03-..."

# LaunchDarkly Test environment — Organization settings > SDK keys
LD_SERVER_SDK_KEY="sdk-..."      # Server-side: used by Python, Go, Java (keep secret)
LD_CLIENT_SIDE_ID="..."          # Client-side ID: used by browser JS (safe to expose)
```

> **Never commit `.env`** — it is gitignored.

### 3. Create LaunchDarkly flags

Log in to [app.launchdarkly.com](https://app.launchdarkly.com) and create the following in your **Test** environment.

---

#### Flag 1 — `helix-auto-scribe` (Boolean)
> Controls the AI clinical transcription + billing-code feature. Part 1.

1. **Features → Flags → Create flag**
2. Name: `Helix Auto-Scribe`  |  Key: `helix-auto-scribe`  |  Type: Boolean
3. Default OFF. Leave all targeting rules empty for now.
4. **Set up a Trigger** (for the Remediate demo):
   - Open the flag → **Settings** tab → **Triggers** → **Add trigger**
   - Type: **Generic trigger**
   - Action: **Turn flag off**
   - Copy the generated URL — use it in the curl command during the demo

---

#### Flag 2 — `helix-maternity-pathway` (Boolean with targeting)
> Controls the maternity pathway feature rollout. Part 2.

1. **Features → Flags → Create flag**
2. Name: `Helix Maternity Pathway`  |  Key: `helix-maternity-pathway`  |  Type: Boolean
3. **Targeting ON** (toggle targeting on in the Test environment)
4. Add **Individual targets**:
   - `dr.chen@helixhealth.org` → **true**
   - `mary.johnson@helixhealth.org` → **true**
5. Add **Rules** (in order):
   - Rule 1: `department` **is one of** `maternity` AND `role` **is one of** `attending` → **true**
   - Rule 2: `department` **is one of** `maternity` AND `role` **is one of** `charge_nurse` → **true**
   - Rule 3: `hospitalTier` **is one of** `level1` AND `hasBirthCenter` **is** `true` → **true**
6. Default rule → **false**
7. Save

---

#### Flag 3 — `helix-clinical-ai` (AI Config)
> Controls model + system prompt for three clinical AI personas. Extra Credit.

1. **Agents → Configs → Create config**
2. Name: `Helix Clinical AI`  |  Key: `helix-clinical-ai`
3. Add **three variations**:

**Variation 1 — HELIX-SCRIBE-ED** (default for `department=ed`)
- Model: `claude-haiku-4-5-20251001`
- Instructions:
```
You are HELIX-SCRIBE-ED, a clinical coding assistant for emergency medicine.
Extract ICD-10 and CPT codes from the encounter transcript.
Be precise and fast. Focus on: injury codes (S/T), E&M complexity (99281-99285),
and emergency procedure CPTs. Return valid JSON only — no markdown, no explanation.
```

**Variation 2 — HELIX-SCRIBE-OB** (for `department=ob`)
- Model: `claude-sonnet-4-5-20251001`
- Instructions:
```
You are HELIX-SCRIBE-OB, a clinical coding assistant for obstetrics and gynecology.
Extract ICD-10 and CPT codes from the obstetric encounter transcript.
Focus on: obstetric codes (O/Z ICD-10), prenatal visit CPTs (59400, 59410),
delivery and postpartum codes. Be thorough — OB coding requires accuracy.
Return valid JSON only — no markdown, no explanation.
```

**Variation 3 — HELIX-PARENT** (for `department=maternity-parent`)
- Model: `claude-sonnet-4-5-20251001`
- Instructions:
```
You are HELIX-PARENT, a compassionate care assistant for new parents at Helix Health Group.
You help parents assess their newborn's symptoms and understand when to seek care.
Be warm, clear, and evidence-based. Use plain language — not medical jargon.
Always recommend calling 911 or going to the ED for: high fever in newborns under 3 months,
difficulty breathing, blue/grey skin, unresponsiveness, or seizures.
Never diagnose — guide parents on when to seek care and what to expect.
Reference current AAP guidelines when relevant.
```

4. Set up **targeting rules** so the right variation fires by department:
   - Rule: `department` **is one of** `ob` → serve Variation 2
   - Rule: `department` **is one of** `maternity-parent`, `postpartum` → serve Variation 3
   - Default → serve Variation 1 (ED)
5. Enable the config

---

## Running the Services

Open **four terminals** from the project root.

### Terminal 1 — Python service (port 8000)

```bash
cd python-service
pip install -r requirements.txt
python main.py
```

Expected output:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Terminal 2 — Go service (port 8001)

```bash
cd go-service
go mod tidy
go run main.go
```

Expected output:
```
LaunchDarkly Go SDK initialised successfully
Go service listening on :8001
```

### Terminal 3 — Java service (port 8002)

```bash
cd java-service
mvn spring-boot:run
```

Expected output:
```
Started HelixApplication in X.XXX seconds
```

### Terminal 4 — Frontend

```bash
cd frontend
python -m http.server 3000
```

Then open **http://localhost:3000** in Chrome.

> The Python service must be running for the SSE flag-change listener to work.  
> The Go and Java services are needed for the targeting demo tabs.

---

## Demo Walkthrough

### Part 1 — Release & Remediate

1. Open the **Part 1 — Release** tab in the dashboard
2. The `helix-auto-scribe` badge in the top-right shows **OFF**
3. In LaunchDarkly: toggle `helix-auto-scribe` **ON**
4. The Auto-Scribe panel appears in the browser **instantly** — no page reload
5. Select department, load a sample encounter, click **Generate Billing Codes**
6. Claude returns structured ICD-10 + CPT codes
7. **Remediate**: run the trigger curl command (from the Remediate card):
   ```bash
   curl -X POST "https://app.launchdarkly.com/api/v1/flags/triggers/YOUR_TRIGGER_URL"
   ```
8. The panel disappears instantly — flag is OFF, no deployment

### Part 2 — Targeting

1. Open the **Part 2 — Target** tab
2. Click each persona card — the Go service evaluates the flag and returns the reason:
   - `TARGET_MATCH` for Dr. Chen and Mary Johnson (individual targets)
   - `RULE_MATCH` for Dr. Patel (Rule 1) and Dr. Torres (Rule 3)
   - `FALLTHROUGH` for Nurse Kim (default OFF)

### Multi-Context (Java)

1. Open the **Multi-Context (Java)** tab
2. Set `orgPlan = enterprise` for a hospital that doesn't match user-level rules
3. The Java service evaluates against both the user context AND the organization context simultaneously
4. Click **Track Event** to fire a custom metric into LD Experimentation

### AI Config / AgentControl

1. Open the **AI Config** tab
2. Select **ED** department → Haiku model, ED coding prompt
3. Select **OB** department → Sonnet model, OB coding prompt
4. Open the **Parent Connect** tab and send one of the sample messages
5. Claude responds with warm, empathetic guidance (HELIX-PARENT variation)
6. Swap the system prompt in LD → next call uses the new prompt, no code change

---

## Architecture

```
helix-health-ld-demo/
├── .env.example          # Template — copy to .env and fill in keys
├── .gitignore
├── README.md
│
├── python-service/
│   ├── main.py           # FastAPI: SSE stream, AI Config, flag trigger
│   └── requirements.txt
│
├── go-service/
│   ├── main.go           # HTTP server: BoolVariationDetail with targeting context
│   └── go.mod
│
├── java-service/
│   ├── pom.xml           # Spring Boot 3.2, LD Java SDK 7.x
│   └── src/main/java/com/helixhealth/
│       ├── HelixApplication.java
│       ├── LdConfig.java       # LD client bean
│       └── FeatureController.java  # Multi-context + event tracking
│
└── frontend/
    └── index.html        # Single-file clinical dashboard — no build step
```

---

## LD Flags Quick Reference

| Flag Key | Type | SDK(s) | Demo Tab |
|----------|------|--------|----------|
| `helix-auto-scribe` | Boolean | Python | Part 1 — Release |
| `helix-maternity-pathway` | Boolean + Targeting | Go, Java | Part 2 — Target |
| `helix-clinical-ai` | AI Config (agent) | Python + LD AI SDK | AI Config, Parent Connect |

---

## Troubleshooting

**SSE shows "disconnected"**  
→ Python service is not running. Start it with `python main.py` in `python-service/`.

**Go service returns an error**  
→ Run `go mod tidy` first to download dependencies.

**Java service fails to start**  
→ Ensure Java 17+ and Maven 3.6+ are installed. Check `LD_SERVER_SDK_KEY` is set in `.env`.

**AI returns an error**  
→ Verify `ANTHROPIC_API_KEY` in `.env` is valid and the `helix-clinical-ai` AI Config is enabled in LD.

**Flag changes don't appear in UI**  
→ Check the Python service logs for `[LD FLAG CHANGE]` lines. If absent, verify `LD_SERVER_SDK_KEY` is the **server-side** key (starts with `sdk-`), not the client-side ID.
