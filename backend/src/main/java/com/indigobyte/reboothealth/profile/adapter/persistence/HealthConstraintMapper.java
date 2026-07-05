package com.indigobyte.reboothealth.profile.adapter.persistence;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

/**
 * health_constraint 表的 MyBatis-Plus Mapper。
 *
 * <p>枚举字段已经在 DO 中转换为 String，不依赖 MyBatis 枚举 TypeHandler。</p>
 */
@Mapper
public interface HealthConstraintMapper extends BaseMapper<HealthConstraintDataObject> {
}
