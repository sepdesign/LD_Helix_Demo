package com.helixhealth;

import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.server.LDClient;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * REST endpoints demonstrating LaunchDarkly with the Java server SDK:
 *
 *   GET  /lab-check?value=<systolic BP>
 *        Part 3: reads helix-bp-alert-threshold (a NUMBER flag) and decides
 *        whether a blood-pressure reading should raise an alert. The alert
 *        logic lives in this code; the threshold it compares against is owned
 *        in the LaunchDarkly dashboard, so the clinical team can re-tune it
 *        with no redeploy. Flags aren't only on/off switches - they can carry
 *        configuration values your code reads at runtime.
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
     * GET /lab-check?value=<systolic blood pressure reading, in mmHg>
     *
     * A developer built this blood-pressure alert, but the threshold it fires at
     * is not hard-coded. It's a LaunchDarkly Number flag, helix-bp-alert-threshold
     * (default 140 mmHg, the usual preeclampsia screening cut-off), and the
     * clinical team owns that number in the dashboard. Because the SDK reads it at
     * request time, changing the flag re-tunes this endpoint's behaviour instantly,
     * with no redeploy.
     */
    @GetMapping("/lab-check")
    public Map<String, Object> labCheck(@RequestParam(defaultValue = "0") int value) {
        LDContext ctx = LDContext.builder("helix-clinical-platform")
                .name("Helix Clinical Platform")
                .build();

        // intVariation reads the current value of the Number flag. The default,
        // 140, is used if the flag is missing or LaunchDarkly is unreachable.
        int threshold = ldClient.intVariation("helix-bp-alert-threshold", ctx, 140);
        boolean alert = value >= threshold;

        return Map.of(
                "flag", "helix-bp-alert-threshold",
                "value", value,
                "threshold", threshold,
                "alert", alert
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
