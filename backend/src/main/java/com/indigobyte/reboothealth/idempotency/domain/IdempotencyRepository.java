package com.indigobyte.reboothealth.idempotency.domain;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;

/**
 * 幂等记录仓储端口。
 *
 * <p>只暴露 insert/find/complete 语义，避免先执行业务后补写幂等记录。</p>
 */
public interface IdempotencyRepository {

    boolean insertProcessing(IdempotencyRecord record);

    Optional<IdempotencyRecord> findByKey(String key);

    boolean complete(String key, String resourceType, UUID resourceId, int responseStatus, Instant completedAt);

    boolean deleteProcessing(String key);
}
