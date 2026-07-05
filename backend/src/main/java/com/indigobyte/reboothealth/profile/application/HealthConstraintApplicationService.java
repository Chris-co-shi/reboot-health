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
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class HealthConstraintApplicationService {

    private static final String ENTITY_TYPE = "HealthConstraint";

    private final HealthConstraintRepository repository;
    private final AuditLogAppender auditLogAppender;
    private final Clock clock;

    public HealthConstraintApplicationService(HealthConstraintRepository repository,
                                              AuditLogAppender auditLogAppender,
                                              Clock clock) {
        this.repository = repository;
        this.auditLogAppender = auditLogAppender;
        this.clock = clock;
    }

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
        HealthConstraint saved = repository.save(constraint);
        auditLogAppender.append("HEALTH_CONSTRAINT_CREATED", ENTITY_TYPE, saved.getId(), null, saved);
        return saved;
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
        HealthConstraint saved = repository.save(current);
        auditLogAppender.append("HEALTH_CONSTRAINT_UPDATED", ENTITY_TYPE, saved.getId(), before, saved);
        return saved;
    }

    @Transactional
    public HealthConstraint changeStatus(UUID id, ConstraintStatus targetStatus) {
        HealthConstraint current = findRequired(id);
        HealthConstraint before = copy(current);
        current.changeStatus(targetStatus, Instant.now(clock));
        HealthConstraint saved = repository.save(current);
        auditLogAppender.append("HEALTH_CONSTRAINT_STATUS_CHANGED", ENTITY_TYPE, saved.getId(), before, saved);
        return saved;
    }

    @Transactional
    public HealthConstraint archive(UUID id, String archiveReason) {
        HealthConstraint current = findRequired(id);
        HealthConstraint before = copy(current);
        current.archive(archiveReason, Instant.now(clock));
        HealthConstraint saved = repository.save(current);
        auditLogAppender.append("HEALTH_CONSTRAINT_ARCHIVED", ENTITY_TYPE, saved.getId(), before, saved);
        return saved;
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
