package com.indigobyte.reboothealth.plan.adapter.persistence;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import java.util.UUID;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

/**
 * plan 表 Mapper。
 */
@Mapper
public interface PlanMapper extends BaseMapper<PlanDataObject> {

    @Select("SELECT id, title, summary, created_at, updated_at FROM plan WHERE singleton_key = 1")
    PlanDataObject selectCurrent();

    @Select("SELECT id, title, summary, created_at, updated_at FROM plan WHERE id = #{id} FOR UPDATE")
    PlanDataObject selectByIdForUpdate(@Param("id") UUID id);
}
