package com.indigobyte.reboothealth.agent.adapter.api;

import com.indigobyte.reboothealth.agent.adapter.api.AgentRunRequests.CreateAgentRunRequest;
import com.indigobyte.reboothealth.agent.application.AgentRunApplicationService;
import com.indigobyte.reboothealth.agent.application.AgentRunApplicationService.CreateAgentRunCommand;
import com.indigobyte.reboothealth.agent.application.AgentRunApplicationService.IdempotentAgentRunResult;
import com.indigobyte.reboothealth.device.application.DeviceApplicationService;
import com.indigobyte.reboothealth.device.domain.DevicePrincipal;
import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * AgentRun REST API。
 *
 * <p>Flutter 只调用 Java；Java 再调用 Python Runtime，并保存结构化结果和状态。</p>
 */
@RestController
@RequestMapping("/api/v1/agent-runs")
public class AgentRunController {

    private final AgentRunApplicationService agentRunService;
    private final DeviceApplicationService deviceService;

    public AgentRunController(AgentRunApplicationService agentRunService, DeviceApplicationService deviceService) {
        this.agentRunService = agentRunService;
        this.deviceService = deviceService;
    }

    @PostMapping
    public ResponseEntity<AgentRunResponse> create(
            @RequestHeader(value = "Authorization", required = false) String authorizationHeader,
            @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey,
            @Valid @RequestBody CreateAgentRunRequest request
    ) {
        DevicePrincipal principal = deviceService.authenticate(authorizationHeader);
        IdempotentAgentRunResult result = agentRunService.create(
                idempotencyKey,
                principal,
                new CreateAgentRunCommand(request.sessionId(), request.triggerType(),
                        request.inputSummary(), request.mockMode())
        );
        return ResponseEntity.status(HttpStatus.valueOf(result.responseStatus()))
                .header("Idempotency-Replayed", String.valueOf(result.replayed()))
                .body(AgentRunResponse.from(result.body()));
    }

    @GetMapping("/{runId}")
    public AgentRunResponse get(
            @PathVariable UUID runId,
            @RequestHeader(value = "Authorization", required = false) String authorizationHeader
    ) {
        DevicePrincipal principal = deviceService.authenticate(authorizationHeader);
        return AgentRunResponse.from(agentRunService.get(runId, principal));
    }
}
