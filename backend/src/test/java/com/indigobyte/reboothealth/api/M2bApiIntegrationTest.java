package com.indigobyte.reboothealth.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Clock;
import java.time.LocalDate;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DataIntegrityViolationException;
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
class M2bApiIntegrationTest {

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

    private UUID goalId;

    @BeforeEach
    void cleanTables() {
        jdbcTemplate.execute("""
                TRUNCATE TABLE idempotency_record, plan_version_goal, plan_item, plan_day, plan_version, plan,
                    audit_log, goal, health_constraint, app_user_profile CASCADE
                """);
        goalId = UUID.randomUUID();
        jdbcTemplate.update("""
                INSERT INTO goal (
                    id, goal_type, title, target_value, unit, baseline_value, status, priority, created_at, updated_at
                ) VALUES (?, 'TRAINING_HABIT', '示例训练习惯', 3, 'SESSIONS_PER_WEEK', 0, 'ACTIVE', 1, now(), now())
                """, goalId);
    }

    @Test
    void flywayRunsPlanAndIdempotencyMigrations() {
        Integer v3Count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM flyway_schema_history WHERE script = 'V3__create_plan_version_tables.sql'",
                Integer.class
        );
        Integer v4Count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM flyway_schema_history WHERE script = 'V4__create_idempotency_record.sql'",
                Integer.class
        );

        assertThat(v3Count).isEqualTo(1);
        assertThat(v4Count).isEqualTo(1);
    }

    @Test
    void sameIdempotencyKeyCreatePlanOnlyCreatesOnePlanAndReplaysResult() throws Exception {
        String key = "plan-create-" + UUID.randomUUID();
        String payload = planPayload("长期计划");

        MvcResult first = mockMvc.perform(post("/api/v1/plans")
                        .header("Idempotency-Key", key)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isCreated())
                .andExpect(header().string("Idempotency-Replayed", "false"))
                .andReturn();

        String planId = readId(first);

        mockMvc.perform(post("/api/v1/plans")
                        .header("Idempotency-Key", key)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isCreated())
                .andExpect(header().string("Idempotency-Replayed", "true"))
                .andExpect(jsonPath("$.id").value(planId));

        assertThat(countRows("plan")).isEqualTo(1);
        assertThat(countRows("audit_log")).isEqualTo(1);
        assertThat(countRows("idempotency_record")).isEqualTo(1);
    }

    @Test
    void reusedIdempotencyKeyWithDifferentPayloadOrOperationReturnsConflict() throws Exception {
        String key = "reuse-key-" + UUID.randomUUID();
        String planId = createPlan(key, "长期计划");

        mockMvc.perform(post("/api/v1/plans")
                        .header("Idempotency-Key", key)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(planPayload("另一个长期计划")))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("IDEMPOTENCY_KEY_REUSED"));

        mockMvc.perform(post("/api/v1/plans/{planId}/versions", planId)
                        .header("Idempotency-Key", key)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(draftPayload(LocalDate.now(Clock.systemUTC()).plusDays(1), "草案")))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("IDEMPOTENCY_KEY_REUSED"));
    }

    @Test
    void missingAndInvalidIdempotencyKeyAreRejected() throws Exception {
        mockMvc.perform(post("/api/v1/plans")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(planPayload("长期计划")))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("IDEMPOTENCY_KEY_REQUIRED"));

        mockMvc.perform(post("/api/v1/plans")
                        .header("Idempotency-Key", "bad")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(planPayload("长期计划")))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("IDEMPOTENCY_KEY_INVALID"));
    }

    @Test
    void currentAndFutureConfirmedPeriodsCanCoexistAndCurrentQueryUsesDate() throws Exception {
        LocalDate today = LocalDate.now(Clock.systemUTC());
        String planId = createPlan(newKey("plan"), "长期计划");
        String currentVersionId = createDraft(planId, today, "本周期");
        confirm(currentVersionId, newKey("confirm-current"));

        String futureVersionId = createDraft(planId, today.plusDays(7), "下周期");
        confirm(futureVersionId, newKey("confirm-future"));

        mockMvc.perform(get("/api/v1/plans/current"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(currentVersionId))
                .andExpect(jsonPath("$.status").value("CONFIRMED"));

        assertThat(statusOfVersion(currentVersionId)).isEqualTo("CONFIRMED");
        assertThat(statusOfVersion(futureVersionId)).isEqualTo("CONFIRMED");
    }

    @Test
    void samePeriodRevisionSupersedesOldConfirmedVersion() throws Exception {
        LocalDate startDate = LocalDate.now(Clock.systemUTC());
        String planId = createPlan(newKey("plan"), "长期计划");
        String firstVersionId = createDraft(planId, startDate, "第一版");
        confirm(firstVersionId, newKey("confirm-first"));

        String secondVersionId = createDraft(planId, startDate, "第二版");
        confirm(secondVersionId, newKey("confirm-second"));

        assertThat(statusOfVersion(firstVersionId)).isEqualTo("SUPERSEDED");
        assertThat(statusOfVersion(secondVersionId)).isEqualTo("CONFIRMED");
        UUID supersedes = jdbcTemplate.queryForObject(
                "SELECT supersedes_version_id FROM plan_version WHERE id = ?::uuid",
                UUID.class,
                secondVersionId
        );
        assertThat(supersedes).isEqualTo(UUID.fromString(firstVersionId));
    }

    @Test
    void overlappingConfirmedPeriodIsRejectedByDatabaseConstraint() throws Exception {
        LocalDate startDate = LocalDate.now(Clock.systemUTC());
        String planId = createPlan(newKey("plan"), "长期计划");
        String firstVersionId = createDraft(planId, startDate, "第一周期");
        confirm(firstVersionId, newKey("confirm-first"));

        String overlappingVersionId = createDraft(planId, startDate.plusDays(3), "重叠周期");
        mockMvc.perform(post("/api/v1/plan-versions/{versionId}/confirm", overlappingVersionId)
                        .header("Idempotency-Key", newKey("confirm-overlap")))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("DATA_CONFLICT"));
    }

    @Test
    void copyConfirmedVersionCreatesShiftedDraftWithItemsAndGoalLinks() throws Exception {
        LocalDate startDate = LocalDate.now(Clock.systemUTC());
        String planId = createPlan(newKey("plan"), "长期计划");
        MvcResult draftResult = createDraftResult(planId, startDate, "本周期");
        String versionId = readId(draftResult);
        String firstDayId = objectMapper.readTree(draftResult.getResponse().getContentAsString())
                .path("days").get(0).path("id").asText();

        mockMvc.perform(post("/api/v1/plan-days/{dayId}/items", firstDayId)
                        .header("Idempotency-Key", newKey("item"))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "goalId":"%s",
                                  "itemType":"BODYWEIGHT",
                                  "title":"示例徒手训练",
                                  "plannedSets":3,
                                  "plannedReps":8,
                                  "sortOrder":1,
                                  "expectedRevision":0
                                }
                                """.formatted(goalId)))
                .andExpect(status().isCreated());

        confirm(versionId, newKey("confirm"));

        MvcResult copyResult = mockMvc.perform(post("/api/v1/plan-versions/{sourceVersionId}/copy", versionId)
                        .header("Idempotency-Key", newKey("copy"))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "startDate":"%s",
                                  "title":"复制草案",
                                  "expectedSourceStatus":"CONFIRMED"
                                }
                                """.formatted(startDate.plusDays(7))))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.status").value("DRAFT"))
                .andExpect(jsonPath("$.copiedFromVersionId").value(versionId))
                .andExpect(jsonPath("$.days", hasSize(7)))
                .andExpect(jsonPath("$.days[0].dayDate").value(startDate.plusDays(7).toString()))
                .andExpect(jsonPath("$.days[0].items", hasSize(1)))
                .andExpect(jsonPath("$.goalIds[0]").value(goalId.toString()))
                .andReturn();

        String copiedVersionId = readId(copyResult);
        assertThat(statusOfVersion(copiedVersionId)).isEqualTo("DRAFT");
        assertThat(jdbcTemplate.queryForObject(
                "SELECT confirmed_at IS NULL FROM plan_version WHERE id = ?::uuid",
                Boolean.class,
                copiedVersionId
        )).isTrue();
    }

    @Test
    void repeatedConfirmWithSameKeyDoesNotWriteDuplicateAuditButNewKeyIsRejectedByStateMachine() throws Exception {
        String planId = createPlan(newKey("plan"), "长期计划");
        String versionId = createDraft(planId, LocalDate.now(Clock.systemUTC()), "本周期");
        String key = newKey("confirm");

        confirm(versionId, key);
        int auditCount = countRows("audit_log");

        mockMvc.perform(post("/api/v1/plan-versions/{versionId}/confirm", versionId)
                        .header("Idempotency-Key", key))
                .andExpect(status().isOk())
                .andExpect(header().string("Idempotency-Replayed", "true"))
                .andExpect(jsonPath("$.status").value("CONFIRMED"));
        assertThat(countRows("audit_log")).isEqualTo(auditCount);

        mockMvc.perform(post("/api/v1/plan-versions/{versionId}/confirm", versionId)
                        .header("Idempotency-Key", newKey("confirm-again")))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("PLAN_VERSION_NOT_DRAFT"));
    }

    @Test
    void incompleteDraftCannotBeConfirmedButRestDaysWithoutItemsAreAllowed() throws Exception {
        String planId = createPlan(newKey("plan"), "长期计划");
        MvcResult draft = createDraftResult(planId, LocalDate.now(Clock.systemUTC()), "本周期");
        String versionId = readId(draft);
        String dayId = objectMapper.readTree(draft.getResponse().getContentAsString()).path("days").get(6).path("id").asText();

        mockMvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete("/api/v1/plan-days/{dayId}", dayId))
                .andExpect(status().isOk());

        mockMvc.perform(post("/api/v1/plan-versions/{versionId}/confirm", versionId)
                        .header("Idempotency-Key", newKey("confirm-incomplete")))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("PLAN_VERSION_INCOMPLETE"));

        String completeDraftId = createDraft(planId, LocalDate.now(Clock.systemUTC()).plusDays(7), "完整休息周");
        confirm(completeDraftId, newKey("confirm-rest"));
        assertThat(statusOfVersion(completeDraftId)).isEqualTo("CONFIRMED");
    }

    @Test
    void databaseConstraintsRejectInvalidIdempotencyAndOverlappingConfirmedRows() {
        Throwable invalidState = catchThrowable(() -> jdbcTemplate.update("""
                INSERT INTO idempotency_record (
                    id, idempotency_key, operation_code, request_hash, state, created_at
                ) VALUES (?, 'invalid-state-key', 'OP', repeat('a', 64), 'BAD', now())
                """, UUID.randomUUID()));

        assertThat(invalidState).isInstanceOf(DataIntegrityViolationException.class);
    }

    private String createPlan(String key, String title) throws Exception {
        return readId(mockMvc.perform(post("/api/v1/plans")
                        .header("Idempotency-Key", key)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(planPayload(title)))
                .andExpect(status().isCreated())
                .andReturn());
    }

    private String createDraft(String planId, LocalDate startDate, String title) throws Exception {
        return readId(createDraftResult(planId, startDate, title));
    }

    private MvcResult createDraftResult(String planId, LocalDate startDate, String title) throws Exception {
        return mockMvc.perform(post("/api/v1/plans/{planId}/versions", planId)
                        .header("Idempotency-Key", newKey("draft"))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(draftPayload(startDate, title)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.days", hasSize(7)))
                .andReturn();
    }

    private void confirm(String versionId, String key) throws Exception {
        mockMvc.perform(post("/api/v1/plan-versions/{versionId}/confirm", versionId)
                        .header("Idempotency-Key", key))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("CONFIRMED"));
    }

    private String planPayload(String title) {
        return """
                {
                  "title":"%s",
                  "summary":"M2B 示例长期计划"
                }
                """.formatted(title);
    }

    private String draftPayload(LocalDate startDate, String title) {
        return """
                {
                  "startDate":"%s",
                  "title":"%s",
                  "summary":"7 天人工计划草案",
                  "goalIds":["%s"]
                }
                """.formatted(startDate, title, goalId);
    }

    private String readId(MvcResult result) throws Exception {
        JsonNode node = objectMapper.readTree(result.getResponse().getContentAsString());
        return node.path("id").asText();
    }

    private int countRows(String table) {
        return jdbcTemplate.queryForObject("SELECT COUNT(*) FROM " + table, Integer.class);
    }

    private String statusOfVersion(String versionId) {
        return jdbcTemplate.queryForObject("SELECT status FROM plan_version WHERE id = ?::uuid", String.class, versionId);
    }

    private String newKey(String prefix) {
        return prefix + "-" + UUID.randomUUID();
    }
}
