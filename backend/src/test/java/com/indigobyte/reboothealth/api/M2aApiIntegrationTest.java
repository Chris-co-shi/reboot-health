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
        jdbcTemplate.execute("TRUNCATE TABLE audit_log, goal, health_constraint, app_user_profile CASCADE");
    }

    @Test
    void flywayRunsM2aMigrationOnPostgreSql() {
        Integer v1Count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM flyway_schema_history WHERE script = 'V1__m2a_profile_constraints_goals.sql'",
                Integer.class
        );
        Integer v2Count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM flyway_schema_history WHERE script = 'V2__strengthen_m2a_constraints.sql'",
                Integer.class
        );

        assertThat(v1Count).isEqualTo(1);
        assertThat(v2Count).isEqualTo(1);
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
                .andExpect(jsonPath("$.displayName").value("测试用户A"))
                .andExpect(jsonPath("$.baselineWeightKg").value(72.5));

        assertThat(countRows("app_user_profile")).isEqualTo(1);
        assertThat(countRows("audit_log")).isEqualTo(1);

        mockMvc.perform(put("/api/v1/profile")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(profilePayload()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.displayName").value("测试用户A"));

        String storedSex = jdbcTemplate.queryForObject("SELECT sex FROM app_user_profile", String.class);
        assertThat(storedSex).isEqualTo("UNSPECIFIED");
        String auditDisplayName = jdbcTemplate.queryForObject(
                "SELECT after_snapshot ->> 'displayName' FROM audit_log WHERE action = 'PROFILE_CREATED'",
                String.class
        );
        assertThat(auditDisplayName).isEqualTo("测试用户A");

        assertThat(countRows("app_user_profile")).isEqualTo(1);
        assertThat(countRows("audit_log")).isEqualTo(1);
    }

    @Test
    void healthConstraintLifecycleRejectsArchivedUpdatesAndHidesArchivedByDefault() throws Exception {
        MvcResult createResult = mockMvc.perform(post("/api/v1/health-constraints")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(healthConstraintPayload("示例训练注意")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ACTIVE"))
                .andReturn();
        String id = readId(createResult);

        mockMvc.perform(put("/api/v1/health-constraints/{id}", id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(healthConstraintPayload("示例训练注意已更新")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.title").value("示例训练注意已更新"));

        mockMvc.perform(patch("/api/v1/health-constraints/{id}/status", id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"status":"INACTIVE"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("INACTIVE"));

        int auditBeforeRejectedArchiveStatus = countRows("audit_log");
        mockMvc.perform(patch("/api/v1/health-constraints/{id}/status", id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"status":"ARCHIVED"}
                                """))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("HEALTH_CONSTRAINT_INVALID_STATUS_TRANSITION"));
        assertThat(countRows("audit_log")).isEqualTo(auditBeforeRejectedArchiveStatus);
        assertThat(statusOf("health_constraint", id)).isEqualTo("INACTIVE");

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
                        .content(healthConstraintPayload("归档后更新")))
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
                                  "targetValue":60,
                                  "unit":"CM",
                                  "baselineValue":72,
                                  "priority":1
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("GOAL_INVALID_TARGET"));

        MvcResult createResult = mockMvc.perform(post("/api/v1/goals")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(goalPayload("示例体重目标")))
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

        int auditBeforeRejectedArchiveStatus = countRows("audit_log");
        mockMvc.perform(patch("/api/v1/goals/{id}/status", id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"status":"ARCHIVED"}
                                """))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("GOAL_INVALID_STATUS_TRANSITION"));
        assertThat(countRows("audit_log")).isEqualTo(auditBeforeRejectedArchiveStatus);
        assertThat(statusOf("goal", id)).isEqualTo("PAUSED");

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
    void completedGoalCannotBeEditedButCanBeArchived() throws Exception {
        MvcResult createResult = mockMvc.perform(post("/api/v1/goals")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(goalPayload("示例习惯目标")))
                .andExpect(status().isOk())
                .andReturn();
        String id = readId(createResult);

        mockMvc.perform(patch("/api/v1/goals/{id}/status", id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"status":"COMPLETED"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("COMPLETED"));

        int auditBeforeRejectedUpdate = countRows("audit_log");
        mockMvc.perform(put("/api/v1/goals/{id}", id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(goalPayload("终态后修改")))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("GOAL_INVALID_STATUS_TRANSITION"));
        assertThat(countRows("audit_log")).isEqualTo(auditBeforeRejectedUpdate);
        assertThat(statusOf("goal", id)).isEqualTo("COMPLETED");

        mockMvc.perform(post("/api/v1/goals/{id}/archive", id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"archiveReason":"终态后隐藏"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ARCHIVED"));
    }

    @Test
    void databaseConstraintsRejectInvalidArchiveFieldsAndGoalValues() {
        assertThat(org.assertj.core.api.Assertions.catchThrowable(() -> jdbcTemplate.update("""
                INSERT INTO health_constraint (
                    id, constraint_type, body_region, severity, title,
                    source_type, status, created_at, updated_at
                ) VALUES (
                    ?, 'TRAINING_PRECAUTION', 'FULL_BODY', 'LOW', '示例',
                    'USER_REPORTED', 'ARCHIVED', now(), now()
                )
                """, UUID.randomUUID()))).hasMessageContaining("ck_health_constraint_archive_fields");

        assertThat(org.assertj.core.api.Assertions.catchThrowable(() -> jdbcTemplate.update("""
                INSERT INTO goal (
                    id, goal_type, title, unit, status, priority,
                    created_at, updated_at
                ) VALUES (
                    ?, 'OTHER', '示例', 'NONE', 'ACTIVE', 6,
                    now(), now()
                )
                """, UUID.randomUUID()))).hasMessageContaining("ck_goal_priority_range");
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
                                  "title":"示例约束",
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

    private String statusOf(String tableName, String id) {
        return jdbcTemplate.queryForObject("SELECT status FROM " + tableName + " WHERE id = ?::uuid", String.class, id);
    }

    private String profilePayload() {
        return """
                {
                  "displayName":"测试用户A",
                  "sex":"UNSPECIFIED",
                  "birthDate":"1990-03-15",
                  "heightCm":168,
                  "baselineWeightKg":72.5,
                  "timezone":"Asia/Shanghai"
                }
                """;
    }

    private String healthConstraintPayload(String title) {
        return """
                {
                  "constraintType":"TRAINING_PRECAUTION",
                  "bodyRegion":"FULL_BODY",
                  "severity":"MEDIUM",
                  "title":"%s",
                  "description":"示例描述：根据主观状态调整训练安排。",
                  "sourceType":"USER_REPORTED",
                  "sourceNote":"测试录入",
                  "effectiveFrom":"2026-07-01"
                }
                """.formatted(title);
    }

    private String goalPayload(String title) {
        return """
                {
                  "goalType":"WEIGHT",
                  "title":"%s",
                  "targetValue":60,
                  "unit":"KG",
                  "baselineValue":72,
                  "targetDate":"2026-12-31",
                  "priority":1
                }
                """.formatted(title);
    }
}
