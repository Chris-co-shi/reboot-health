from __future__ import annotations

from typing import Any, Iterable, Mapping

from agent_runtime.providers.base import BaseModelProvider
from agent_runtime.schema import PLANNING_SCHEMA_VERSION


class MockProvider(BaseModelProvider):
    """Deterministic provider used by default for stable local tests."""

    provider_name = "mock"

    def generate_initial_planning(
        self,
        prompt: str,
        planning_input: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        del prompt
        risks = _detect_risks(planning_input)
        return {
            "schemaVersion": PLANNING_SCHEMA_VERSION,
            "summary": "根据当前输入生成待确认的首周计划草案与今日行动草案，等待后续事实校验、用户确认和正式流程处理。",
            "understandingCandidates": _understanding_candidates(planning_input, risks),
            "healthConstraintCandidates": _health_constraint_candidates(
                planning_input,
                risks,
            ),
            "goalCandidates": _goal_candidates(planning_input),
            "programDraft": _program_draft(),
            "phaseDraft": _phase_draft(),
            "weeklyPlanDraft": _weekly_plan_draft(),
            "todayActionDraft": _today_action_draft(planning_input),
            "safetyNotes": _safety_notes(risks),
            "questions": _questions(risks),
            "requiresUserConfirmation": True,
        }


def _understanding_candidates(
    planning_input: Mapping[str, Any],
    risks: set[str],
) -> list[dict[str, Any]]:
    user_text = str(planning_input.get("userText") or "").strip()
    candidates: list[dict[str, Any]] = []
    if user_text:
        candidates.append(
            {
                "type": "user_health_status",
                "text": user_text,
                "confidence": "medium",
                "candidate": True,
            }
        )
    else:
        candidates.append(
            {
                "type": "missing_user_health_status",
                "text": "用户自然语言健康状态为空，需要补充当前状态和可训练时间。",
                "confidence": "high",
                "candidate": True,
            }
        )

    profile = planning_input.get("profile") or {}
    if isinstance(profile, Mapping) and profile:
        candidates.append(
            {
                "type": "known_profile",
                "text": "已收到用户档案，将仅作为计划草案上下文。",
                "profileKeys": sorted(str(key) for key in profile.keys()),
                "confidence": "medium",
                "candidate": True,
            }
        )

    if "low_fitness" in risks:
        candidates.append(
            {
                "type": "fitness_baseline",
                "text": "输入提示基础体能较差，首周以恢复节奏、低强度和可持续记录为优先。",
                "confidence": "medium",
                "candidate": True,
            }
        )
    return candidates


def _health_constraint_candidates(
    planning_input: Mapping[str, Any],
    risks: set[str],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in _as_iterable(planning_input.get("knownHealthConstraints")):
        candidates.append(
            {
                "name": "已知健康约束候选",
                "detail": item,
                "source": "input",
                "candidate": True,
                "requiresUserConfirmation": True,
            }
        )

    if "neck" in risks:
        candidates.append(
            {
                "name": "颈椎友好训练约束",
                "rationale": "输入或档案提示颈椎问题，草案避免颈部负重、颈后动作、猛烈甩头和长时间抬头。",
                "severity": "caution",
                "candidate": True,
                "requiresUserConfirmation": True,
            }
        )
    if "swim_choking" in risks:
        candidates.append(
            {
                "name": "游泳呛水与水中安全约束",
                "rationale": "输入提示游泳换气或呛水风险，草案仅安排短距离技术练习并要求浅水区、同伴或救生员条件。",
                "severity": "caution",
                "candidate": True,
                "requiresUserConfirmation": True,
            }
        )
    if "blood_pressure" in risks:
        candidates.append(
            {
                "name": "血压偏高训练约束",
                "rationale": "输入或档案提示血压风险，草案避免冲强度，并要求训练前后记录血压和异常症状。",
                "severity": "caution",
                "candidate": True,
                "requiresUserConfirmation": True,
            }
        )
    if "low_fitness" in risks:
        candidates.append(
            {
                "name": "体能下降起步约束",
                "rationale": "首周不追求容量和速度，以 RPE 3-6、保留余力和动作质量为主。",
                "severity": "caution",
                "candidate": True,
                "requiresUserConfirmation": True,
            }
        )
    if not candidates:
        candidates.append(
            {
                "name": "低强度起步约束",
                "rationale": "缺少明确安全信息时，首周默认按保守强度生成草案。",
                "severity": "caution",
                "candidate": True,
                "requiresUserConfirmation": True,
            }
        )
    return candidates


def _goal_candidates(planning_input: Mapping[str, Any]) -> list[dict[str, Any]]:
    goals = list(_as_iterable(planning_input.get("goals")))
    candidates: list[dict[str, Any]] = []
    for goal in goals:
        candidates.append(
            {
                "name": "输入目标候选",
                "detail": goal,
                "candidate": True,
                "requiresUserConfirmation": True,
            }
        )
    if not candidates:
        candidates.extend(
            [
                {
                    "name": "恢复规律训练",
                    "horizon": "12周",
                    "candidate": True,
                    "requiresUserConfirmation": True,
                },
                {
                    "name": "提高基础有氧与肌耐力",
                    "horizon": "12周",
                    "candidate": True,
                    "requiresUserConfirmation": True,
                },
                {
                    "name": "降低腹部脂肪并改善颈肩髋核心控制",
                    "horizon": "12周",
                    "candidate": True,
                    "requiresUserConfirmation": True,
                },
            ]
        )
    return candidates


def _program_draft() -> dict[str, Any]:
    return {
        "name": "12周体能重建计划草案",
        "status": "draft_requires_confirmation",
        "authority": "python_candidate_only",
        "principles": [
            "第1-4周以 RPE 3-6 起步，不做到力竭。",
            "每次只调整一个变量：次数、组数、距离、时间或器械最小配重。",
            "漏练不补双倍训练，按下一次计划继续。",
            "器械重量不预设公斤数，用 RIR 3 或 RPE 规则选择并记录实际重量。",
        ],
        "boundaries": [
            "Python 只生成候选和草案。",
            "Java 后续负责事实保存、安全规则、用户确认和计划发布。",
        ],
    }


def _phase_draft() -> dict[str, Any]:
    return {
        "name": "基础重建期草案",
        "weekRange": "第1-4周",
        "focus": [
            "建立训练节奏",
            "恢复动作质量",
            "学习水中呼气和短距离换气",
            "控制颈肩、髋、核心和足踝",
        ],
        "intensityCap": "RPE 3-6",
        "progressionRule": "本周完成率、睡眠、症状、RPE、游泳呛水和慌乱均稳定后，下一周才考虑升级。",
        "status": "draft_requires_confirmation",
    }


def _weekly_plan_draft() -> dict[str, Any]:
    return {
        "name": "首周计划草案",
        "status": "draft_requires_confirmation",
        "intensityCap": "RPE 3-6",
        "days": [
            {
                "day": "周一",
                "focus": "徒手力量 A + 颈肩稳定",
                "items": [
                    _item("训练前记录", "血压、静息心率、颈肩不适评分", "如明显高于平时或有胸闷头晕，取消训练"),
                    _item("椅子深蹲", "2组 x 8次", "RPE 3-5，起身呼气"),
                    _item("高位俯卧撑", "2组 x 6次", "下巴微收，不伸头"),
                    _item("扶墙分腿蹲", "2组 x 6次/侧", "保持稳定，必要时减小幅度"),
                    _item("臀桥", "2组 x 10次", "不用脖子顶地"),
                    _item("Dead Bug", "2组 x 6次/侧", "后脑勺自然放地"),
                    _item("下巴回收 + 肩胛后收下沉", "各2组", "动作温和，不猛烈拉伸颈部"),
                ],
            },
            {
                "day": "周二",
                "focus": "游泳技术 + 水中有氧",
                "items": [
                    _item("浅水行走", "5分钟", "RPE 2-3"),
                    _item("扶池边水下呼气", "6组 x 5次", "慢吐泡，抬头吸气动作小"),
                    _item("短距离游", "10米 x 6趟", "每趟休息60-90秒，不硬游25米"),
                    _item("训练记录", "呛水次数、是否慌乱、颈部不适", "有救生员或同伴，浅水区进行"),
                ],
            },
            {
                "day": "周三",
                "focus": "健身房辅助训练",
                "items": [
                    _item("平地跑步机热身", "8分钟", "轻松走，不冲速度"),
                    _item("胸托划船", "2组 x 10次", "肩胛后收下沉，不耸肩"),
                    _item("中立握高位下拉", "2组 x 10次", "拉向上胸，不向颈后拉"),
                    _item("腿举", "2组 x 10次", "RIR 3，不憋气"),
                    _item("坐姿腿弯举", "2组 x 10次", "动作可控"),
                    _item("器械推胸", "2组 x 10次", "头颈中立，不顶重量"),
                    _item("Pallof Press", "2组 x 8次/侧", "抗旋核心，呼吸平稳"),
                    _item("平地走路冷身", "8分钟", "记录运动后5分钟心率"),
                ],
            },
            {
                "day": "周四",
                "focus": "恢复日",
                "items": [
                    _item("轻松步行", "20-30分钟或拆分完成", "保持能完整说话的强度"),
                    _item("每日10分钟恢复流程", "下巴回收、墙面滑手、髋屈肌和小腿拉伸、短脚、单脚平衡", "全程温和"),
                    _item("工作中断恢复", "每35分钟起身2分钟", "走动、下巴回收、肩胛后收下沉"),
                ],
            },
            {
                "day": "周五",
                "focus": "徒手力量 B + 走路间歇",
                "items": [
                    _item("坐站", "2组 x 8次", "RPE 3-5"),
                    _item("高位俯卧撑", "2组 x 6次", "下巴微收"),
                    _item("徒手髋铰链", "2组 x 8次", "脊柱中立"),
                    _item("低台阶上台", "2组 x 6次/侧", "选择低台阶，避免冲击"),
                    _item("侧卧抬腿", "2组 x 10次/侧", "骨盆稳定"),
                    _item("Bird Dog", "2组 x 6次/侧，保持3秒", "看向地面"),
                    _item("跪姿侧桥", "2组 x 10秒/侧", "头颈跟躯干一条线"),
                    _item("走路间歇", "慢走5分钟；快走1分钟+慢走2分钟 x 6；慢走5分钟", "不跑，不冲刺"),
                ],
            },
            {
                "day": "周六",
                "focus": "游泳技术 + 篮球低强度技术",
                "items": [
                    _item("游泳短距离技术", "10米 x 6趟", "充分休息，不硬游25米"),
                    _item("扶池边水下呼气", "6组 x 5次", "不甩头换气"),
                    _item("篮球原地技术", "10-15分钟", "原地运球、近距离定点投篮，不对抗"),
                    _item("记录", "呛水、慌乱、颈肩膝足不适", "任一症状加重则停止"),
                ],
            },
            {
                "day": "周日",
                "focus": "完全恢复和周复盘",
                "items": [
                    _item("轻松走路", "可选20分钟", "恢复优先"),
                    _item("周复盘", "完成率、睡眠、血压、RPE、疼痛和游泳呛水", "不满足升级条件则重复当前周"),
                ],
            },
        ],
    }


def _today_action_draft(planning_input: Mapping[str, Any]) -> dict[str, Any]:
    today = str(planning_input.get("today") or "启动日").strip() or "启动日"
    return {
        "name": "今日行动草案",
        "date": today,
        "status": "draft_requires_confirmation",
        "actions": [
            {
                "name": "基线记录",
                "detail": "记录体重、腰围、早晚血压、静息心率、颈肩腰膝足不适评分。",
                "stopRule": "如血压明显高于平时，或出现胸闷、头晕、异常心悸，取消训练。",
            },
            {
                "name": "10分钟恢复流程",
                "detail": "下巴回收、墙面滑手、髋屈肌拉伸、小腿拉伸、短脚训练和单脚平衡。",
                "stopRule": "出现放射痛、麻木、头晕、恶心或电击样感觉时停止。",
            },
            {
                "name": "低强度启动训练",
                "detail": "若身体状态稳定，执行首周周一徒手力量A；若疲劳或血压异常，仅做轻松步行。",
                "stopRule": "任何动作疼痛达到4分以上，或第二天明显加重，下一次同类训练量减少。",
            },
        ],
        "doNotDo": [
            "不做 HIIT、Tabata、极限冲刺或1RM测试。",
            "不做颈部负重、颈桥、颈后下拉、颈后推举或杠铃后背深蹲。",
            "游泳不硬凑25米，不持续抬头蛙泳，不蝶泳，不猛烈甩头换气。",
        ],
    }


def _item(name: str, prescription: str, note: str) -> dict[str, str]:
    return {
        "name": name,
        "prescription": prescription,
        "note": note,
    }


def _safety_notes(risks: set[str]) -> list[str]:
    notes = [
        "本输出只是候选和草案，需要用户确认，并由 Java 侧执行事实保存、安全规则、确认和发布流程。",
        "第1周强度控制在 RPE 3-6，力量训练每组保留约3次余力，不做到力竭。",
        "出现放射痛、麻木、握力下降、头晕、恶心、电击样感觉、走路不稳或症状明显加重时，立即停止。",
    ]
    if "neck" in risks:
        notes.append("颈椎风险按保守处理：保持颈部中立，避免颈部负重、颈后动作、猛烈拉伸和长时间抬头。")
    else:
        notes.append("即使未明确提供颈椎信息，首周草案也默认采用颈椎友好动作。")
    if "swim_choking" in risks:
        notes.append("游泳呛水风险按保守处理：浅水区、有救生员或同伴、短距离、充分休息，不硬游25米。")
    if "blood_pressure" in risks:
        notes.append("血压风险按保守处理：训练前后记录，异常升高或胸闷头晕时取消训练。")
    if "low_fitness" in risks:
        notes.append("体能差按保守处理：先恢复节奏和动作质量，不用篮球或跑步冲心肺。")
    return notes


def _questions(risks: set[str]) -> list[str]:
    questions = [
        "最近7天早晚血压大致范围是多少？是否有胸闷、头晕或异常心悸？",
        "颈部、肩、手臂或手指是否出现放射痛、麻木、握力下降或电击样感觉？",
        "本周可训练日期、健身房条件和游泳池安全条件是什么？",
    ]
    if "swim_choking" in risks:
        questions.append("游泳时最近一次呛水发生在什么情境？是否能在浅水区稳定水下呼气？")
    if "low_fitness" in risks:
        questions.append("快走10分钟后的喘息程度和运动后5分钟心率恢复情况如何？")
    return questions


def _detect_risks(planning_input: Mapping[str, Any]) -> set[str]:
    text = _flatten_text(planning_input).lower()
    risks: set[str] = set()
    if any(keyword in text for keyword in ("颈椎", "脖子", "颈部", "cervical", "neck")):
        risks.add("neck")
    if any(keyword in text for keyword in ("呛水", "不会换气", "游泳", "swim", "chok")):
        risks.add("swim_choking")
    if any(keyword in text for keyword in ("血压", "高血压", "amlodipine", "氨氯地平", "135", "140", "145")):
        risks.add("blood_pressure")
    if any(keyword in text for keyword in ("体能差", "喘", "肥胖", "超重", "久坐", "走几步", "basketball")):
        risks.add("low_fitness")
    return risks


def _flatten_text(value: Any) -> str:
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
    return " ".join(part for part in parts if part)


def _as_iterable(value: Any) -> Iterable[Any]:
    if value is None:
        return []
    if isinstance(value, list | tuple):
        return value
    return [value]
