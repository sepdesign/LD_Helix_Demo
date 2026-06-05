package com.helixhealth;

import com.launchdarkly.sdk.server.LDClient;
import com.launchdarkly.sdk.server.LDConfig;
import io.github.cdimascio.dotenv.Dotenv;
import jakarta.annotation.PreDestroy;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Initialises and exposes the LaunchDarkly Java SDK client as a Spring bean.
 *
 * The SDK key is loaded from ../.env (project root) via dotenv-java.
 * Replace "LD_SERVER_SDK_KEY" with your Test environment server-side SDK key
 * if you are not using the .env file — or export the environment variable
 * before running: export LD_SERVER_SDK_KEY=sdk-...
 */
@Configuration
public class LdConfig {

    private LDClient ldClient;

    @Bean
    public LDClient ldClient() {
        // Load .env from the project root (one level up from java-service/)
        Dotenv dotenv = Dotenv.configure()
                .directory("../")
                .ignoreIfMissing()
                .load();

        String sdkKey = dotenv.get("LD_SERVER_SDK_KEY",
                System.getenv("LD_SERVER_SDK_KEY"));

        if (sdkKey == null || sdkKey.isBlank()) {
            throw new IllegalStateException(
                "LD_SERVER_SDK_KEY is not set. Add it to ../.env or export it as an environment variable.");
        }

        LDConfig config = new LDConfig.Builder().build();
        ldClient = new LDClient(sdkKey, config);
        return ldClient;
    }

    @PreDestroy
    public void shutdown() throws Exception {
        if (ldClient != null) {
            ldClient.close();
        }
    }
}
