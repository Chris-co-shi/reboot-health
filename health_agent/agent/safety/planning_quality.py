"""INITIAL_PLANNING 输出质量门禁。

门禁只做内容级保守校验：发现过激、越权或不可执行的草案时生成 warning/error。
它不保存事实、不调用外部资源，也不替代后续确定性安全规则。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from agent.safety import rules


@dataclass(frozen=True)
class QualityFinding:
    """质量门禁发现项。"""

    code: str
    message: str
    severity: str = "warning"

    def to_warning(self) -> str:
        """转成 AgentRunResult.warnings 中的稳定字符串。"""
        return f"quality:{self.severity}:{self.code}:{self.message}"

    def to_dict(self) -> dict[str, str]:
        """返回可序列化结构，便于后续 API 化。"""
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class QualityGateResult:
    """Planning Quality Gate 的执行结果。"""

    findings: tuple[QualityFinding, ...] = ()

    @property
    def passed(self) -> bool:
        """没有 error 级发现时视为通过。"""
        return not any(finding.severity == "error" for finding in self.findings)

    @property
    def warnings(self) -> tuple[str, ...]:
        """返回可附加到 AgentRunResult 的 warning 字符串。"""
        return tuple(finding.to_warning() for finding in self.findings)

    def count_by_severity(self, severity: str) -> int:
        """统计指定等级的发现数量。"""
        return sum(1 for finding in self.findings if finding.severity == severity)


class PlanningQualityGate:
    """对 INITIAL_PLANNING 输出执行保守质量校验。"""

    def evaluate(
        self,
        planning_input: Mapping[str, Any] | None,
        output: Mapping[str, Any] | None,
    ) -> QualityGateResult:
        """检查输出是否满足首轮健康计划质量门禁。"""
        input_text = _flatten_text(planning_input or {})
        output_data = dict(output or {})
        output_text = _flatten_text(output_data)
        weekly_text = _flatten_text(output_data.get("weeklyPlanDraft") or {})
        today_text = _flatten_text(output_data.get("todayActionDraft") or {})

        findings: list[QualityFinding] = []
        self._check_confirmation(output_data, findings)
        self._check_forbidden_claims(output_text, findings)
        self._check_cervical_risk(input_text, output_data, findings)
        self._check_swimming_risk(input_text, output_data, findings)
        self._check_low_fitness_risk(
            input_text,
            output_data,
            output_data.get("todayActionDraft") or {},
            findings,
        )
        self._check_extreme_weight_loss_request(input_text, findings)
        self._check_blood_pressure_risk(input_text, output_data, findings)
        self._check_week_one_focus(weekly_text, findings)
        self._check_weekly_downgrade_or_stop(weekly_text, findings)
        self._check_today_minimum_standard(today_text, findings)
        return QualityGateResult(tuple(findings))

    def _check_confirmation(
        self,
        output: Mapping[str, Any],
        findings: list[QualityFinding],
    ) -> None:
        if output.get("requiresUserConfirmation") is not True:
            findings.append(
                QualityFinding(
                    code="auto_confirmed_output",
                    message="INITIAL_PLANNING 输出必须等待用户确认。",
                    severity="error",
                )
            )

    def _check_forbidden_claims(
        self,
        output_text: str,
        findings: list[QualityFinding],
    ) -> None:
        for phrase in rules.FORBIDDEN_BUSINESS_FACT_CLAIMS:
            if phrase in output_text:
                findings.append(
                    QualityFinding(
                        code="forbidden_business_fact_claim",
                        message=f"输出不得声称已经保存、发布、确认或修改事实：{phrase}",
                        severity="error",
                    )
                )
                return

    def _check_cervical_risk(
        self,
        input_text: str,
        output: Mapping[str, Any],
        findings: list[QualityFinding],
    ) -> None:
        if _contains_any(input_text, rules.CERVICAL_RISK_KEYWORDS) and _has_unsafe_keyword(
            output,
            rules.CERVICAL_HIGH_LOAD_KEYWORDS,
        ):
            findings.append(
                QualityFinding(
                    code="heavy_neck_loading_for_cervical_issue",
                    message="存在颈椎风险时，草案不得建议颈部高负荷、冲击性或复杂动作。",
                )
            )

    def _check_swimming_risk(
        self,
        input_text: str,
        output: Mapping[str, Any],
        findings: list[QualityFinding],
    ) -> None:
        if _contains_any(
            input_text,
            rules.SWIM_CHOKING_RISK_KEYWORDS,
        ) and _has_unsafe_keyword(output, rules.AGGRESSIVE_SWIMMING_KEYWORDS):
            findings.append(
                QualityFinding(
                    code="aggressive_swimming_for_choking_risk",
                    message="存在游泳呛水或换气困难时，草案不得建议长距离连续或高强度游泳。",
                )
            )

    def _check_low_fitness_risk(
        self,
        input_text: str,
        output: Mapping[str, Any],
        today_action: Any,
        findings: list[QualityFinding],
    ) -> None:
        if not _contains_any(input_text, rules.LOW_FITNESS_RISK_KEYWORDS):
            return
        if _has_unsafe_keyword(output, rules.LOW_FITNESS_AGGRESSIVE_KEYWORDS):
            findings.append(
                QualityFinding(
                    code="hiit_for_low_fitness",
                    message="基础体能很低时，草案不得建议 HIIT、Tabata、高强度间歇或长时间训练。",
                )
            )
        if _has_unsafe_keyword(today_action, rules.TODAY_TOO_LARGE_KEYWORDS):
            findings.append(
                QualityFinding(
                    code="today_action_too_large",
                    message="今日行动必须足够小，不能明显超过当前基础能力。",
                )
            )

    def _check_extreme_weight_loss_request(
        self,
        input_text: str,
        findings: list[QualityFinding],
    ) -> None:
        if _contains_any(input_text, rules.EXTREME_WEIGHT_LOSS_REQUEST_KEYWORDS):
            findings.append(
                QualityFinding(
                    code="extreme_weight_loss_request_needs_safety_boundary",
                    message="极端减重或要求狠练的请求必须保守处理，并保留安全提醒。",
                )
            )

    def _check_blood_pressure_risk(
        self,
        input_text: str,
        output: Mapping[str, Any],
        findings: list[QualityFinding],
    ) -> None:
        if _contains_any(
            input_text,
            rules.BLOOD_PRESSURE_RISK_KEYWORDS,
        ) and _has_unsafe_keyword(output, rules.BLOOD_PRESSURE_AGGRESSIVE_KEYWORDS):
            findings.append(
                QualityFinding(
                    code="high_intensity_for_blood_pressure_risk",
                    message="存在血压偏高倾向时，草案不得建议冲强度、憋气、极限力量或高压训练。",
                )
            )

    def _check_week_one_focus(
        self,
        weekly_text: str,
        findings: list[QualityFinding],
    ) -> None:
        if weekly_text and not _contains_any(
            weekly_text,
            rules.WEEK_ONE_CONSERVATIVE_KEYWORDS,
        ):
            findings.append(
                QualityFinding(
                    code="missing_conservative_week1_focus",
                    message="首周计划应以适应、恢复、低强度、动作质量或呼吸适应为主。",
                )
            )

    def _check_weekly_downgrade_or_stop(
        self,
        weekly_text: str,
        findings: list[QualityFinding],
    ) -> None:
        if weekly_text and not _contains_any(
            weekly_text,
            rules.WEEKLY_DOWNGRADE_OR_STOP_KEYWORDS,
        ):
            findings.append(
                QualityFinding(
                    code="missing_weekly_downgrade_or_stop_condition",
                    message="WeeklyPlanDraft 必须包含降级方案或停止条件。",
                )
            )

    def _check_today_minimum_standard(
        self,
        today_text: str,
        findings: list[QualityFinding],
    ) -> None:
        if today_text and not _contains_any(
            today_text,
            rules.TODAY_MINIMUM_STANDARD_KEYWORDS,
        ):
            findings.append(
                QualityFinding(
                    code="missing_today_minimum_completion_standard",
                    message="TodayActionDraft 必须包含最低完成标准。",
                )
            )


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    """大小写不敏感关键词匹配，兼容中英文。"""
    normalized = text.lower()
    return any(keyword.lower() in normalized for keyword in keywords)


def _has_unsafe_keyword(value: Any, keywords: Iterable[str]) -> bool:
    """匹配危险建议，忽略 exclusions、停止条件和禁止项中的危险词。"""
    return _has_unsafe_recommendation(value, keywords, path=())


def _has_unsafe_recommendation(
    value: Any,
    keywords: Iterable[str],
    path: tuple[str, ...],
) -> bool:
    """递归判断危险词是否出现在推荐或执行语境中。"""
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            next_path = (*path, key_text)
            if _is_safe_context_key(key_text):
                continue
            if _has_unsafe_recommendation(item, keywords, next_path):
                return True
        return False
    if isinstance(value, list | tuple | set):
        return any(_has_unsafe_recommendation(item, keywords, path) for item in value)
    if value is None:
        return False

    text = str(value)
    for line in _split_lines(text):
        for keyword in keywords:
            if keyword.lower() not in line.lower():
                continue
            if _is_negated(line, keyword) or _is_safe_context_path(path):
                continue
            if _is_recommendation_context(line, path):
                return True
    return False


def _is_safe_context_key(key: str) -> bool:
    """识别排除、禁止、停止和安全提醒字段。"""
    normalized = key.lower().replace("_", "").replace("-", "")
    return any(
        token in normalized
        for token in (
            "exclusion",
            "exclude",
            "donot",
            "dont",
            "avoid",
            "forbid",
            "forbidden",
            "stopcondition",
            "stoprule",
            "safetynote",
            "safety",
            "warning",
            "contraindication",
        )
    ) or key in ("排除", "不做", "禁止", "避免", "停止条件", "安全提醒")


def _is_safe_context_path(path: tuple[str, ...]) -> bool:
    """判断当前字段路径是否位于安全/排除语境中。"""
    return any(_is_safe_context_key(key) for key in path)


def _is_recommendation_context(line: str, path: tuple[str, ...]) -> bool:
    """判断当前文本是否是在建议、安排或执行语境中。"""
    lowered = line.lower()
    if any(
        keyword in lowered
        for keyword in (
            "推荐",
            "建议",
            "计划",
            "执行",
            "安排",
            "做",
            "练",
            "训练",
            "prescription",
            "action",
            "workout",
        )
    ):
        return True
    normalized_path = tuple(key.lower().replace("_", "").replace("-", "") for key in path)
    return any(
        key in normalized_path
        for key in (
            "actions",
            "items",
            "detail",
            "focus",
            "prescription",
            "weeklyplandraft",
            "todayactiondraft",
            "programdraft",
            "phasedraft",
        )
    )


def _is_negated(line: str, keyword: str) -> bool:
    """判断关键词附近是否处于否定或禁止语境。"""
    lowered = line.lower()
    keyword_index = lowered.find(keyword.lower())
    if keyword_index < 0:
        return False
    prefix = lowered[max(0, keyword_index - 32):keyword_index]
    suffix = lowered[keyword_index:keyword_index + len(keyword) + 16]
    nearby = f"{prefix}{suffix}"
    return any(negation.lower() in nearby for negation in rules.NEGATION_KEYWORDS)


def _split_lines(text: str) -> list[str]:
    """按常见分隔符拆分文本片段。"""
    separators = "\n。；;，,"
    lines = [text]
    for separator in separators:
        next_lines: list[str] = []
        for line in lines:
            next_lines.extend(part.strip() for part in line.split(separator))
        lines = next_lines
    return [line for line in lines if line]


def _flatten_text(value: Any) -> str:
    """递归展开结构化对象为文本。"""
    parts: list[str] = []
    if isinstance(value, Mapping):
        for key in sorted(value.keys(), key=str):
            parts.append(str(key))
            parts.append(_flatten_text(value[key]))
    elif isinstance(value, list | tuple | set):
        for item in value:
            parts.append(_flatten_text(item))
    elif value is not None:
        parts.append(str(value))
    return "\n".join(part for part in parts if part)
