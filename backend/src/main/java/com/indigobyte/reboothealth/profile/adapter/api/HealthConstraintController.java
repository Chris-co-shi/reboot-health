package com.indigobyte.reboothealth.profile.adapter.api;

import com.indigobyte.reboothealth.profile.application.HealthConstraintApplicationService;
import com.indigobyte.reboothealth.profile.application.HealthConstraintApplicationService.SaveHealthConstraintCommand;
import com.indigobyte.reboothealth.profile.domain.ConstraintStatus;
import com.indigobyte.reboothealth.profile.domain.HealthConstraintFilter;
import jakarta.validation.Valid;
import java.util.List;
import java.util.UUID;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 健康约束 REST API。
 *
 * <p>Controller 只负责请求转换并调用应用服务，不直接依赖持久化接口或持久化对象。</p>
 */
@RestController
@RequestMapping("/api/v1/health-constraints")
public class HealthConstraintController {

    private final HealthConstraintApplicationService service;

    public HealthConstraintController(HealthConstraintApplicationService service) {
        this.service = service;
    }

    @GetMapping
    public List<HealthConstraintResponse> list(
            @RequestParam(required = false) ConstraintStatus status,
            @RequestParam(defaultValue = "false") boolean includeArchived
    ) {
        return service.list(new HealthConstraintFilter(status, includeArchived)).stream()
                .map(HealthConstraintResponse::from)
                .toList();
    }

    @PostMapping
    public HealthConstraintResponse create(@Valid @RequestBody HealthConstraintRequest request) {
        return HealthConstraintResponse.from(service.create(toCommand(request)));
    }

    @PutMapping("/{id}")
    public HealthConstraintResponse update(@PathVariable UUID id, @Valid @RequestBody HealthConstraintRequest request) {
        return HealthConstraintResponse.from(service.update(id, toCommand(request)));
    }

    @PatchMapping("/{id}/status")
    public HealthConstraintResponse changeStatus(@PathVariable UUID id, @Valid @RequestBody HealthConstraintStatusRequest request) {
        return HealthConstraintResponse.from(service.changeStatus(id, request.status()));
    }

    @PostMapping("/{id}/archive")
    public HealthConstraintResponse archive(@PathVariable UUID id, @Valid @RequestBody ArchiveRequest request) {
        return HealthConstraintResponse.from(service.archive(id, request.archiveReason()));
    }

    private SaveHealthConstraintCommand toCommand(HealthConstraintRequest request) {
        return new SaveHealthConstraintCommand(
                request.constraintType(),
                request.bodyRegion(),
                request.severity(),
                request.title(),
                request.description(),
                request.sourceType(),
                request.sourceNote(),
                request.effectiveFrom(),
                request.effectiveTo()
        );
    }
}
