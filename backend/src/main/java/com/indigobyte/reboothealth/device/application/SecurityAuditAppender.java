package com.indigobyte.reboothealth.device.application;

import com.indigobyte.reboothealth.audit.application.AuditLogAppender;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

/**
 * 安全事件审计追加器。
 *
 * <p>部分安全拒绝事件会以业务异常结束请求，因此需要独立事务保存审计，避免拒绝记录被外层事务回滚。</p>
 */
@Component
@RequiredArgsConstructor
public class SecurityAuditAppender {

    private final AuditLogAppender auditLogAppender;

    /**
     * 使用独立事务追加安全审计。
     */
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void append(String action, String entityType, UUID entityId, Object before, Object after) {
        auditLogAppender.append(action, entityType, entityId, before, after);
    }
}
