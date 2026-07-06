package com.indigobyte.reboothealth.idempotency.adapter.persistence;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.indigobyte.reboothealth.idempotency.domain.IdempotencyRecord;
import com.indigobyte.reboothealth.idempotency.domain.IdempotencyRepository;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

/**
 * IdempotencyRepository 的 MyBatis-Plus 实现。
 */
@Repository
@RequiredArgsConstructor
public class MyBatisIdempotencyRepository implements IdempotencyRepository {

    private final IdempotencyRecordMapper mapper;

    @Override
    public boolean insertProcessing(IdempotencyRecord record) {
        return mapper.insertProcessing(IdempotencyPersistenceConverter.toDataObject(record)) == 1;
    }

    @Override
    public Optional<IdempotencyRecord> findByKey(String key) {
        LambdaQueryWrapper<IdempotencyRecordDataObject> query = new LambdaQueryWrapper<>();
        query.eq(IdempotencyRecordDataObject::getIdempotencyKey, key);
        return Optional.ofNullable(IdempotencyPersistenceConverter.toDomain(mapper.selectOne(query)));
    }

    @Override
    public boolean complete(String key, String resourceType, UUID resourceId, int responseStatus, Instant completedAt) {
        return mapper.complete(key, resourceType, resourceId, responseStatus, completedAt) == 1;
    }

    @Override
    public boolean deleteProcessing(String key) {
        return mapper.deleteProcessing(key) == 1;
    }
}
