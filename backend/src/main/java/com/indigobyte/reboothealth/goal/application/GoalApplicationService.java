package com.indigobyte.reboothealth.goal.application;

import com.indigobyte.reboothealth.audit.application.AuditLogAppender;
import com.indigobyte.reboothealth.error.ApplicationException;
import com.indigobyte.reboothealth.error.ErrorCode;
import com.indigobyte.reboothealth.goal.domain.Goal;
import com.indigobyte.reboothealth.goal.domain.GoalFilter;
import com.indigobyte.reboothealth.goal.domain.GoalRepository;
import com.indigobyte.reboothealth.goal.domain.GoalStatus;
import com.indigobyte.reboothealth.goal.domain.GoalType;
import com.indigobyte.reboothealth.goal.domain.GoalUnit;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class GoalApplicationService {

    private static final String ENTITY_TYPE = "Goal";

    private final GoalRepository repository;
    private final AuditLogAppender auditLogAppender;
    private final Clock clock;

    public GoalApplicationService(GoalRepository repository, AuditLogAppender auditLogAppender, Clock clock) {
        this.repository = repository;
        this.auditLogAppender = auditLogAppender;
        this.clock = clock;
    }

    @Transactional(readOnly = true)
    public List<Goal> list(GoalFilter filter) {
        return repository.findAll(filter);
    }

    @Transactional
    public Goal create(SaveGoalCommand command) {
        Instant now = Instant.now(clock);
        Goal goal = Goal.create(
                command.goalType(),
                command.title(),
                command.targetValue(),
                command.unit(),
                command.baselineValue(),
                command.targetDate(),
                command.priority(),
                now
        );
        Goal saved = repository.save(goal);
        auditLogAppender.append("GOAL_CREATED", ENTITY_TYPE, saved.getId(), null, saved);
        return saved;
    }

    @Transactional
    public Goal update(UUID id, SaveGoalCommand command) {
        Goal current = findRequired(id);
        Goal before = copy(current);
        current.update(
                command.goalType(),
                command.title(),
                command.targetValue(),
                command.unit(),
                command.baselineValue(),
                command.targetDate(),
                command.priority(),
                Instant.now(clock)
        );
        Goal saved = repository.save(current);
        auditLogAppender.append("GOAL_UPDATED", ENTITY_TYPE, saved.getId(), before, saved);
        return saved;
    }

    @Transactional
    public Goal changeStatus(UUID id, GoalStatus targetStatus) {
        Goal current = findRequired(id);
        Goal before = copy(current);
        current.changeStatus(targetStatus, Instant.now(clock));
        Goal saved = repository.save(current);
        auditLogAppender.append("GOAL_STATUS_CHANGED", ENTITY_TYPE, saved.getId(), before, saved);
        return saved;
    }

    @Transactional
    public Goal archive(UUID id, String archiveReason) {
        Goal current = findRequired(id);
        Goal before = copy(current);
        current.archive(archiveReason, Instant.now(clock));
        Goal saved = repository.save(current);
        auditLogAppender.append("GOAL_ARCHIVED", ENTITY_TYPE, saved.getId(), before, saved);
        return saved;
    }

    private Goal findRequired(UUID id) {
        return repository.findById(id).orElseThrow(() -> new ApplicationException(
                ErrorCode.GOAL_NOT_FOUND,
                "目标不存在",
                HttpStatus.NOT_FOUND
        ));
    }

    private Goal copy(Goal source) {
        return new Goal(
                source.getId(),
                source.getGoalType(),
                source.getTitle(),
                source.getTargetValue(),
                source.getUnit(),
                source.getBaselineValue(),
                source.getTargetDate(),
                source.getStatus(),
                source.getPriority(),
                source.getArchiveReason(),
                source.getCreatedAt(),
                source.getUpdatedAt(),
                source.getArchivedAt()
        );
    }

    public record SaveGoalCommand(
            GoalType goalType,
            String title,
            BigDecimal targetValue,
            GoalUnit unit,
            BigDecimal baselineValue,
            LocalDate targetDate,
            Integer priority
    ) {
    }
}
