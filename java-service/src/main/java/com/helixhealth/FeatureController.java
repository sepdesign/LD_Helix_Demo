package com.helixhealth;

import com.launchdarkly.sdk.ContextKind;
import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.server.LDClient;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * REST endpoints demonstrating:
 *
 *   GET  /feature/multi-context
 *        Part 2 — Evaluates helix-maternity-pathway against a MULTI-CONTEXT:
 *        both a "user" context (the individual provider) and an "organization"
 *        context (the hospital) are combined.  LD evaluates rules against all
 *        contexts simultaneously — an enterprise plan at the org level can
 *        unlock a feature even if the individual user context alone wouldn't.
 *
 *   POST /track-event
 *        Extra Credit — Tracks a custom conversion event for Experimentation.
 *        Wire the helix-maternity-pathway flag to an LD Experiment and attach
 *        the "maternity-pathway-engaged" metric.  LD will attribute events to
 *        the correct experiment variation automatically.
 *
 *   GET  /health
 *        SDK liveness check.
 */
@RestController
@CrossOrigin(origins = "*")
public class FeatureController {

    private final LDClient ldClient;

    public FeatureController(LDClient ldClient) {
        this.ldClient = ldClient;
    }

    /**
     * GET /feature/multi-context
     *
     * Query params:
     *   userId        — provider key  (e.g. dr.chen@helixhealth.org)
     *   name          — display name
     *   role          — attending | resident | charge_nurse | floor_nurse
     *   department    — maternity | ed | icu | general
     *   orgId         — hospital / organisation key  (e.g. helix-northwest)
     *   orgPlan       — enterprise | standard | community
     *   hasBirthCenter — true | false
     *
     * Multi-context: the same flag evaluation runs against BOTH the user
     * context and the organization context.  Rules that target by org plan
     * can unlock the feature without requiring individual user targeting.
     */
    @GetMapping("/feature/multi-context")
    public Map<String, Object> multiContextFeature(
            @RequestParam(defaultValue = "provider-default") String userId,
            @RequestParam(defaultValue = "") String name,
            @RequestParam(defaultValue = "general") String role,
            @RequestParam(defaultValue = "general") String department,
            @RequestParam(defaultValue = "helix-default") String orgId,
            @RequestParam(defaultValue = "standard") String orgPlan,
            @RequestParam(defaultValue = "false") String hasBirthCenter) {

        // User context — individual provider attributes
        LDContext userCtx = LDContext.builder(ContextKind.of("user"), userId)
                .name(name)
                .set("role", role)
                .set("department", department)
                .build();

        // Organisation context — hospital-level attributes
        // Rules in LD can match on orgPlan="enterprise" here regardless of user
        LDContext orgCtx = LDContext.builder(ContextKind.of("organization"), orgId)
                .set("plan", orgPlan)
                .set("hasBirthCenter", Boolean.parseBoolean(hasBirthCenter))
                .build();

        // Multi-context: LD evaluates targeting rules against BOTH contexts.
        // This is the enterprise pattern — org-level entitlements + user-level targeting.
        LDContext multiCtx = LDContext.createMulti(userCtx, orgCtx);

        boolean enabled = ldClient.boolVariation("helix-maternity-pathway", multiCtx, false);

        return Map.of(
                "flag", "helix-maternity-pathway",
                "enabled", enabled,
                "userContext", Map.of(
                        "key", userId,
                        "role", role,
                        "department", department
                ),
                "orgContext", Map.of(
                        "key", orgId,
                        "plan", orgPlan,
                        "hasBirthCenter", hasBirthCenter
                )
        );
    }

    /**
     * POST /track-event
     *
     * Body (JSON):
     *   userId     — context key
     *   eventName  — custom metric name (must match the metric key in LD Experimentation)
     *   value      — optional numeric value (e.g. time-on-feature in seconds)
     *
     * To use this for Experimentation:
     *   1. Create a metric in LD Experimentation → "maternity-pathway-engaged"
     *   2. Attach it to an experiment on helix-maternity-pathway
     *   3. POST to this endpoint when a provider engages with the feature
     *   4. LD attributes the event to the correct flag variation automatically
     */
    @PostMapping("/track-event")
    public Map<String, Object> trackEvent(@RequestBody Map<String, Object> body) {
        String userId = (String) body.getOrDefault("userId", "anonymous");
        String eventName = (String) body.getOrDefault("eventName", "maternity-pathway-engaged");
        double value = body.containsKey("value")
                ? Double.parseDouble(body.get("value").toString())
                : 1.0;

        LDContext ctx = LDContext.builder(userId).build();

        // Track a custom numeric metric event.
        // Replace "maternity-pathway-engaged" with your metric key from LD Experimentation.
        ldClient.trackMetric(eventName, ctx, value);

        return Map.of(
                "tracked", true,
                "event", eventName,
                "userId", userId,
                "value", value
        );
    }

    /** GET /health */
    @GetMapping("/health")
    public Map<String, Object> health() {
        return Map.of(
                "status", "ok",
                "sdkInitialized", ldClient.isInitialized()
        );
    }
}
