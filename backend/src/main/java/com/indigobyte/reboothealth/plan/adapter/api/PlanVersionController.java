package com.indigobyte.reboothealth.plan.adapter.api;

import com.indigobyte.reboothealth.plan.adapter.api.PlanRequests.CancelVersionRequest;
import com.indigobyte.reboothealth.plan.adapter.api.PlanRequests.ConfirmVersionRequest;
import com.indigobyte.reboothealth.plan.adapter.api.PlanRequests.CopyVersionRequest;
import com.indigobyte.reboothealth.plan.adapter.api.PlanRequests.SaveDayRequest;
import com.indigobyte.reboothealth.plan.adapter.api.PlanRequests.SaveItemRequest;
import com.indigobyte.reboothealth.plan.adapter.api.PlanRequests.UpdateVersionRequest;
import com.indigobyte.reboothealth.plan.application.IdempotentResult;
import com.indigobyte.reboothealth.plan.application.PlanApplicationService;
import com.indigobyte.reboothealth.plan.application.PlanApplicationService.CancelVersionCommand;
import com.indigobyte.reboothealth.plan.application.PlanApplicationService.ConfirmVersionCommand;
import com.indigobyte.reboothealth.plan.application.PlanApplicationService.CopyVersionCommand;
import com.indigobyte.reboothealth.plan.application.PlanApplicationService.SaveDayCommand;
import com.indigobyte.reboothealth.plan.application.PlanApplicationService.SaveItemCommand;
import com.indigobyte.reboothealth.plan.application.PlanApplicationService.UpdateVersionCommand;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.validation.annotation.Validated;

/**
 * 计划版本、计划日和计划条目 REST API。
 */
@RestController
@RequestMapping("/api/v1")
@Validated
public class PlanVersionController {

    private final PlanApplicationService service;

    public PlanVersionController(PlanApplicationService service) {
        this.service = service;
    }

    @GetMapping("/plan-versions/{versionId}")
    public PlanVersionResponse get(@PathVariable UUID versionId) {
        return PlanVersionResponse.from(service.getVersionDetail(versionId));
    }

    @GetMapping("/plan-versions/{versionId}/preview")
    public PlanVersionPreviewResponse preview(@PathVariable UUID versionId) {
        return PlanVersionPreviewResponse.from(service.preview(versionId));
    }

    @PutMapping("/plan-versions/{versionId}")
    public PlanVersionResponse update(@PathVariable UUID versionId, @Valid @RequestBody UpdateVersionRequest request) {
        return PlanVersionResponse.from(service.updateVersion(versionId, new UpdateVersionCommand(
                request.title(), request.summary(), request.goalIds(), request.expectedRevision()
        )));
    }

    @PostMapping("/plan-versions/{versionId}/confirm")
    public ResponseEntity<PlanVersionResponse> confirm(
            @PathVariable UUID versionId,
            @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey,
            @Valid @RequestBody ConfirmVersionRequest request
    ) {
        return response(map(service.confirm(idempotencyKey, versionId,
                new ConfirmVersionCommand(request.expectedRevision())), PlanVersionResponse::from));
    }

    @PostMapping("/plan-versions/{versionId}/cancel")
    public ResponseEntity<PlanVersionResponse> cancel(
            @PathVariable UUID versionId,
            @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey,
            @Valid @RequestBody CancelVersionRequest request
    ) {
        return response(map(service.cancel(idempotencyKey, versionId,
                        new CancelVersionCommand(request.cancelReason(), request.expectedRevision())),
                PlanVersionResponse::from));
    }

    @PostMapping("/plan-versions/{sourceVersionId}/copy")
    public ResponseEntity<PlanVersionResponse> copy(
            @PathVariable UUID sourceVersionId,
            @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey,
            @Valid @RequestBody CopyVersionRequest request
    ) {
        return response(map(service.copyVersion(idempotencyKey, sourceVersionId, new CopyVersionCommand(
                request.startDate(), request.title(), request.summary(), request.expectedSourceStatus()
        )), PlanVersionResponse::from));
    }

    @PostMapping("/plan-versions/{versionId}/days")
    public ResponseEntity<PlanVersionResponse> createDay(
            @PathVariable UUID versionId,
            @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey,
            @Valid @RequestBody SaveDayRequest request
    ) {
        return response(map(service.createDay(idempotencyKey, versionId, toCommand(request)), PlanVersionResponse::from));
    }

    @PutMapping("/plan-days/{dayId}")
    public PlanVersionResponse updateDay(@PathVariable UUID dayId, @Valid @RequestBody SaveDayRequest request) {
        return PlanVersionResponse.from(service.updateDay(dayId, toCommand(request)));
    }

    @DeleteMapping("/plan-days/{dayId}")
    public PlanVersionResponse deleteDay(@PathVariable UUID dayId,
                                         @RequestParam @NotNull @Min(0) Integer expectedRevision) {
        return PlanVersionResponse.from(service.deleteDay(dayId, expectedRevision));
    }

    @PostMapping("/plan-days/{dayId}/items")
    public ResponseEntity<PlanVersionResponse> createItem(
            @PathVariable UUID dayId,
            @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey,
            @Valid @RequestBody SaveItemRequest request
    ) {
        return response(map(service.createItem(idempotencyKey, dayId, toCommand(request)), PlanVersionResponse::from));
    }

    @PutMapping("/plan-items/{itemId}")
    public PlanVersionResponse updateItem(@PathVariable UUID itemId, @Valid @RequestBody SaveItemRequest request) {
        return PlanVersionResponse.from(service.updateItem(itemId, toCommand(request)));
    }

    @DeleteMapping("/plan-items/{itemId}")
    public PlanVersionResponse deleteItem(@PathVariable UUID itemId,
                                          @RequestParam @NotNull @Min(0) Integer expectedRevision) {
        return PlanVersionResponse.from(service.deleteItem(itemId, expectedRevision));
    }

    private SaveDayCommand toCommand(SaveDayRequest request) {
        return new SaveDayCommand(request.dayDate(), request.title(), request.note(), request.sortOrder(), request.expectedRevision());
    }

    private SaveItemCommand toCommand(SaveItemRequest request) {
        return new SaveItemCommand(request.goalId(), request.itemType(), request.title(), request.description(),
                request.plannedSets(), request.plannedReps(), request.plannedDurationMinutes(),
                request.plannedDistanceMeters(), request.plannedRpe(), request.sortOrder(), request.expectedRevision());
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
