package com.indigobyte.reboothealth.audit.domain;

public interface AuditLogRepository {

    void append(AuditLog auditLog);
}
