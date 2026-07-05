package com.indigobyte.reboothealth.idempotency.adapter.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.Instant;
import java.util.UUID;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/**
 * idempotency_record 表的持久化对象。
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@TableName("idempotency_record")
public class IdempotencyRecordDataObject {

    @TableId(value = "id", type = IdType.INPUT)
    private UUID id;

    @TableField("idempotency_key")
    private String idempotencyKey;

    @TableField("operation_code")
    private String operationCode;

    @TableField("request_hash")
    private String requestHash;

    @TableField("state")
    private String state;

    @TableField("resource_type")
    private String resourceType;

    @TableField("resource_id")
    private UUID resourceId;

    @TableField("response_status")
    private Integer responseStatus;

    @TableField("created_at")
    private Instant createdAt;

    @TableField("completed_at")
    private Instant completedAt;
}
