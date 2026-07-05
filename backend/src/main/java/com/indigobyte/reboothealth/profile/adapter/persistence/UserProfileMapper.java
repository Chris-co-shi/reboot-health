package com.indigobyte.reboothealth.profile.adapter.persistence;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

/**
 * app_user_profile 表的 MyBatis-Plus Mapper。
 *
 * <p>只映射 Persistence DO，业务语义由 Repository Adapter 和应用服务处理。</p>
 */
@Mapper
public interface UserProfileMapper extends BaseMapper<UserProfileDataObject> {
}
