package com.indigobyte.reboothealth.idempotency.adapter.persistence;

import com.indigobyte.reboothealth.idempotency.domain.IdempotencyRecord;
import com.indigobyte.reboothealth.idempotency.domain.IdempotencyState;

/**
 * 幂等记录领域对象与持久化对象转换器。
 */
public final class IdempotencyPersistenceConverter {

    private IdempotencyPersistenceConverter() {
    }

    public static IdempotencyRecordDataObject toDataObject(IdempotencyRecord record) {
        return new IdempotencyRecordDataObject(
                record.getId(),
                record.getIdempotencyKey(),
                record.getOperationCode(),
                record.getRequestHash(),
                record.getState().name(),
                record.getResourceType(),
                record.getResourceId(),
                record.getResponseStatus(),
                record.getCreatedAt(),
                record.getCompletedAt()
        );
    }

    public static IdempotencyRecord toDomain(IdempotencyRecordDataObject dataObject) {
        if (dataObject == null) {
            return null;
        }
        return new IdempotencyRecord(
                dataObject.getId(),
                dataObject.getIdempotencyKey(),
                dataObject.getOperationCode(),
                dataObject.getRequestHash(),
                IdempotencyState.valueOf(dataObject.getState()),
                dataObject.getResourceType(),
                dataObject.getResourceId(),
                dataObject.getResponseStatus(),
                dataObject.getCreatedAt(),
                dataObject.getCompletedAt()
        );
    }
}
