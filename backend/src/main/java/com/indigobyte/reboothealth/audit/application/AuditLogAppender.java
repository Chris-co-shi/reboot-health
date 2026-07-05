package com.indigobyte.reboothealth.audit.application;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.indigobyte.reboothealth.audit.domain.AuditLog;
import com.indigobyte.reboothealth.audit.domain.AuditLogRepository;
import com.indigobyte.reboothealth.error.ApplicationException;
import com.indigobyte.reboothealth.error.ErrorCode;
import java.time.Clock;
import java.time.Instant;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

@Component
public class AuditLogAppender {

    public static final String LOCAL_USER = "LOCAL_USER";

    private final AuditLogRepository auditLogRepository;
    private final ObjectMapper objectMapper;
    private final Clock clock;

    public AuditLogAppender(AuditLogRepository auditLogRepository, ObjectMapper objectMapper, Clock clock) {
        this.auditLogRepository = auditLogRepository;
        this.objectMapper = objectMapper;
        this.clock = clock;
    }

    public void append(String action, String entityType, UUID entityId, Object before, Object after) {
        try {
            auditLogRepository.append(new AuditLog(
                    UUID.randomUUID(),
                    LOCAL_USER,
                    action,
                    entityType,
                    entityId,
                    snapshot(before),
                    snapshot(after),
                    Instant.now(clock)
            ));
        } catch (JsonProcessingException ex) {
            throw new ApplicationException(ErrorCode.AUDIT_WRITE_FAILED, "审计快照序列化失败", HttpStatus.INTERNAL_SERVER_ERROR);
        }
    }

    private String snapshot(Object value) throws JsonProcessingException {
        return value == null ? null : objectMapper.writeValueAsString(value);
    }
}
