package com.indigobyte.reboothealth.audit.adapter;

import com.indigobyte.reboothealth.audit.domain.AuditLog;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AuditLogMapper {

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
