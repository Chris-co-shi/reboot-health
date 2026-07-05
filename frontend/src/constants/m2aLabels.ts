import type {
  BodyRegion,
  ConstraintSeverity,
  ConstraintSourceType,
  ConstraintStatus,
  ConstraintType,
  GoalStatus,
  GoalType,
  GoalUnit,
  Sex,
} from '@/types/m2a';

export interface SelectOption<T extends string> {
  label: string;
  value: T;
}

export const sexLabels: Record<Sex, string> = {
  MALE: '男',
  FEMALE: '女',
  OTHER: '其他',
  UNSPECIFIED: '未指定',
};

export const sexOptions: Array<SelectOption<Sex>> = [
  { label: sexLabels.MALE, value: 'MALE' },
  { label: sexLabels.FEMALE, value: 'FEMALE' },
  { label: sexLabels.OTHER, value: 'OTHER' },
  { label: sexLabels.UNSPECIFIED, value: 'UNSPECIFIED' },
];

export const constraintTypeLabels: Record<ConstraintType, string> = {
  HYPERTENSION: '血压相关限制',
  CERVICAL_LIMITATION: '颈椎限制',
  SHOULDER_NECK_DISCOMFORT: '肩颈不适',
  LOWER_BACK_STRAIN: '下背劳损',
  HIP_MOBILITY_LIMITATION: '髋活动受限',
  FOOT_SOLE_ISSUE: '足底问题',
  ACHILLES_DISCOMFORT: '跟腱不适',
  FORBIDDEN_MOVEMENT: '禁止动作',
  TRAINING_PRECAUTION: '训练注意事项',
  OTHER: '其他',
};

export const constraintTypeOptions: Array<SelectOption<ConstraintType>> = [
  { label: constraintTypeLabels.HYPERTENSION, value: 'HYPERTENSION' },
  { label: constraintTypeLabels.CERVICAL_LIMITATION, value: 'CERVICAL_LIMITATION' },
  { label: constraintTypeLabels.SHOULDER_NECK_DISCOMFORT, value: 'SHOULDER_NECK_DISCOMFORT' },
  { label: constraintTypeLabels.LOWER_BACK_STRAIN, value: 'LOWER_BACK_STRAIN' },
  { label: constraintTypeLabels.HIP_MOBILITY_LIMITATION, value: 'HIP_MOBILITY_LIMITATION' },
  { label: constraintTypeLabels.FOOT_SOLE_ISSUE, value: 'FOOT_SOLE_ISSUE' },
  { label: constraintTypeLabels.ACHILLES_DISCOMFORT, value: 'ACHILLES_DISCOMFORT' },
  { label: constraintTypeLabels.FORBIDDEN_MOVEMENT, value: 'FORBIDDEN_MOVEMENT' },
  { label: constraintTypeLabels.TRAINING_PRECAUTION, value: 'TRAINING_PRECAUTION' },
  { label: constraintTypeLabels.OTHER, value: 'OTHER' },
];

export const bodyRegionLabels: Record<BodyRegion, string> = {
  CARDIOVASCULAR: '心肺/循环',
  CERVICAL_SPINE: '颈椎',
  SHOULDER_NECK: '肩颈',
  LOWER_BACK: '下背',
  HIP: '髋',
  FOOT_SOLE: '足底',
  ACHILLES_TENDON: '跟腱',
  FULL_BODY: '全身',
  OTHER: '其他',
};

export const bodyRegionOptions: Array<SelectOption<BodyRegion>> = [
  { label: bodyRegionLabels.CARDIOVASCULAR, value: 'CARDIOVASCULAR' },
  { label: bodyRegionLabels.CERVICAL_SPINE, value: 'CERVICAL_SPINE' },
  { label: bodyRegionLabels.SHOULDER_NECK, value: 'SHOULDER_NECK' },
  { label: bodyRegionLabels.LOWER_BACK, value: 'LOWER_BACK' },
  { label: bodyRegionLabels.HIP, value: 'HIP' },
  { label: bodyRegionLabels.FOOT_SOLE, value: 'FOOT_SOLE' },
  { label: bodyRegionLabels.ACHILLES_TENDON, value: 'ACHILLES_TENDON' },
  { label: bodyRegionLabels.FULL_BODY, value: 'FULL_BODY' },
  { label: bodyRegionLabels.OTHER, value: 'OTHER' },
];

export const constraintSeverityLabels: Record<ConstraintSeverity, string> = {
  INFO: '信息',
  LOW: '低',
  MEDIUM: '中',
  HIGH: '高',
  CRITICAL: '严重',
};

export const constraintSeverityOptions: Array<SelectOption<ConstraintSeverity>> = [
  { label: constraintSeverityLabels.INFO, value: 'INFO' },
  { label: constraintSeverityLabels.LOW, value: 'LOW' },
  { label: constraintSeverityLabels.MEDIUM, value: 'MEDIUM' },
  { label: constraintSeverityLabels.HIGH, value: 'HIGH' },
  { label: constraintSeverityLabels.CRITICAL, value: 'CRITICAL' },
];

export const constraintSourceTypeLabels: Record<ConstraintSourceType, string> = {
  USER_REPORTED: '用户描述',
  DOCTOR_ADVICE: '专业建议',
  MEDICAL_REPORT: '检查报告',
  MEASUREMENT: '测量记录',
  OTHER: '其他',
};

export const constraintSourceTypeOptions: Array<SelectOption<ConstraintSourceType>> = [
  { label: constraintSourceTypeLabels.USER_REPORTED, value: 'USER_REPORTED' },
  { label: constraintSourceTypeLabels.DOCTOR_ADVICE, value: 'DOCTOR_ADVICE' },
  { label: constraintSourceTypeLabels.MEDICAL_REPORT, value: 'MEDICAL_REPORT' },
  { label: constraintSourceTypeLabels.MEASUREMENT, value: 'MEASUREMENT' },
  { label: constraintSourceTypeLabels.OTHER, value: 'OTHER' },
];

export const constraintStatusLabels: Record<ConstraintStatus, string> = {
  ACTIVE: '有效',
  INACTIVE: '停用',
  RESOLVED: '已解决',
  ARCHIVED: '已归档',
};

export const goalTypeLabels: Record<GoalType, string> = {
  WEIGHT: '体重',
  WAIST: '腰围',
  TRAINING_HABIT: '训练习惯',
  AEROBIC_CAPACITY: '有氧能力',
  STRENGTH: '力量',
  SWIMMING: '游泳',
  BASKETBALL_CONDITIONING: '篮球体能',
  SLEEP: '睡眠',
  OTHER: '其他',
};

export const goalTypeOptions: Array<SelectOption<GoalType>> = [
  { label: goalTypeLabels.WEIGHT, value: 'WEIGHT' },
  { label: goalTypeLabels.WAIST, value: 'WAIST' },
  { label: goalTypeLabels.TRAINING_HABIT, value: 'TRAINING_HABIT' },
  { label: goalTypeLabels.AEROBIC_CAPACITY, value: 'AEROBIC_CAPACITY' },
  { label: goalTypeLabels.STRENGTH, value: 'STRENGTH' },
  { label: goalTypeLabels.SWIMMING, value: 'SWIMMING' },
  { label: goalTypeLabels.BASKETBALL_CONDITIONING, value: 'BASKETBALL_CONDITIONING' },
  { label: goalTypeLabels.SLEEP, value: 'SLEEP' },
  { label: goalTypeLabels.OTHER, value: 'OTHER' },
];

export const goalUnitLabels: Record<GoalUnit, string> = {
  KG: '千克',
  CM: '厘米',
  SESSIONS_PER_WEEK: '次/周',
  MINUTES: '分钟',
  MINUTES_PER_DAY: '分钟/天',
  METERS: '米',
  LAPS: '趟',
  REPETITIONS: '次数',
  SECONDS: '秒',
  SCORE: '评分',
  PERCENT: '百分比',
  NONE: '无数值',
};

export const goalUnitOptions: Array<SelectOption<GoalUnit>> = [
  { label: goalUnitLabels.KG, value: 'KG' },
  { label: goalUnitLabels.CM, value: 'CM' },
  { label: goalUnitLabels.SESSIONS_PER_WEEK, value: 'SESSIONS_PER_WEEK' },
  { label: goalUnitLabels.MINUTES, value: 'MINUTES' },
  { label: goalUnitLabels.MINUTES_PER_DAY, value: 'MINUTES_PER_DAY' },
  { label: goalUnitLabels.METERS, value: 'METERS' },
  { label: goalUnitLabels.LAPS, value: 'LAPS' },
  { label: goalUnitLabels.REPETITIONS, value: 'REPETITIONS' },
  { label: goalUnitLabels.SECONDS, value: 'SECONDS' },
  { label: goalUnitLabels.SCORE, value: 'SCORE' },
  { label: goalUnitLabels.PERCENT, value: 'PERCENT' },
  { label: goalUnitLabels.NONE, value: 'NONE' },
];

export const goalStatusLabels: Record<GoalStatus, string> = {
  ACTIVE: '进行中',
  PAUSED: '已暂停',
  COMPLETED: '已完成',
  CANCELLED: '已取消',
  ARCHIVED: '已归档',
};

export const allowedGoalUnits: Record<GoalType, GoalUnit[]> = {
  WEIGHT: ['KG'],
  WAIST: ['CM'],
  TRAINING_HABIT: ['SESSIONS_PER_WEEK'],
  AEROBIC_CAPACITY: ['MINUTES', 'SECONDS', 'SCORE', 'PERCENT'],
  STRENGTH: ['REPETITIONS', 'SECONDS', 'SCORE', 'PERCENT'],
  SWIMMING: ['METERS', 'LAPS', 'MINUTES', 'SECONDS'],
  BASKETBALL_CONDITIONING: ['MINUTES', 'SECONDS', 'SCORE', 'PERCENT'],
  SLEEP: ['MINUTES', 'MINUTES_PER_DAY'],
  OTHER: ['NONE', 'KG', 'CM', 'SESSIONS_PER_WEEK', 'MINUTES', 'MINUTES_PER_DAY', 'METERS', 'LAPS', 'REPETITIONS', 'SECONDS', 'SCORE', 'PERCENT'],
};

export function optionsForGoalType(goalType: GoalType): Array<SelectOption<GoalUnit>> {
  const allowed = allowedGoalUnits[goalType];
  return goalUnitOptions.filter((option) => allowed.includes(option.value));
}
