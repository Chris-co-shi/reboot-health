package com.indigobyte.reboothealth.profile.adapter.api;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * 健康约束归档请求对象。
 *
 * <p>用于 POST /api/v1/health-constraints/{id}/archive 接口，必须提供归档原因。</p>
 *
 * @param archiveReason 归档原因，不能为空且最长 300 字符
 */
public record ArchiveRequest(@NotBlank @Size(max = 300) String archiveReason) {
}
