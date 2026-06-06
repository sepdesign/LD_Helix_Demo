// Helix Health Group: Patient Access & Targeting Service (Go)
// =============================================================
// Part 2 of the demo: the helix-maternity-pathway flag, evaluated per clinician.
//
// The story: Helix is rolling out a new "Maternity Care Pathway" module. A single
// targeting rule decides who sees it — "department is maternity" → on, everyone
// else off. The browser asks this service to evaluate the flag for a given
// clinician, then renders either the Pathway module or the plain standard chart
// based on the answer.
//
// What this file shows off:
//   • Building an ldcontext from a clinician's attributes (department, role)
//   • BoolVariationDetail — returns BOTH the true/false value AND the reason
//     (RULE_MATCH, FALLTHROUGH, ...), so the UI can explain *why* a clinician
//     got the result they did
//   • A flag-change listener that logs to stdout the instant the flag changes
//     in LaunchDarkly, before any new request even arrives
//
// Run:
//   go mod tidy
//   go run main.go

package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/joho/godotenv"
	"github.com/launchdarkly/go-sdk-common/v3/ldcontext"
	ld "github.com/launchdarkly/go-server-sdk/v7"
)

var ldClient *ld.LDClient

// FeatureResponse is what we return to the frontend for the targeting demo.
type FeatureResponse struct {
	UserID     string            `json:"userId"`
	Flag       string            `json:"flag"`
	Enabled    bool              `json:"enabled"`
	Reason     string            `json:"reason"`   // RULE_MATCH, FALLTHROUGH, or OFF
	Context    map[string]string `json:"context"`  // attributes used in the evaluation
}

// cors wraps a handler with permissive CORS headers for the demo frontend.
func cors(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusOK)
			return
		}
		next(w, r)
	}
}

// GET /feature
//
// The frontend calls this once per clinician (when you click a persona card).
// Query params describe who that clinician is:
//   userId      string: provider email / unique key
//   name        string: display name (cosmetic)
//   department  string: "maternity" | "ed" | "general" ...  ← what the rule checks
//   role        string: "attending" | "charge_nurse" ...    ← carried for display
//
// The LaunchDarkly targeting rule for helix-maternity-pathway is deliberately
// simple — one attribute, one rule:
//   Rule    : department is one of "maternity"  → true
//   Default : false
//
// You can expand the rollout entirely from the dashboard later (add another
// department, target a single provider by key, gate by hospital, ramp by
// percentage) without touching a line of this code.
func featureHandler(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()

	userID := q.Get("userId")
	if userID == "" {
		userID = "anonymous"
	}

	department := q.Get("department")
	role := q.Get("role")

	// Build the LaunchDarkly context for this clinician. The "department"
	// attribute is what the targeting rule matches on; "role" rides along for
	// display and so you could target on it later with no code change.
	ctx := ldcontext.NewBuilder(userID).
		Name(q.Get("name")).
		SetString("department", department).
		SetString("role", role).
		Build()

	// BoolVariationDetail returns the value AND the reason LD used to decide it.
	// This is what lets us show "RULE_MATCH" vs "TARGET_MATCH" vs "FALLTHROUGH"
	// in the targeting demo.
	//
	// Replace "helix-maternity-pathway" with your flag key if you rename it.
	enabled, detail, err := ldClient.BoolVariationDetail("helix-maternity-pathway", ctx, false)
	if err != nil {
		http.Error(w, fmt.Sprintf("flag evaluation error: %v", err), http.StatusInternalServerError)
		return
	}

	// detail.Reason is a value type (ldreason.EvaluationReason). Its zero value
	// has an empty kind; GetKind() yields TARGET_MATCH / RULE_MATCH / FALLTHROUGH / OFF.
	reason := string(detail.Reason.GetKind())
	if reason == "" {
		reason = "UNKNOWN"
	}

	resp := FeatureResponse{
		UserID:  userID,
		Flag:    "helix-maternity-pathway",
		Enabled: enabled,
		Reason:  reason,
		Context: map[string]string{
			"department": department,
			"role":       role,
		},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

// GET /health
func healthHandler(w http.ResponseWriter, r *http.Request) {
	status := "ok"
	if !ldClient.Initialized() {
		status = "sdk_not_ready"
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": status})
}

func main() {
	// Load .env from parent directory (project root)
	if err := godotenv.Load("../.env"); err != nil {
		log.Println("No .env file found, expecting environment variables to be set")
	}

	sdkKey := os.Getenv("LD_SERVER_SDK_KEY")
	if sdkKey == "" {
		log.Fatal("LD_SERVER_SDK_KEY is not set. Add it to ../.env or export it.")
	}

	var err error
	// MakeClient blocks up to 5 seconds while the SDK fetches flag data from LD.
	ldClient, err = ld.MakeClient(sdkKey, 5*time.Second)
	if err != nil {
		log.Fatalf("LaunchDarkly client failed to initialise: %v", err)
	}
	defer ldClient.Close()

	log.Println("LaunchDarkly Go SDK initialised successfully")

	// Flag change listener: fires whenever ANY flag changes in this environment.
	// In the demo: toggle helix-maternity-pathway in the LD dashboard and watch
	// this log line appear instantly, before any API call is made.
	flagCh := ldClient.GetFlagTracker().AddFlagChangeListener()
	go func() {
		for event := range flagCh {
			log.Printf("[LD] Flag changed: %s, all subsequent evaluations will use the new value\n", event.Key)
		}
	}()

	http.HandleFunc("/feature", cors(featureHandler))
	http.HandleFunc("/health", cors(healthHandler))

	log.Println("Go service listening on :8001")
	log.Fatal(http.ListenAndServe(":8001", nil))
}
