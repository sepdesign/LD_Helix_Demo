// Helix Health Group — Patient Access & Targeting Service (Go)
// =============================================================
// Covers:
//   Part 2 — helix-maternity-pathway flag with individual and rule-based targeting
//
// Demonstrates:
//   • ldcontext with rich clinical attributes (department, role, hospitalTier)
//   • BoolVariationDetail — returns the evaluation reason (RULE_MATCH, TARGET_MATCH, etc.)
//   • Flag change listener — logs every flag change to stdout in real time
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
	Reason     string            `json:"reason"`   // e.g. TARGET_MATCH, RULE_MATCH, FALLTHROUGH
	Context    map[string]string `json:"context"`  // attributes used in evaluation
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
// Query params — mirror a clinical provider's identity attributes:
//   userId        string  — provider email / unique key (used for individual targeting)
//   name          string  — display name (cosmetic)
//   department    string  — "maternity" | "ed" | "icu" | "general"
//   role          string  — "attending" | "resident" | "charge_nurse" | "floor_nurse"
//   hospitalTier  string  — "level1" | "level2" | "community"
//   hasBirthCenter bool   — "true" | "false"
//
// LaunchDarkly targeting rules for helix-maternity-pathway:
//   Individual targets : dr.chen@helixhealth.org → true
//                        mary.johnson@helixhealth.org → true
//   Rule 1  : department = "maternity"  AND role = "attending"       → true
//   Rule 2  : department = "maternity"  AND role = "charge_nurse"    → true
//   Rule 3  : hospitalTier = "level1"   AND hasBirthCenter = true    → true
//   Default : false
func featureHandler(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()

	userID := q.Get("userId")
	if userID == "" {
		userID = "anonymous"
	}

	department := q.Get("department")
	role := q.Get("role")
	hospitalTier := q.Get("hospitalTier")
	hasBirthCenter := q.Get("hasBirthCenter") == "true"

	// Build the LaunchDarkly context with clinical attributes.
	// These attributes are what the targeting rules in the LD dashboard match against.
	ctx := ldcontext.NewBuilder(userID).
		Name(q.Get("name")).
		SetString("department", department).
		SetString("role", role).
		SetString("hospitalTier", hospitalTier).
		SetBool("hasBirthCenter", hasBirthCenter).
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

	reason := "UNKNOWN"
	if detail.Reason != nil {
		reason = detail.Reason.String()
	}

	resp := FeatureResponse{
		UserID:  userID,
		Flag:    "helix-maternity-pathway",
		Enabled: enabled,
		Reason:  reason,
		Context: map[string]string{
			"department":     department,
			"role":           role,
			"hospitalTier":   hospitalTier,
			"hasBirthCenter": fmt.Sprintf("%v", hasBirthCenter),
		},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

// GET /health
func healthHandler(w http.ResponseWriter, r *http.Request) {
	status := "ok"
	if !ldClient.IsInitialized() {
		status = "sdk_not_ready"
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": status})
}

func main() {
	// Load .env from parent directory (project root)
	if err := godotenv.Load("../.env"); err != nil {
		log.Println("No .env file found — expecting environment variables to be set")
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

	// Flag change listener — fires whenever ANY flag changes in this environment.
	// In the demo: toggle helix-maternity-pathway in the LD dashboard and watch
	// this log line appear instantly, before any API call is made.
	flagCh := ldClient.GetFlagTracker().AddFlagChangeListener()
	go func() {
		for event := range flagCh {
			log.Printf("[LD] Flag changed: %s — all subsequent evaluations will use the new value\n", event.Key)
		}
	}()

	http.HandleFunc("/feature", cors(featureHandler))
	http.HandleFunc("/health", cors(healthHandler))

	log.Println("Go service listening on :8001")
	log.Fatal(http.ListenAndServe(":8001", nil))
}
