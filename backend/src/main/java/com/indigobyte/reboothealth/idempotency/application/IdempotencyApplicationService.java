package com.indigobyte.reboothealth.idempotency.application;

import com.indigobyte.reboothealth.error.ApplicationException;
import com.indigobyte.reboothealth.error.ErrorCode;
import com.indigobyte.reboothealth.idempotency.domain.IdempotencyRecord;
import com.indigobyte.reboothealth.idempotency.domain.IdempotencyRepository;
import java.time.Clock;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

/**
 * 幂等应用服务。
 *
 * <p>负责 key 校验、命令指纹比对、PROCESSING 记录插入和 COMPLETED 标记；业务事务由调用方包裹。</p>
 */
@Service
@RequiredArgsConstructor
public class IdempotencyApplicationService {

    private final IdempotencyRepository repository;
    private final IdempotencyKeyValidator keyValidator;
    private final CommandFingerprint fingerprint;
    private final Clock clock;

    public IdempotencyStart start(String key, String operationCode, Map<String, UUID> pathIds, Object command) {
        keyValidator.validate(key);
        String requestHash = fingerprint.hash(operationCode, pathIds, command);
        Instant now = Instant.now(clock);
        boolean inserted = repository.insertProcessing(IdempotencyRecord.processing(key, operationCode, requestHash, now));
        if (inserted) {
            return new IdempotencyStart(true, null);
        }
        IdempotencyRecord existing = repository.findByKey(key).orElseThrow(() -> new ApplicationException(
                ErrorCode.DATA_CONFLICT, "幂等记录读取失败，请重试", HttpStatus.CONFLICT));
        if (!existing.getOperationCode().equals(operationCode) || !existing.getRequestHash().equals(requestHash)) {
            throw new ApplicationException(ErrorCode.IDEMPOTENCY_KEY_REUSED,
                    "Idempotency-Key 已被不同请求使用", HttpStatus.CONFLICT);
        }
        return new IdempotencyStart(false, existing);
    }

    public void complete(String key, String resourceType, UUID resourceId, int responseStatus) {
        boolean completed = repository.complete(key, resourceType, resourceId, responseStatus, Instant.now(clock));
        if (!completed) {
            throw new ApplicationException(ErrorCode.DATA_CONFLICT, "幂等记录完成状态更新失败", HttpStatus.CONFLICT);
        }
    }
}
