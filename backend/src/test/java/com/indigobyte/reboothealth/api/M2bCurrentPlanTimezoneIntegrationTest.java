package com.indigobyte.reboothealth.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
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
import org.springframework.test.web.servlet.MvcResult;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

/**
 * 当前计划日期的时区集成测试。
 */
@Testcontainers
@AutoConfigureMockMvc
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class M2bCurrentPlanTimezoneIntegrationTest {

    @Container
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:17-alpine");

    @DynamicPropertySource
    static void configureDatasource(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
        registry.add("app.default-timezone", () -> "Asia/Shanghai");
    }

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @MockitoBean
    private Clock clock;

    private UUID goalId;

    @BeforeEach
    void setUp() {
        when(clock.instant()).thenReturn(Instant.parse("2026-07-05T16:30:00Z"));
        when(clock.getZone()).thenReturn(ZoneOffset.UTC);
        jdbcTemplate.execute("""
                TRUNCATE TABLE idempotency_record, plan_version_goal, plan_item, plan_day, plan_version, plan,
                    audit_log, goal, health_constraint, app_user_profile CASCADE
                """);
        goalId = UUID.randomUUID();
        jdbcTemplate.update("""
                INSERT INTO goal (
                    id, goal_type, title, target_value, unit, baseline_value, status, priority, created_at, updated_at
                ) VALUES (?, 'TRAINING_HABIT', '跨日目标', 3, 'SESSIONS_PER_WEEK', 0, 'ACTIVE', 1, now(), now())
                """, goalId);
    }

    @Test
    void currentPlanUsesUserProfileTimezoneAcrossUtcDayBoundary() throws Exception {
        insertProfile("Asia/Tokyo");
        String versionId = createConfirmedVersion(LocalDate.of(2026, 7, 6));

        mockMvc.perform(get("/api/v1/plans/current"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(versionId));
    }

    @Test
    void currentPlanUsesConfiguredDefaultTimezoneWhenProfileMissing() throws Exception {
        String versionId = createConfirmedVersion(LocalDate.of(2026, 7, 6));

        mockMvc.perform(get("/api/v1/plans/current"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(versionId));
    }

    private String createConfirmedVersion(LocalDate startDate) throws Exception {
        String planId = readId(mockMvc.perform(post("/api/v1/plans")
                        .header("Idempotency-Key", "plan-" + UUID.randomUUID())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "title":"跨日计划",
                                  "summary":"测试计划"
                                }
                                """))
                .andExpect(status().isCreated())
                .andReturn());
        MvcResult draft = mockMvc.perform(post("/api/v1/plans/{planId}/versions", planId)
                        .header("Idempotency-Key", "draft-" + UUID.randomUUID())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "startDate":"%s",
                                  "title":"跨日周期",
                                  "summary":"测试周期",
                                  "goalIds":["%s"]
                                }
                                """.formatted(startDate, goalId)))
                .andExpect(status().isCreated())
                .andReturn();
        String versionId = readId(draft);
        mockMvc.perform(post("/api/v1/plan-versions/{versionId}/confirm", versionId)
                        .header("Idempotency-Key", "confirm-" + UUID.randomUUID())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "expectedRevision":0
                                }
                                """))
                .andExpect(status().isOk());
        return versionId;
    }

    private void insertProfile(String timezone) {
        jdbcTemplate.update("""
                INSERT INTO app_user_profile (
                    id, display_name, sex, birth_date, height_cm, baseline_weight_kg, timezone, created_at, updated_at
                ) VALUES (?, 'Timezone Tester', 'MALE', DATE '1990-01-01', 180.00, 70.00, ?, now(), now())
                """, UUID.randomUUID(), timezone);
    }

    private String readId(MvcResult result) throws Exception {
        JsonNode node = objectMapper.readTree(result.getResponse().getContentAsString());
        return node.path("id").asText();
    }
}
