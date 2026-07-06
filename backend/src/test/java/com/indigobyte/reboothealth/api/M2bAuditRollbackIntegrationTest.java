package com.indigobyte.reboothealth.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.reset;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.indigobyte.reboothealth.audit.domain.AuditLog;
import com.indigobyte.reboothealth.audit.domain.AuditLogRepository;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@Testcontainers
@AutoConfigureMockMvc
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = "app.device.auth.enabled=false")
class M2bAuditRollbackIntegrationTest {

    @Container
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:17-alpine");

    @DynamicPropertySource
    static void configureDatasource(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
    }

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @MockitoBean
    private AuditLogRepository auditLogRepository;

    @Test
    void idempotencyRecordAndBusinessRollbackWhenAuditFails() throws Exception {
        doThrow(new RuntimeException("audit failed")).when(auditLogRepository).append(any(AuditLog.class));

        mockMvc.perform(post("/api/v1/plans")
                        .header("Idempotency-Key", "rollback-" + UUID.randomUUID())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "title":"回滚示例计划",
                                  "summary":"审计失败时整体回滚"
                                }
                                """))
                .andExpect(status().isInternalServerError())
                .andExpect(jsonPath("$.code").value("INTERNAL_ERROR"));

        assertThat(countRows("plan")).isZero();
        assertThat(countRows("idempotency_record")).isZero();
    }

    @Test
    void sameIdempotencyKeyCanRetryAfterServerFailureRollback() throws Exception {
        String key = "retry-after-500-" + UUID.randomUUID();
        String payload = """
                {
                  "title":"500 后重试计划",
                  "summary":"第一次失败后复用同一个 key"
                }
                """;
        doThrow(new RuntimeException("audit failed once")).when(auditLogRepository).append(any(AuditLog.class));

        mockMvc.perform(post("/api/v1/plans")
                        .header("Idempotency-Key", key)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isInternalServerError())
                .andExpect(jsonPath("$.code").value("INTERNAL_ERROR"));

        reset(auditLogRepository);

        mockMvc.perform(post("/api/v1/plans")
                        .header("Idempotency-Key", key)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isCreated());

        assertThat(countRows("plan")).isEqualTo(1);
        assertThat(countRows("idempotency_record")).isEqualTo(1);
    }

    private int countRows(String table) {
        return jdbcTemplate.queryForObject("SELECT COUNT(*) FROM " + table, Integer.class);
    }
}
