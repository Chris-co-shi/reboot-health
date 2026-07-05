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

    /**
     * 查询健康约束列表。
     *
     * @param status 可选的状态过滤条件
     * @param includeArchived 是否包含已归档的约束，默认为 false
     * @return 健康约束响应对象列表
     */
    @GetMapping
    public List<HealthConstraintResponse> list(
            @RequestParam(required = false) ConstraintStatus status,
            @RequestParam(defaultValue = "false") boolean includeArchived
    ) {
        return service.list(new HealthConstraintFilter(status, includeArchived)).stream()
                .map(HealthConstraintResponse::from)
                .toList();
    }

    /**
     * 创建新的健康约束。
     *
     * @param request 包含约束信息的请求对象
     * @return 创建后的健康约束响应对象
     */
    @PostMapping
    public HealthConstraintResponse create(@Valid @RequestBody HealthConstraintRequest request) {
        return HealthConstraintResponse.from(service.create(toCommand(request)));
    }

    /**
     * 更新健康约束的业务字段。
     *
     * @param id 约束 ID
     * @param request 包含更新数据的请求对象
     * @return 更新后的健康约束响应对象
     */
    @PutMapping("/{id}")
    public HealthConstraintResponse update(@PathVariable UUID id, @Valid @RequestBody HealthConstraintRequest request) {
        return HealthConstraintResponse.from(service.update(id, toCommand(request)));
    }

    /**
     * 变更健康约束的状态。
     *
     * @param id 约束 ID
     * @param request 包含目标状态的请求对象
     * @return 状态变更后的健康约束响应对象
     */
    @PatchMapping("/{id}/status")
    public HealthConstraintResponse changeStatus(@PathVariable UUID id, @Valid @RequestBody HealthConstraintStatusRequest request) {
        return HealthConstraintResponse.from(service.changeStatus(id, request.status()));
    }

    /**
     * 归档健康约束。
     *
     * @param id 约束 ID
     * @param request 包含归档原因的请求对象
     * @return 归档后的健康约束响应对象
     */
    @PostMapping("/{id}/archive")
    public HealthConstraintResponse archive(@PathVariable UUID id, @Valid @RequestBody ArchiveRequest request) {
        return HealthConstraintResponse.from(service.archive(id, request.archiveReason()));
    }

    /**
     * 将 API 请求对象转换为应用服务命令对象。
     *
     * @param request API 层的健康约束请求对象
     * @return 应用层的保存命令对象
     */
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
