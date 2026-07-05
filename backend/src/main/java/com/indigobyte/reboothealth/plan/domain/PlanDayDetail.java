package com.indigobyte.reboothealth.plan.domain;

import java.util.List;

/**
 * 计划日及其条目的只读详情。
 */
public record PlanDayDetail(PlanDay day, List<PlanItem> items) {
}
