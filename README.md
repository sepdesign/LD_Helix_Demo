# Helix Health Group: LaunchDarkly SE Demo

Three-service demo built with **Python**, **Go**, and **Java**. Covers feature flag release, instant rollback, context-based targeting, multi-context evaluation, Experimentation, and AI Config.

---

## The Scenario

**Helix Health Group** operates 47 hospitals across 12 states, from Level I trauma centers to dedicated birth centers, on a single unified clinical platform.

Three engineering teams are shipping simultaneously:

| Team | Service | SDK | Assignment Coverage |
|------|---------|-----|---------------------|
| Clinical AI team | `python-service` | Python + LD AI SDK | Part 1: Release & Remediate + Extra: AI Config |
| Patient Access team | `go-service` | Go | Part 2: Targeting |
| Analytics team | `java-service` | Java (Spring Boot) | Part 2: Multi-context + Experimentation |

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
```

> **Never commit `.env`.** It is gitignored.

### 3. Create LaunchDarkly flags

Log in to [app.launchdarkly.com](https://app.launchdarkly.com) and create the following in your **Test** environment.

---

#### Flag 1: `helix-auto-scribe` (Boolean)

Controls the AI clinical transcription and billing-code feature. Used in Part 1.

1. **Features → Flags → Create flag**
2. Name: `Helix Auto-Scribe`  |  Key: `helix-auto-scribe`  |  Type: Boolean
3. Default OFF. Leave targeting rules empty for now.
4. Set up a trigger for the Remediate demo:
   - Open the flag → **Settings** tab → **Triggers** → **Add trigger**
   - Type: **Generic trigger**
   - Action: **Turn flag off**
   - Copy the generated URL and keep it handy for the demo

---

#### Flag 2: `helix-maternity-pathway` (Boolean with targeting)

Controls the maternity pathway rollout. Used in Part 2.

1. **Features → Flags → Create flag**
2. Name: `Helix Maternity Pathway`  |  Key: `helix-maternity-pathway`  |  Type: Boolean
3. Turn targeting ON in the Test environment
4. Add individual targets:
   - `dr.chen@helixhealth.org` → **true**
   - `mary.johnson@helixhealth.org` → **true**
5. Add rules in this order:
   - Rule 1: `department` **is one of** `maternity` AND `role` **is one of** `attending` → **true**
   - Rule 2: `department` **is one of** `maternity` AND `role` **is one of** `charge_nurse` → **true**
   - Rule 3: `hospitalTier` **is one of** `level1` AND `hasBirthCenter` **is** `true` → **true**
6. Default rule → **false**
7. Save

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
> Go and Java are needed for the targeting and multi-context demo tabs.

---

## Demo Walkthrough

### Part 1: Release & Remediate

1. Open the **Part 1 Release** tab in the dashboard
2. The `helix-auto-scribe` badge shows **OFF**
3. In LaunchDarkly, toggle `helix-auto-scribe` **ON**
4. The Auto-Scribe panel appears instantly with no page reload
5. Select a department, load a sample encounter, click **Generate Billing Codes**
6. Claude returns structured ICD-10 and CPT codes
7. To remediate, run the trigger curl command from the Remediate card:
   ```bash
   curl -X POST "https://app.launchdarkly.com/api/v1/flags/triggers/YOUR_TRIGGER_URL"
   ```
8. The panel disappears. Flag is OFF, no deployment needed.

### Part 2: Targeting

1. Open the **Part 2 Target** tab
2. Click each persona card. The Go service evaluates the flag and returns the reason:
   - `TARGET_MATCH` for Dr. Chen and Mary Johnson (individual targets)
   - `RULE_MATCH` for Dr. Patel (Rule 1) and Dr. Torres (Rule 3)
   - `FALLTHROUGH` for Nurse Kim (default OFF)

### Multi-Context (Java)

1. Open the **Multi-Context** tab
2. Set `orgPlan = enterprise` for a hospital that doesn't match user-level rules alone
3. The Java service evaluates against both user and organization context
4. Click **Track Event** to fire a custom metric into LD Experimentation

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
├── python-service/
│   ├── main.py           # FastAPI: SSE stream, AI Config, flag trigger
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
│       └── FeatureController.java  # multi-context + event tracking
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
