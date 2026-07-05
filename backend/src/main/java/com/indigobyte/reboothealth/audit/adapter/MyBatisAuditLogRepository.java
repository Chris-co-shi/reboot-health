package com.indigobyte.reboothealth.audit.adapter;

import com.indigobyte.reboothealth.audit.domain.AuditLog;
import com.indigobyte.reboothealth.audit.domain.AuditLogRepository;
import org.springframework.stereotype.Repository;

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
