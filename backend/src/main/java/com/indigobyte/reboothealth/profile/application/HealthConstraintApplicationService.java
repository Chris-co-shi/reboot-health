package com.indigobyte.reboothealth.profile.application;

import com.indigobyte.reboothealth.audit.application.AuditLogAppender;
import com.indigobyte.reboothealth.error.ApplicationException;
import com.indigobyte.reboothealth.error.ErrorCode;
import com.indigobyte.reboothealth.profile.domain.BodyRegion;
import com.indigobyte.reboothealth.profile.domain.ConstraintSeverity;
import com.indigobyte.reboothealth.profile.domain.ConstraintSourceType;
import com.indigobyte.reboothealth.profile.domain.ConstraintStatus;
import com.indigobyte.reboothealth.profile.domain.ConstraintType;
import com.indigobyte.reboothealth.profile.domain.HealthConstraint;
import com.indigobyte.reboothealth.profile.domain.HealthConstraintFilter;
import com.indigobyte.reboothealth.profile.domain.HealthConstraintRepository;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 健康约束应用服务。
 *
 * <p>负责健康约束查询、创建、修改、普通状态变更和归档的事务编排；状态机由领域聚合执行。</p>
 */
@Service
@RequiredArgsConstructor
public class HealthConstraintApplicationService {

    private static final String ENTITY_TYPE = "HealthConstraint";

    private final HealthConstraintRepository repository;
    private final AuditLogAppender auditLogAppender;
    private final Clock clock;

    @Transactional(readOnly = true)
    public List<HealthConstraint> list(HealthConstraintFilter filter) {
        return repository.findAll(filter);
    }

    @Transactional
    public HealthConstraint create(SaveHealthConstraintCommand command) {
        Instant now = Instant.now(clock);
        HealthConstraint constraint = HealthConstraint.create(
                command.constraintType(),
                command.bodyRegion(),
                command.severity(),
                command.title(),
                command.description(),
                command.sourceType(),
                command.sourceNote(),
                command.effectiveFrom(),
                command.effectiveTo(),
                now
        );
        repository.insert(constraint);
        auditLogAppender.append("HEALTH_CONSTRAINT_CREATED", ENTITY_TYPE, constraint.getId(), null, constraint);
        return constraint;
    }

    @Transactional
    public HealthConstraint update(UUID id, SaveHealthConstraintCommand command) {
        HealthConstraint current = findRequired(id);
        HealthConstraint before = copy(current);
        current.update(
                command.constraintType(),
                command.bodyRegion(),
                command.severity(),
                command.title(),
                command.description(),
                command.sourceType(),
                command.sourceNote(),
                command.effectiveFrom(),
                command.effectiveTo(),
                Instant.now(clock)
        );
        assertUpdated(repository.update(current));
        auditLogAppender.append("HEALTH_CONSTRAINT_UPDATED", ENTITY_TYPE, current.getId(), before, current);
        return current;
    }

    @Transactional
    public HealthConstraint changeStatus(UUID id, ConstraintStatus targetStatus) {
        HealthConstraint current = findRequired(id);
        HealthConstraint before = copy(current);
        current.changeStatus(targetStatus, Instant.now(clock));
        assertUpdated(repository.update(current));
        auditLogAppender.append("HEALTH_CONSTRAINT_STATUS_CHANGED", ENTITY_TYPE, current.getId(), before, current);
        return current;
    }

    @Transactional
    public HealthConstraint archive(UUID id, String archiveReason) {
        HealthConstraint current = findRequired(id);
        HealthConstraint before = copy(current);
        current.archive(archiveReason, Instant.now(clock));
        assertUpdated(repository.update(current));
        auditLogAppender.append("HEALTH_CONSTRAINT_ARCHIVED", ENTITY_TYPE, current.getId(), before, current);
        return current;
    }

    private HealthConstraint findRequired(UUID id) {
        return repository.findById(id).orElseThrow(() -> new ApplicationException(
                ErrorCode.HEALTH_CONSTRAINT_NOT_FOUND,
                "健康约束不存在",
                HttpStatus.NOT_FOUND
        ));
    }

    private HealthConstraint copy(HealthConstraint source) {
        return new HealthConstraint(
                source.getId(),
                source.getConstraintType(),
                source.getBodyRegion(),
                source.getSeverity(),
                source.getTitle(),
                source.getDescription(),
                source.getSourceType(),
                source.getSourceNote(),
                source.getStatus(),
                source.getEffectiveFrom(),
                source.getEffectiveTo(),
                source.getArchiveReason(),
                source.getCreatedAt(),
                source.getUpdatedAt(),
                source.getArchivedAt()
        );
    }

    private void assertUpdated(boolean updated) {
        if (!updated) {
            throw new ApplicationException(ErrorCode.DATA_CONFLICT, "健康约束更新冲突，请刷新后重试", HttpStatus.CONFLICT);
        }
    }

    public record SaveHealthConstraintCommand(
            ConstraintType constraintType,
            BodyRegion bodyRegion,
            ConstraintSeverity severity,
            String title,
            String description,
            ConstraintSourceType sourceType,
            String sourceNote,
            LocalDate effectiveFrom,
            LocalDate effectiveTo
    ) {
    }
}
