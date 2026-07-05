package com.indigobyte.reboothealth.audit.adapter;

import com.indigobyte.reboothealth.audit.domain.AuditLog;
import com.indigobyte.reboothealth.audit.domain.AuditLogRepository;
import org.springframework.stereotype.Repository;

/**
 * AuditLogRepository 的 MyBatis 实现。
 *
 * <p>审计记录只追加，不提供更新或删除入口；事务由调用方应用服务控制。</p>
 */
@Repository
public class MyBatisAuditLogRepository implements AuditLogRepository {

    private final AuditLogMapper auditLogMapper;

    public MyBatisAuditLogRepository(AuditLogMapper auditLogMapper) {
        this.auditLogMapper = auditLogMapper;
    }

    @Override
    public void append(AuditLog auditLog) {
        auditLogMapper.insert(auditLog);
    }
}
