package com.indigobyte.reboothealth.plan.domain;

import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

/**
 * 计划确认时保存的健康约束稳定快照。
 *
 * <p>快照只暴露明确字段，并通过 schemaVersion 支持后续格式演进；不得直接序列化领域对象作为历史上下文。</p>
 */
public record HealthConstraintSnapshot(
        int schemaVersion,
        Instant generatedAt,
        List<Item> items
) {

    /**
     * 健康约束快照条目。
     */
    public record Item(
            UUID id,
            String constraintType,
            String bodyRegion,
            String severity,
            String title,
            String description,
            String sourceType,
            String sourceNote,
            String status,
            LocalDate effectiveFrom,
            LocalDate effectiveTo
    ) {
    }
}
