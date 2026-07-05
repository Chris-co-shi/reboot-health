package com.indigobyte.reboothealth.audit.adapter;

import com.indigobyte.reboothealth.audit.domain.AuditLog;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;

/**
 * audit_log 表的专用 Mapper。
 *
 * <p>before/after 快照是 PostgreSQL JSONB，当前保留显式 CAST，避免未经集成测试验证的隐式字符串写入。</p>
 */
@Mapper
public interface AuditLogMapper {

    /**
     * 追加审计记录。JSON 字符串在 SQL 中显式转为 jsonb。
     */
    @Insert("""
            INSERT INTO audit_log (
                id, actor, action, entity_type, entity_id,
                before_snapshot, after_snapshot, created_at
            ) VALUES (
                #{id}, #{actor}, #{action}, #{entityType}, #{entityId},
                CAST(#{beforeSnapshot} AS jsonb), CAST(#{afterSnapshot} AS jsonb), #{createdAt}
            )
            """)
    void insert(AuditLog auditLog);
}
