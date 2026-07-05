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

    /**
     * 查询健康约束列表。
     *
     * @param filter 过滤条件，包含状态和是否包含已归档约束
     * @return 符合条件的约束列表，按创建时间倒序排列
     */
    @Transactional(readOnly = true)
    public List<HealthConstraint> list(HealthConstraintFilter filter) {
        return repository.findAll(filter);
    }

    /**
     * 创建新的健康约束。
     *
     * <p>新建的约束默认为 ACTIVE 状态，并记录审计日志。</p>
     *
     * @param command 包含约束信息的命令对象
     * @return 创建后的健康约束对象
     */
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

    /**
     * 更新健康约束的业务字段。
     *
     * <p>已归档的约束不能编辑，更新前会创建副本用于审计日志。</p>
     *
     * @param id 约束 ID
     * @param command 包含更新数据的命令对象
     * @return 更新后的健康约束对象
     * @throws ApplicationException 如果约束不存在或更新冲突
     */
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

    /**
     * 变更健康约束的状态。
     *
     * <p>不允许直接进入 ARCHIVED 状态，归档必须走 archive 方法。更新前会创建副本用于审计日志。</p>
     *
     * @param id 约束 ID
     * @param targetStatus 目标状态
     * @return 状态变更后的健康约束对象
     * @throws ApplicationException 如果约束不存在、状态转换不合法或更新冲突
     */
    @Transactional
    public HealthConstraint changeStatus(UUID id, ConstraintStatus targetStatus) {
        HealthConstraint current = findRequired(id);
        HealthConstraint before = copy(current);
        current.changeStatus(targetStatus, Instant.now(clock));
        assertUpdated(repository.update(current));
        auditLogAppender.append("HEALTH_CONSTRAINT_STATUS_CHANGED", ENTITY_TYPE, current.getId(), before, current);
        return current;
    }

    /**
     * 归档健康约束。
     *
     * <p>归档是终态操作，必须提供归档原因。更新前会创建副本用于审计日志。</p>
     *
     * @param id 约束 ID
     * @param archiveReason 归档原因，不能为空
     * @return 归档后的健康约束对象
     * @throws ApplicationException 如果约束不存在、归档原因为空或更新冲突
     */
    @Transactional
    public HealthConstraint archive(UUID id, String archiveReason) {
        HealthConstraint current = findRequired(id);
        HealthConstraint before = copy(current);
        current.archive(archiveReason, Instant.now(clock));
        assertUpdated(repository.update(current));
        auditLogAppender.append("HEALTH_CONSTRAINT_ARCHIVED", ENTITY_TYPE, current.getId(), before, current);
        return current;
    }

    /**
     * 根据 ID 查询约束，不存在则抛出异常。
     *
     * @param id 约束 ID
     * @return 健康约束对象
     * @throws ApplicationException 如果约束不存在，返回 404
     */
    private HealthConstraint findRequired(UUID id) {
        return repository.findById(id).orElseThrow(() -> new ApplicationException(
                ErrorCode.HEALTH_CONSTRAINT_NOT_FOUND,
                "健康约束不存在",
                HttpStatus.NOT_FOUND
        ));
    }

    /**
     * 创建约束对象的深拷贝，用于审计日志记录变更前状态。
     *
     * @param source 源约束对象
     * @return 复制后的新约束对象
     */
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

    /**
     * 断言数据库更新是否成功。
     *
     * @param updated 如果为 false 则抛出冲突异常
     * @throws ApplicationException 如果更新失败，表示存在并发冲突
     */
    private void assertUpdated(boolean updated) {
        if (!updated) {
            throw new ApplicationException(ErrorCode.DATA_CONFLICT, "健康约束更新冲突，请刷新后重试", HttpStatus.CONFLICT);
        }
    }

    /**
     * 保存健康约束的命令对象。
     *
     * @param constraintType 约束类型
     * @param bodyRegion 身体部位
     * @param severity 严重程度
     * @param title 约束标题
     * @param description 详细描述
     * @param sourceType 来源类型
     * @param sourceNote 来源备注
     * @param effectiveFrom 生效开始日期
     * @param effectiveTo 生效结束日期
     */
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
