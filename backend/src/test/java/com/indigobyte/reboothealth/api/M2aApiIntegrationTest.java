package com.indigobyte.reboothealth.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@Testcontainers
@AutoConfigureMockMvc
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class M2aApiIntegrationTest {

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
    private ObjectMapper objectMapper;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @BeforeEach
    void cleanTables() {
        jdbcTemplate.execute("TRUNCATE TABLE audit_log, goal, health_constraint, app_user_profile");
    }

    @Test
    void flywayRunsM2aMigrationOnPostgreSql() {
        Integer migrationCount = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM flyway_schema_history WHERE script = 'V1__m2a_profile_constraints_goals.sql'",
                Integer.class
        );

        assertThat(migrationCount).isEqualTo(1);
    }

    @Test
    void getProfileBeforeInitializationReturnsNotFound() throws Exception {
        mockMvc.perform(get("/api/v1/profile"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("PROFILE_NOT_INITIALIZED"));
    }

    @Test
    void putProfileCreatesAndIdempotentUpdateDoesNotWriteNoChangeAudit() throws Exception {
        mockMvc.perform(put("/api/v1/profile")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(profilePayload()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.displayName").value("sxc"))
                .andExpect(jsonPath("$.baselineWeightKg").value(94.0));

        assertThat(countRows("app_user_profile")).isEqualTo(1);
        assertThat(countRows("audit_log")).isEqualTo(1);

        mockMvc.perform(put("/api/v1/profile")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(profilePayload()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.displayName").value("sxc"));

        assertThat(countRows("app_user_profile")).isEqualTo(1);
        assertThat(countRows("audit_log")).isEqualTo(1);
    }

    @Test
    void healthConstraintLifecycleRejectsArchivedUpdatesAndHidesArchivedByDefault() throws Exception {
        MvcResult createResult = mockMvc.perform(post("/api/v1/health-constraints")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(healthConstraintPayload("高血压", "ACTIVE")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ACTIVE"))
                .andReturn();
        String id = readId(createResult);

        mockMvc.perform(put("/api/v1/health-constraints/{id}", id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(healthConstraintPayload("高血压训练注意", "ACTIVE")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.title").value("高血压训练注意"));

        mockMvc.perform(patch("/api/v1/health-constraints/{id}/status", id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"status":"INACTIVE"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("INACTIVE"));

        mockMvc.perform(post("/api/v1/health-constraints/{id}/archive", id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"archiveReason":"录入重复，保留历史"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ARCHIVED"))
                .andExpect(jsonPath("$.archiveReason").value("录入重复，保留历史"));

        mockMvc.perform(put("/api/v1/health-constraints/{id}", id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(healthConstraintPayload("归档后更新", "ACTIVE")))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("HEALTH_CONSTRAINT_ARCHIVED"));

        mockMvc.perform(get("/api/v1/health-constraints"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(0)));

        mockMvc.perform(get("/api/v1/health-constraints").param("includeArchived", "true"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(1)));

        assertThat(countRows("audit_log")).isEqualTo(4);
    }

    @Test
    void goalLifecycleRejectsInvalidTargetAndArchivedUpdates() throws Exception {
        mockMvc.perform(post("/api/v1/goals")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "goalType":"WEIGHT",
                                  "title":"错误单位",
                                  "targetValue":80,
                                  "unit":"CM",
                                  "baselineValue":94,
                                  "priority":1
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("GOAL_INVALID_TARGET"));

        MvcResult createResult = mockMvc.perform(post("/api/v1/goals")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(goalPayload("减重到 80kg")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ACTIVE"))
                .andExpect(jsonPath("$.unit").value("KG"))
                .andReturn();
        String id = readId(createResult);

        mockMvc.perform(put("/api/v1/goals/{id}", id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(goalPayload("阶段减重")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.title").value("阶段减重"));

        mockMvc.perform(patch("/api/v1/goals/{id}/status", id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"status":"PAUSED"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("PAUSED"));

        mockMvc.perform(post("/api/v1/goals/{id}/archive", id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"archiveReason":"目标重新拆分"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ARCHIVED"));

        mockMvc.perform(put("/api/v1/goals/{id}", id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(goalPayload("归档后更新")))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("GOAL_ARCHIVED"));

        assertThat(countRows("audit_log")).isEqualTo(4);
    }

    @Test
    void invalidEnumAndBeanValidationReturnStableErrors() throws Exception {
        mockMvc.perform(post("/api/v1/health-constraints")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "constraintType":"UNKNOWN",
                                  "bodyRegion":"CARDIOVASCULAR",
                                  "severity":"HIGH",
                                  "title":"高血压",
                                  "sourceType":"DOCTOR_ADVICE"
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("ENUM_INVALID"));

        mockMvc.perform(post("/api/v1/goals")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "goalType":"WEIGHT",
                                  "unit":"KG",
                                  "priority":1
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("VALIDATION_ERROR"));
    }

    private String readId(MvcResult result) throws Exception {
        JsonNode body = objectMapper.readTree(result.getResponse().getContentAsString());
        return body.get("id").asText();
    }

    private int countRows(String tableName) {
        Integer count = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM " + tableName, Integer.class);
        return count == null ? 0 : count;
    }

    private String profilePayload() {
        return """
                {
                  "displayName":"sxc",
                  "sex":"MALE",
                  "birthDate":"1992-01-01",
                  "heightCm":175,
                  "baselineWeightKg":94,
                  "timezone":"Asia/Shanghai"
                }
                """;
    }

    private String healthConstraintPayload(String title, String ignoredStatus) {
        return """
                {
                  "constraintType":"HYPERTENSION",
                  "bodyRegion":"CARDIOVASCULAR",
                  "severity":"HIGH",
                  "title":"%s",
                  "description":"按医嘱服用降压药，训练避免激进升级。",
                  "sourceType":"DOCTOR_ADVICE",
                  "sourceNote":"用户录入",
                  "effectiveFrom":"2026-07-01"
                }
                """.formatted(title);
    }

    private String goalPayload(String title) {
        return """
                {
                  "goalType":"WEIGHT",
                  "title":"%s",
                  "targetValue":80,
                  "unit":"KG",
                  "baselineValue":94,
                  "targetDate":"2026-12-31",
                  "priority":1
                }
                """.formatted(title);
    }
}
