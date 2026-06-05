package com.helixhealth;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Helix Health Group — Java Clinical Analytics Service
 *
 * Covers:
 *   Part 2  — Multi-context flag evaluation (user context + organisation context)
 *   Extra   — Custom metric event tracking for LaunchDarkly Experimentation
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
