package com.helixhealth;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Helix Health Group: Java Clinical Service
 *
 * Part 3 of the demo: configuration as a flag. A developer built a blood-pressure
 * alert (GET /lab-check); the threshold it fires at is a LaunchDarkly Number flag,
 * helix-bp-alert-threshold, that the clinical team owns in the dashboard. The Java
 * SDK reads the flag at request time, so changing the number re-tunes the alert
 * instantly, with no redeploy - flags aren't just on/off switches.
 *
 * Run:
 *   mvn spring-boot:run
 *   (requires Maven 3.6+ and Java 17+)
 */
@SpringBootApplication
public class HelixApplication {
    public static void main(String[] args) {
        SpringApplication.run(HelixApplication.class, args);
    }
}
