package com.indigobyte.reboothealth.plan.adapter.api;

import com.indigobyte.reboothealth.plan.adapter.api.PlanRequests.CreateDraftRequest;
import com.indigobyte.reboothealth.plan.adapter.api.PlanRequests.CreatePlanRequest;
import com.indigobyte.reboothealth.plan.adapter.api.PlanVersionResponse.PlanVersionSummaryResponse;
import com.indigobyte.reboothealth.plan.application.IdempotentResult;
import com.indigobyte.reboothealth.plan.application.PlanApplicationService;
import com.indigobyte.reboothealth.plan.application.PlanApplicationService.CreateDraftCommand;
import com.indigobyte.reboothealth.plan.application.PlanApplicationService.CreatePlanCommand;
import com.indigobyte.reboothealth.plan.domain.PlanVersionFilter;
import com.indigobyte.reboothealth.plan.domain.PlanVersionStatus;
import jakarta.validation.Valid;
import java.time.Clock;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 长期计划 REST API。
 */
@RestController
@RequestMapping("/api/v1/plans")
public class PlanController {

    private final PlanApplicationService service;
    private final Clock clock;

    public PlanController(PlanApplicationService service, Clock clock) {
        this.service = service;
        this.clock = clock;
    }

    @PostMapping
    public ResponseEntity<PlanResponse> create(
            @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey,
            @Valid @RequestBody CreatePlanRequest request
    ) {
        IdempotentResult<PlanResponse> result = map(service.createPlan(
                idempotencyKey,
                new CreatePlanCommand(request.title(), request.summary())
        ), PlanResponse::from);
        return response(result);
    }

    @GetMapping
    public PlanResponse singleton() {
        return PlanResponse.from(service.getSingletonPlan());
    }

    @GetMapping("/current")
    public PlanVersionResponse current() {
        return PlanVersionResponse.from(service.getCurrentPlan(LocalDate.now(clock)));
    }

    @GetMapping("/{planId}")
    public PlanResponse get(@PathVariable UUID planId) {
        return PlanResponse.from(service.getPlan(planId));
    }

    @GetMapping("/{planId}/versions")
    public List<PlanVersionSummaryResponse> versions(
            @PathVariable UUID planId,
            @RequestParam(required = false) PlanVersionStatus status
    ) {
        return service.listVersions(planId, new PlanVersionFilter(status)).stream()
                .map(PlanVersionResponse::summary)
                .toList();
    }

    @PostMapping("/{planId}/versions")
    public ResponseEntity<PlanVersionResponse> createDraft(
            @PathVariable UUID planId,
            @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey,
            @Valid @RequestBody CreateDraftRequest request
    ) {
        return response(map(service.createDraft(
                idempotencyKey,
                planId,
                new CreateDraftCommand(request.startDate(), request.title(), request.summary(), request.goalIds())
        ), PlanVersionResponse::from));
    }

    private <S, T> IdempotentResult<T> map(IdempotentResult<S> source, java.util.function.Function<S, T> mapper) {
        return new IdempotentResult<>(mapper.apply(source.body()), source.responseStatus(), source.replayed());
    }

    private <T> ResponseEntity<T> response(IdempotentResult<T> result) {
        return ResponseEntity.status(HttpStatus.valueOf(result.responseStatus()))
                .header("Idempotency-Replayed", String.valueOf(result.replayed()))
                .body(result.body());
    }
}
