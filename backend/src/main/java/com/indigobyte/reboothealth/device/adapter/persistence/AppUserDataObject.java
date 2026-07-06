package com.indigobyte.reboothealth.device.adapter.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.Instant;
import java.util.UUID;
import lombok.Getter;
import lombok.Setter;

/**
 * app_user 表持久化对象。
 */
@Getter
@Setter
@TableName("app_user")
public class AppUserDataObject {

    @TableId(type = IdType.INPUT)
    private UUID id;
    private Short singletonKey;
    private String status;
    private Instant createdAt;
    private Instant updatedAt;
}
