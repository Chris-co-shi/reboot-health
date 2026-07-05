package com.indigobyte.reboothealth.goal.adapter.api;

import com.indigobyte.reboothealth.goal.application.GoalApplicationService;
import com.indigobyte.reboothealth.goal.application.GoalApplicationService.SaveGoalCommand;
import com.indigobyte.reboothealth.goal.domain.GoalFilter;
import com.indigobyte.reboothealth.goal.domain.GoalStatus;
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

@RestController
@RequestMapping("/api/v1/goals")
public class GoalController {

    private final GoalApplicationService service;

    public GoalController(GoalApplicationService service) {
        this.service = service;
    }

    @GetMapping
    public List<GoalResponse> list(
            @RequestParam(required = false) GoalStatus status,
            @RequestParam(defaultValue = "false") boolean includeArchived
    ) {
        return service.list(new GoalFilter(status, includeArchived)).stream()
                .map(GoalResponse::from)
                .toList();
    }

    @PostMapping
    public GoalResponse create(@Valid @RequestBody GoalRequest request) {
        return GoalResponse.from(service.create(toCommand(request)));
    }

    @PutMapping("/{id}")
    public GoalResponse update(@PathVariable UUID id, @Valid @RequestBody GoalRequest request) {
        return GoalResponse.from(service.update(id, toCommand(request)));
    }

    @PatchMapping("/{id}/status")
    public GoalResponse changeStatus(@PathVariable UUID id, @Valid @RequestBody GoalStatusRequest request) {
        return GoalResponse.from(service.changeStatus(id, request.status()));
    }

    @PostMapping("/{id}/archive")
    public GoalResponse archive(@PathVariable UUID id, @Valid @RequestBody GoalArchiveRequest request) {
        return GoalResponse.from(service.archive(id, request.archiveReason()));
    }

    private SaveGoalCommand toCommand(GoalRequest request) {
        return new SaveGoalCommand(
                request.goalType(),
                request.title(),
                request.targetValue(),
                request.unit(),
                request.baselineValue(),
                request.targetDate(),
                request.priority()
        );
    }
}
