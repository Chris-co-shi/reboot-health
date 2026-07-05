package com.indigobyte.reboothealth;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.mybatis.spring.annotation.MapperScan;

@SpringBootApplication
@MapperScan({
        "com.indigobyte.reboothealth.audit.adapter",
        "com.indigobyte.reboothealth.goal.adapter.persistence",
        "com.indigobyte.reboothealth.idempotency.adapter.persistence",
        "com.indigobyte.reboothealth.plan.adapter.persistence",
        "com.indigobyte.reboothealth.profile.adapter.persistence"
})
public class RebootHealthApplication {

    public static void main(String[] args) {
        SpringApplication.run(RebootHealthApplication.class, args);
    }
}
