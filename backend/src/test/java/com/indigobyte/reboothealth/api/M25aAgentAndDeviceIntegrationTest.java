package com.indigobyte.reboothealth.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.indigobyte.reboothealth.agent.application.AgentRuntimeClient;
import com.indigobyte.reboothealth.agent.application.AgentRuntimeException;
import com.indigobyte.reboothealth.agent.application.AgentRuntimeResponse;
import com.indigobyte.reboothealth.device.application.DeviceApplicationService;
import com.indigobyte.reboothealth.device.application.DeviceApplicationService.BootstrapCode;
import com.indigobyte.reboothealth.device.application.DeviceApplicationService.BootstrapConsumeCommand;
import com.indigobyte.reboothealth.device.domain.DevicePlatform;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;
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

@Testcontainers
@AutoConfigureMockMvc
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class M25aAgentAndDeviceIntegrationTest {

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

    @Autowired
    private DeviceApplicationService deviceService;

    @MockitoBean
    private AgentRuntimeClient runtimeClient;

    @BeforeEach
    void cleanTables() {
        jdbcTemplate.execute("""
                TRUNCATE TABLE agent_tool_call, agent_run, device_credential, pairing_session,
                    device, bootstrap_session, app_user, idempotency_record,
                    audit_log, plan_version_goal, plan_item, plan_day, plan_version, plan,
                    goal, health_constraint, app_user_profile CASCADE
                """);
    }

    @Test
    void flywayRunsM25aMigration() {
        Integer v6Count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM flyway_schema_history WHERE script = 'V6__create_agent_and_device_tables.sql'",
                Integer.class
        );

        assertThat(v6Count).isEqualTo(1);
    }

    @Test
    void bootstrapCodeIsRequiredAndCanOnlyBeConsumedOnce() throws Exception {
        mockMvc.perform(post("/api/v1/device-bootstrap/consume")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(bootstrapPayload("WRONGCODE")))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("BOOTSTRAP_CODE_INVALID"));
        assertThat(countAuditActions("BOOTSTRAP_CODE_REJECTED")).isEqualTo(1);

        BootstrapCode bootstrapCode = deviceService.createBootstrapCodeForCli();
        MvcResult result = consumeBootstrap(bootstrapCode.code());
        String accessToken = read(result, "accessToken");
        String refreshToken = read(result, "refreshToken");

        assertThat(countRows("app_user")).isEqualTo(1);
        assertThat(countRows("device")).isEqualTo(1);
        assertThat(jdbcTemplate.queryForObject("SELECT trust_level FROM device", String.class))
                .isEqualTo("TRUSTED_PRIMARY");

        mockMvc.perform(post("/api/v1/device-bootstrap/consume")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(bootstrapPayload(bootstrapCode.code())))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("BOOTSTRAP_CODE_INVALID"));
        assertThatThrownBy(() -> deviceService.createBootstrapCodeForCli())
                .hasMessageContaining("首台设备已初始化");

        assertThat(auditSnapshots()).doesNotContain(bootstrapCode.code(), accessToken, refreshToken);
    }

    @Test
    void expiredBootstrapCodeIsRejected() throws Exception {
        BootstrapCode bootstrapCode = deviceService.createBootstrapCodeForCli();
        jdbcTemplate.update("""
                UPDATE bootstrap_session
                SET expires_at = TIMESTAMPTZ '2026-01-01T00:00:00Z'
                WHERE code_hash IS NOT NULL
                """);

        mockMvc.perform(post("/api/v1/device-bootstrap/consume")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(bootstrapPayload(bootstrapCode.code())))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("BOOTSTRAP_CODE_INVALID"));
    }

    @Test
    void repeatedWrongBootstrapCodeRevokesActiveSession() throws Exception {
        BootstrapCode bootstrapCode = deviceService.createBootstrapCodeForCli();
        for (int index = 0; index < 5; index++) {
            mockMvc.perform(post("/api/v1/device-bootstrap/consume")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(bootstrapPayload("WRONG-" + index)))
                    .andExpect(status().isConflict())
                    .andExpect(jsonPath("$.code").value("BOOTSTRAP_CODE_INVALID"));
        }

        assertThat(jdbcTemplate.queryForObject("SELECT status FROM bootstrap_session", String.class))
                .isEqualTo("REVOKED");
        assertThat(jdbcTemplate.queryForObject("SELECT failure_count FROM bootstrap_session", Integer.class))
                .isEqualTo(5);

        mockMvc.perform(post("/api/v1/device-bootstrap/consume")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(bootstrapPayload(bootstrapCode.code())))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("BOOTSTRAP_CODE_INVALID"));
    }

    @Test
    void concurrentBootstrapConsumptionOnlyAllowsOneSuccess() throws Exception {
        BootstrapCode bootstrapCode = deviceService.createBootstrapCodeForCli();
        CountDownLatch start = new CountDownLatch(1);
        AtomicInteger success = new AtomicInteger();
        AtomicInteger failed = new AtomicInteger();
        try (var executor = Executors.newFixedThreadPool(2)) {
            for (int index = 0; index < 2; index++) {
                executor.submit(() -> {
                    try {
                        start.await();
                        deviceService.consumeBootstrap(new BootstrapConsumeCommand(
                                bootstrapCode.code(), "并发测试设备", DevicePlatform.MACOS));
                        success.incrementAndGet();
                    } catch (Exception ex) {
                        failed.incrementAndGet();
                    }
                });
            }
            start.countDown();
        }

        assertThat(success.get()).isEqualTo(1);
        assertThat(failed.get()).isEqualTo(1);
        assertThat(countRows("device")).isEqualTo(1);
    }

    @Test
    void pairingSessionRequiresAuthorizedDeviceAndCanOnlyBeConsumedOnce() throws Exception {
        String accessToken = initializeAndReadAccessToken();

        mockMvc.perform(post("/api/v1/devices/pairing-sessions"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("DEVICE_UNAUTHORIZED"));

        MvcResult pairing = mockMvc.perform(post("/api/v1/devices/pairing-sessions")
                        .header("Authorization", "Bearer " + accessToken))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.pairingCode").isString())
                .andExpect(jsonPath("$.qrPayload").isString())
                .andReturn();

        String pairingCode = read(pairing, "pairingCode");
        MvcResult secondDevice = mockMvc.perform(post("/api/v1/devices/pair")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(pairingPayload(pairingCode)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.accessToken").isString())
                .andReturn();

        mockMvc.perform(post("/api/v1/devices/pair")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(pairingPayload(pairingCode)))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("PAIRING_SESSION_INVALID"));

        assertThat(countRows("device")).isEqualTo(2);

        UUID secondDeviceId = UUID.fromString(read(secondDevice, "deviceId"));
        mockMvc.perform(post("/api/v1/devices/{deviceId}/revoke", secondDeviceId)
                        .header("Authorization", "Bearer " + accessToken))
                .andExpect(status().isNoContent());

        assertThat(jdbcTemplate.queryForObject("SELECT status FROM device WHERE id = ?::uuid", String.class, secondDeviceId))
                .isEqualTo("REVOKED");
        assertThat(jdbcTemplate.queryForObject("SELECT COUNT(*) FROM device WHERE status = 'ACTIVE'", Integer.class))
                .isEqualTo(1);
    }

    @Test
    void agentRunSuccessIsIdempotentAndReplaysWithoutSecondRuntimeCall() throws Exception {
        String accessToken = initializeAndReadAccessToken();
        when(runtimeClient.execute(any())).thenReturn(successRuntimeResponse());
        String key = "agent-run-" + UUID.randomUUID();

        MvcResult first = mockMvc.perform(post("/api/v1/agent-runs")
                        .header("Authorization", "Bearer " + accessToken)
                        .header("Idempotency-Key", key)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(agentRunPayload("success")))
                .andExpect(status().isCreated())
                .andExpect(header().string("Idempotency-Replayed", "false"))
                .andExpect(jsonPath("$.status").value("READY_FOR_USER_REVIEW"))
                .andExpect(jsonPath("$.structuredOutput.cards[0].title").value("AI教练服务已连接"))
                .andReturn();

        String runId = read(first, "id");
        mockMvc.perform(post("/api/v1/agent-runs")
                        .header("Authorization", "Bearer " + accessToken)
                        .header("Idempotency-Key", key)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(agentRunPayload("success")))
                .andExpect(status().isCreated())
                .andExpect(header().string("Idempotency-Replayed", "true"))
                .andExpect(jsonPath("$.id").value(runId));

        verify(runtimeClient, times(1)).execute(any());
        assertThat(countRows("agent_run")).isEqualTo(1);
    }

    @Test
    void agentRunInvalidOutputAndTimeoutBecomeFailedRun() throws Exception {
        String accessToken = initializeAndReadAccessToken();
        when(runtimeClient.execute(any())).thenReturn(new AgentRuntimeResponse("bad", "", List.of()));

        mockMvc.perform(post("/api/v1/agent-runs")
                        .header("Authorization", "Bearer " + accessToken)
                        .header("Idempotency-Key", "agent-invalid-" + UUID.randomUUID())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(agentRunPayload("invalid")))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.status").value("FAILED"))
                .andExpect(jsonPath("$.failureCode").value("AGENT_RUNTIME_INVALID_OUTPUT"));

        when(runtimeClient.execute(any())).thenThrow(new AgentRuntimeException("AGENT_RUNTIME_UNAVAILABLE", "timeout"));
        mockMvc.perform(post("/api/v1/agent-runs")
                        .header("Authorization", "Bearer " + accessToken)
                        .header("Idempotency-Key", "agent-timeout-" + UUID.randomUUID())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(agentRunPayload("timeout")))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.status").value("FAILED"))
                .andExpect(jsonPath("$.failureCode").value("AGENT_RUNTIME_UNAVAILABLE"));
    }

    private MvcResult consumeBootstrap(String code) throws Exception {
        return mockMvc.perform(post("/api/v1/device-bootstrap/consume")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(bootstrapPayload(code)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.accessToken").isString())
                .andExpect(jsonPath("$.refreshToken").isString())
                .andReturn();
    }

    private String initializeAndReadAccessToken() throws Exception {
        BootstrapCode bootstrapCode = deviceService.createBootstrapCodeForCli();
        return read(consumeBootstrap(bootstrapCode.code()), "accessToken");
    }

    private AgentRuntimeResponse successRuntimeResponse() {
        return new AgentRuntimeResponse("1.0", "Agent runtime is ready", List.of(
                new AgentRuntimeResponse.Card("SYSTEM_STATUS", "AI教练服务已连接", "Java与Python运行链路正常")
        ));
    }

    private String bootstrapPayload(String code) {
        return """
                {
                  "bootstrapCode":"%s",
                  "deviceName":"测试 Mac",
                  "platform":"MACOS"
                }
                """.formatted(code);
    }

    private String pairingPayload(String code) {
        return """
                {
                  "pairingCode":"%s",
                  "deviceName":"测试 iPhone",
                  "platform":"IOS"
                }
                """.formatted(code);
    }

    private String agentRunPayload(String mockMode) {
        return """
                {
                  "triggerType":"TECHNICAL_SMOKE_TEST",
                  "inputSummary":"技术链路检查",
                  "mockMode":"%s"
                }
                """.formatted(mockMode);
    }

    private String read(MvcResult result, String field) throws Exception {
        JsonNode json = objectMapper.readTree(result.getResponse().getContentAsString());
        return json.path(field).asText();
    }

    private int countRows(String table) {
        return jdbcTemplate.queryForObject("SELECT COUNT(*) FROM " + table, Integer.class);
    }

    private int countAuditActions(String action) {
        return jdbcTemplate.queryForObject("SELECT COUNT(*) FROM audit_log WHERE action = ?", Integer.class, action);
    }

    private String auditSnapshots() {
        return jdbcTemplate.queryForObject("""
                SELECT COALESCE(string_agg(
                    COALESCE(before_snapshot::text, '') || COALESCE(after_snapshot::text, ''),
                    ''
                ), '')
                FROM audit_log
                """, String.class);
    }
}
