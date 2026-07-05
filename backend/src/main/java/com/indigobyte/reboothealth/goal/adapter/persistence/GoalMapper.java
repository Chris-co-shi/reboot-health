package com.indigobyte.reboothealth.goal.adapter.persistence;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

/**
 * goal 表的 MyBatis-Plus Mapper。
 *
 * <p>只负责数据库行映射，不承载目标状态机或单位组合校验。</p>
 */
@Mapper
public interface GoalMapper extends BaseMapper<GoalDataObject> {
}
