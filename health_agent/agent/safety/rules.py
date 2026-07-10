"""Planning Quality Gate 的规则常量。

这些规则是保守关键词门禁，不替代确定性安全规则，也不把 AI 输出升级为已确认
健康事实。
"""

from __future__ import annotations


FORBIDDEN_BUSINESS_FACT_CLAIMS = (
    "已保存",
    "保存成功",
    "已发布",
    "发布成功",
    "已确认",
    "确认成功",
    "已生效",
    "已经生效",
    "已写入",
    "写入数据库",
    "已更新业务事实",
    "已修改业务事实",
)

NEGATION_KEYWORDS = (
    "不",
    "不得",
    "不要",
    "禁止",
    "避免",
    "不能",
    "无须",
    "无需",
    "取消",
    "停止",
    "do not",
    "don't",
    "avoid",
    "forbid",
    "without",
)

CERVICAL_RISK_KEYWORDS = (
    "颈椎",
    "脖子",
    "颈部",
    "颈肩",
    "cervical",
    "neck",
)

CERVICAL_HIGH_LOAD_KEYWORDS = (
    "颈桥",
    "颈部负重",
    "头颈负重",
    "颈后推举",
    "颈后下拉",
    "颈后深蹲",
    "杠铃后背深蹲",
    "头倒立",
    "倒立撑",
    "猛烈甩头",
    "高负荷颈",
    "大重量卧推",
    "大重量深蹲",
    "大重量硬拉",
    "每天大重量",
    "冲重量",
)

SWIM_CHOKING_RISK_KEYWORDS = (
    "呛水",
    "不会换气",
    "换气困难",
    "呼吸困难",
    "chok",
    "breathing difficulty",
)

AGGRESSIVE_SWIMMING_KEYWORDS = (
    "长距离连续游",
    "连续游1000",
    "连续游 1000",
    "连续游800",
    "连续游 800",
    "高强度游泳",
    "冲刺游",
    "不休息游",
    "持续游泳30分钟",
    "持续游泳 30 分钟",
    "蝶泳训练",
    "硬游25米",
    "硬游 25 米",
)

LOW_FITNESS_RISK_KEYWORDS = (
    "体能差",
    "体能很差",
    "两个回合就喘",
    "篮球两个回合",
    "喘",
    "久坐",
    "低体能",
    "low fitness",
)

LOW_FITNESS_AGGRESSIVE_KEYWORDS = (
    "HIIT",
    "Tabata",
    "高强度间歇",
    "高强度循环",
    "冲刺间歇",
    "极限冲刺",
    "长时间训练",
    "90分钟训练",
    "90 分钟训练",
    "2小时训练",
    "2 小时训练",
)

EXTREME_WEIGHT_LOSS_REQUEST_KEYWORDS = (
    "30天瘦20斤",
    "30 天瘦 20 斤",
    "一个月瘦20斤",
    "一个月瘦 20 斤",
    "快速降体重",
    "快速减重",
    "狠一点",
    "每天练HIIT",
    "每天练 HIIT",
)

BLOOD_PRESSURE_RISK_KEYWORDS = (
    "血压",
    "高血压",
    "140/90",
    "145/95",
    "135/85",
    "blood pressure",
    "hypertension",
)

BLOOD_PRESSURE_AGGRESSIVE_KEYWORDS = (
    "冲强度",
    "高强度训练",
    "高强度间歇",
    "憋气",
    "屏息",
    "1RM",
    "极限力量",
    "最大重量",
    "冲重量",
    "大重量冲刺",
    "高压训练",
    "力竭测试",
)

WEEK_ONE_CONSERVATIVE_KEYWORDS = (
    "首周",
    "第1周",
    "第 1 周",
    "适应",
    "恢复",
    "低强度",
    "动作质量",
    "呼吸",
    "呼气",
    "RPE 3-6",
    "RPE3-6",
    "保留余力",
)

WEEKLY_DOWNGRADE_OR_STOP_KEYWORDS = (
    "降级",
    "停止",
    "取消训练",
    "减少",
    "重复当前周",
    "不满足升级条件",
    "疼痛",
    "胸闷",
    "头晕",
    "stopRule",
    "停止条件",
)

TODAY_MINIMUM_STANDARD_KEYWORDS = (
    "最低完成",
    "最小完成",
    "最低标准",
    "至少",
    "只做",
    "仅做",
    "基线记录",
    "10分钟恢复",
    "10 分钟恢复",
    "minimum",
)

TODAY_TOO_LARGE_KEYWORDS = (
    "HIIT",
    "Tabata",
    "高强度间歇",
    "冲刺",
    "60分钟训练",
    "60 分钟训练",
    "90分钟",
    "90 分钟",
    "2小时",
    "2 小时",
    "1000米",
    "1000 米",
)
