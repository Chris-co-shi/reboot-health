package com.indigobyte.reboothealth.common;

import java.time.Instant;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/system")
public class SystemInfoController {

    @GetMapping("/info")
    public Map<String, Object> info() {
        return Map.of(
                "name", "reboot-health",
                "stage", "M1-skeleton",
                "businessReady", false,
                "timestamp", Instant.now().toString()
        );
    }
}
