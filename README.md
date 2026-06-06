# Helix Health Group: LaunchDarkly SE Demo

Three-service demo built with **Python**, **Go**, and **Java**. Covers feature flag release, instant rollback, context-based targeting, configuration-driven features (a Number flag), and AI Config.

---

## The Scenario

**Helix Health Group** operates 47 hospitals across 12 states, from Level I trauma centers to dedicated birth centers, on a single unified clinical platform.

Three engineering teams are shipping simultaneously:

| Team | Service | SDK | Assignment Coverage |
|------|---------|-----|---------------------|
| Clinical AI team | `python-service` | Python + LD AI SDK | Part 1: Release & Remediate + Extra: AI Config |
| Patient Access team | `go-service` | Go | Part 2: Targeting |
| Patient Safety team | `java-service` | Java (Spring Boot) | Part 3: Config-driven clinical alert |

`frontend/index.html` is a single-file clinical dashboard. No build step; open directly in Chrome.

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.10+ | `python --version` |
| Go | 1.21+ | `go version` |
| Java | 17+ | `java -version` |
| Maven | 3.6+ | `mvn -version` |
| Chrome | Any | For the frontend |

Validated against Python 3.12, Go 1.26, Temurin (Eclipse Adoptium) JDK 17, and Maven 3.9.

### Verify your environment

Before creating flags or starting services, run the bundled prerequisite checker. It confirms your toolchain versions, that `.env` holds the three required credentials, that the Python packages are importable, and which service ports are free:

```bash
python scripts/check_prerequisites.py
```

Exit code `0` means every required check passed (warnings do not fail the run). Sample output:

```
==============================================================
 Helix Health Group: LaunchDarkly demo prerequisite check
==============================================================

Toolchain
---------
 [ OK ]  Python  ->  3.12.10  (>= 3.10)
 [ OK ]  Go      ->  1.26.4  (>= 1.21)
 [ OK ]  Java    ->  17.0.19  (>= 17)
 [ OK ]  Maven   ->  3.9.9  (>= 3.6)

Environment (.env)
------------------
 [ OK ]  .env file  ->  /path/to/LD_Helix_Demo/.env
 [ OK ]  ANTHROPIC_API_KEY  ->  sk-ant-...  (108 chars)
 [ OK ]  LD_SERVER_SDK_KEY  ->  sdk-f18...  (40 chars)
 [ OK ]  LD_CLIENT_SIDE_ID  ->  6a1e36e...  (24 chars)
...
 RESULT: all required checks passed
```

The checker masks secrets (it prints only a short prefix and the length), so its output is safe to paste into an issue or share while pairing.

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/sepdesign/LD_Helix_Demo.git
cd LD_Helix_Demo
```

### 2. Configure credentials

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Anthropic API key (https://console.anthropic.com)
ANTHROPIC_API_KEY="sk-ant-api03-..."

# LaunchDarkly Test environment server-side key (Organization settings > SDK keys)
LD_SERVER_SDK_KEY="sdk-..."      # used by Python, Go, Java (keep secret)
LD_CLIENT_SIDE_ID="..."          # used by browser JS (safe to expose)

# REST API access token, used to turn the flag on/off from the command line in
# Part 1 (Account settings > Authorization > Access tokens; write access to Test).
LD_API_TOKEN="api-..."           # keep secret
```

> **Never commit `.env`.** It is gitignored.

Before running the Part 1 curl commands, export the API token in your shell so `$LD_API_TOKEN` resolves:
>
> ```bash
> export LD_API_TOKEN=api-...          # bash / zsh
> $env:LD_API_TOKEN="api-..."          # PowerShell
> ```

### 3. Run the prerequisite check

Confirm your toolchain, credentials, and ports before going further:

```bash
python scripts/check_prerequisites.py
```

Fix any `[FAIL]` items it reports, then continue. (See [Verify your environment](#verify-your-environment) above for sample output.)

### 4. Create LaunchDarkly flags

Log in to [app.launchdarkly.com](https://app.launchdarkly.com) and create the following in your **Test** environment.

---

#### Flag 1: `helix-auto-scribe` (Boolean)

Controls the AI clinical transcription and billing-code feature. Used in Part 1.

1. **Features → Flags → Create flag**
2. Name: `Helix Auto-Scribe`  |  Key: `helix-auto-scribe`  |  Type: Boolean
3. Default OFF. Leave targeting rules empty for now.
4. No per-flag trigger is needed — the Remediate step turns this flag off from the
   command line via the LaunchDarkly REST API, using the account-level `LD_API_TOKEN`
   you set in step 2. (Flag *triggers* are a valid no-token webhook alternative if you
   want your monitoring system to flip the flag directly; not required for this demo.)

---

#### Flag 2: `helix-maternity-pathway` (Boolean with targeting)

Controls who sees the new Maternity Care Pathway module. Used in Part 2.

1. **Features → Flags → Create flag**
2. Name: `Helix Maternity Pathway`  |  Key: `helix-maternity-pathway`  |  Type: Boolean
3. Turn targeting ON in the Test environment
4. Add one rule:
   - Rule 1: `department` **is one of** `maternity` → serve **true**
5. Default rule → **false**
6. Save

> **One-rule story (recommended).** The demo tells a clean story — *maternity staff see the Pathway, everyone else gets the standard chart* — so a single `department is maternity` rule is all you need. You can layer on more targeting later (individual pilot users, role conditions, hospital tier, percentage rollouts) entirely from the dashboard with no code change. The demo personas (Dr. Alvarez, Grace Liu, Dr. Reed) resolve correctly under this single rule; they also work if you keep additional rules.

---

#### Flag 3: `helix-clinical-ai` (AI Config)

Controls the model and system prompt for three clinical AI personas. Used for AI Config.

1. **Agents → Configs → Create config**
2. Name: `Helix Clinical AI`  |  Key: `helix-clinical-ai`
3. Add three variations:

**Variation 1: HELIX-SCRIBE-ED** (default for `department=ed`)
- Model: `claude-haiku-4-5-20251001`
- Instructions:
```
You are HELIX-SCRIBE-ED, a clinical coding assistant for emergency medicine.
Extract ICD-10 and CPT codes from the encounter transcript.
Be precise and fast. Focus on: injury codes (S/T), E&M complexity (99281-99285),
and emergency procedure CPTs. Return valid JSON only. No markdown, no explanation.
```

**Variation 2: HELIX-SCRIBE-OB** (for `department=ob`)
- Model: `claude-sonnet-4-5-20251001`
- Instructions:
```
You are HELIX-SCRIBE-OB, a clinical coding assistant for obstetrics and gynecology.
Extract ICD-10 and CPT codes from the obstetric encounter transcript.
Focus on: obstetric codes (O/Z ICD-10), prenatal visit CPTs (59400, 59410),
delivery and postpartum codes. Be thorough. OB coding requires accuracy.
Return valid JSON only. No markdown, no explanation.
```

**Variation 3: HELIX-PARENT** (for `department=maternity-parent`)
- Model: `claude-sonnet-4-5-20251001`
- Instructions:
```
You are HELIX-PARENT, a care assistant for new parents at Helix Health Group.
Help parents assess their newborn's symptoms and know when to seek care.
Be warm, clear, and evidence-based. Use plain language, not medical jargon.
Always recommend calling 911 or going to the ED for: high fever in newborns under 3 months,
difficulty breathing, blue/grey skin, unresponsiveness, or seizures.
Never diagnose. Guide parents on when to seek care and what to expect.
Reference current AAP guidelines when relevant.
```

4. Set up targeting rules by department:
   - `department` **is one of** `ob` → serve Variation 2
   - `department` **is one of** `maternity-parent`, `postpartum` → serve Variation 3
   - Default → serve Variation 1 (ED)
5. Enable the config

---

#### Flag 4: `helix-bp-alert-threshold` (Number)

Controls the blood-pressure threshold the Java service uses to raise an alert. Used in Part 3.

1. **Features → Flags → Create flag**
2. Name: `Helix BP Alert Threshold`  |  Key: `helix-bp-alert-threshold`  |  Type: **Number**
3. Set the variation value to **`140`** (mmHg — the usual preeclampsia screening cut-off) and make it the default served value
4. Save. During the demo you'll change this number (e.g. to `130`) and watch the same reading flip from NORMAL to ALERT — no redeploy.

> The Java service defaults to `140` if this flag is missing, so Part 3 still runs before you create it; creating the flag is what lets you change the threshold live.

---

## Running the Services

You'll need four terminals open from the project root.

### Terminal 1: Python service (port 8000)

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

### Terminal 2: Go service (port 8001)

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

### Terminal 3: Java service (port 8002)

```bash
cd java-service
mvn spring-boot:run
```

Expected output:
```
Started HelixApplication in X.XXX seconds
```

### Terminal 4: Frontend

```bash
cd frontend
python -m http.server 3000
```

Open **http://localhost:3000** in Chrome.

> The Python service must be running for the SSE listener to work.  
> Go and Java are needed for the Part 2 (targeting) and Part 3 (evaluate) demo tabs.

---

## Demo Walkthrough

### Part 1: Release & Remediate

1. Open the **Part 1 Release** tab in the dashboard
2. The `helix-auto-scribe` badge shows **OFF**
3. **Release:** in LaunchDarkly, toggle `helix-auto-scribe` **ON** (or run the REST call below with `turnFlagOn`)
4. The Auto-Scribe panel appears instantly with no page reload — the Python service streams the change to the browser over SSE
5. Select a department, load a sample encounter, click **Generate Billing Codes**
6. Claude returns structured ICD-10 and CPT codes
7. **Remediate:** turn the flag off via the LaunchDarkly REST API — from curl, Postman, or your monitoring tool. Uses `$LD_API_TOKEN` (the project key is `default` unless you created a custom project):
   ```bash
   curl -X PATCH "https://app.launchdarkly.com/api/v2/flags/default/helix-auto-scribe" \
     -H "Authorization: $LD_API_TOKEN" \
     -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
     -d '{"environmentKey":"test","instructions":[{"kind":"turnFlagOff"}]}'
   ```
   (Swap `turnFlagOff` → `turnFlagOn` to release it again.)
8. The panel disappears instantly over SSE. Flag is OFF, no deployment needed.

> **Sending it from Postman:** method `PATCH`, same URL. Headers: `Authorization: <your token>` (no "Bearer" prefix) and `Content-Type: application/json; domain-model=launchdarkly.semanticpatch`. Body → raw JSON: `{"environmentKey":"test","instructions":[{"kind":"turnFlagOff"}]}`.
> ⚠️ Postman auto-adds `Content-Type: application/json` when you pick raw/JSON — **edit it** to keep the `; domain-model=launchdarkly.semanticpatch` suffix, or LD returns `400`.

### Part 2: Targeting — Maternity Care Pathway

The story: *Helix is rolling out a new Maternity Care Pathway module. Maternity staff see it; everyone else keeps the standard chart.* One rule decides — `department is maternity → ON`, default OFF.

1. Open the **Part 2 Target** tab
2. Click **Dr. Alvarez (Maternity)** → the **Maternity Care Pathway** module renders in the patient chart (stage tracker, care plan, order sets)
3. Click **Grace Liu, RN (Maternity)** → the same Pathway module — it's the *department*, not the role
4. Click **Dr. Reed (Emergency)** → the **standard chart** (vitals only) with a "not enabled" note
5. Expand **"LaunchDarkly evaluation detail"** under the chart to see the SDK reason (`RULE_MATCH` for the maternity staff, `FALLTHROUGH` for Dr. Reed) and the exact context sent
6. To change who's in, edit the rule in LD (e.g., add `emergency`) and re-click a clinician — the chart re-renders, no redeploy

> The Go service returns `enabled` + `reason` via `BoolVariationDetail`; the UI renders the Pathway module when `enabled` is `true`, the standard chart when `false`.

### Part 3: Configuration as a Flag (Java)

Flags aren't only on/off switches — they can carry a value your code reads at runtime. A developer built a blood-pressure alert; the **threshold** it fires at is a LaunchDarkly **Number** flag (`helix-bp-alert-threshold`, default 140 mmHg) that the clinical team owns. The Java service reads it via `GET /lab-check?value=…`.

1. Open the **Part 3: Alerts** tab
2. Enter a systolic blood pressure (the box defaults to **135**) and click **Check reading** → **✅ NORMAL** (135 is below the 140 threshold)
3. In LaunchDarkly, lower **`helix-bp-alert-threshold`** from 140 to **130**, then check **135** again → **🚨 ALERT**
4. Same reading, new behaviour — the Java SDK read the new threshold live. The alert *logic* is in code; the *threshold* is owned in the dashboard, with no redeploy

> The Java service uses `intVariation` with a default of 140, so Part 3 runs even before you create the flag; creating `helix-bp-alert-threshold` (Flag 4 above) is what lets you change the threshold live. This shows flags carrying **configuration**, not just toggles.

### AI Config

1. Open the **AI Config** tab
2. Select **ED** department: Haiku model, ED coding prompt
3. Select **OB** department: Sonnet model, OB coding prompt
4. Open the **Parent Connect** tab and send one of the sample messages
5. Claude responds through the HELIX-PARENT variation
6. Update the system prompt in LD and generate again. The next call picks it up with no code change.

---

## Architecture

```
LD_Helix_Demo/
├── .env.example          # copy to .env and fill in your keys
├── .gitignore
├── README.md
├── INTEGRATION_GUIDE.md  # how to add LD to an app from scratch
│
├── scripts/
│   └── check_prerequisites.py  # verifies toolchain, .env, pip deps, ports
│
├── python-service/
│   ├── main.py           # FastAPI: SSE stream, AI Config, Parent Connect
│   └── requirements.txt
│
├── go-service/
│   ├── main.go           # BoolVariationDetail with targeting context
│   └── go.mod
│
├── java-service/
│   ├── pom.xml           # Spring Boot 3.2, LD Java SDK 7.x
│   └── src/main/java/com/helixhealth/
│       ├── HelixApplication.java
│       ├── LdConfig.java
│       └── FeatureController.java  # GET /lab-check (config-driven alert)
│
├── frontend/
│   └── index.html        # single-file clinical dashboard, no build step
│
└── presentation/
    └── index.html        # reveal.js slide deck, open in Chrome
```

---

## Flag Reference

| Flag Key | Type | SDK(s) | Demo Tab |
|----------|------|--------|----------|
| `helix-auto-scribe` | Boolean | Python | Part 1 Release |
| `helix-maternity-pathway` | Boolean + Targeting | Go, Java | Part 2 Target |
| `helix-clinical-ai` | AI Config | Python + LD AI SDK | AI Config, Parent Connect |

---

## Troubleshooting

**SSE shows "disconnected"**  
Python service is not running. Start it with `python main.py` in `python-service/`.

**Go service returns an error**  
Run `go mod tidy` first to download dependencies.

**Java service fails to start**  
Check that Java 17+ and Maven 3.6+ are installed, and that `LD_SERVER_SDK_KEY` is set in `.env`.

**AI returns an error**  
Verify `ANTHROPIC_API_KEY` in `.env` is valid and the `helix-clinical-ai` AI Config is enabled in LD.

**Flag changes don't appear in the browser**  
Check the Python service logs. If no `[LD FLAG CHANGE]` lines appear, verify `LD_SERVER_SDK_KEY` is the server-side key (starts with `sdk-`), not the client-side ID.
