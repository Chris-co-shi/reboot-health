export type Sex = 'MALE' | 'FEMALE' | 'OTHER' | 'UNSPECIFIED';

export type ConstraintType =
  | 'HYPERTENSION'
  | 'CERVICAL_LIMITATION'
  | 'SHOULDER_NECK_DISCOMFORT'
  | 'LOWER_BACK_STRAIN'
  | 'HIP_MOBILITY_LIMITATION'
  | 'FOOT_SOLE_ISSUE'
  | 'ACHILLES_DISCOMFORT'
  | 'FORBIDDEN_MOVEMENT'
  | 'TRAINING_PRECAUTION'
  | 'OTHER';

export type BodyRegion =
  | 'CARDIOVASCULAR'
  | 'CERVICAL_SPINE'
  | 'SHOULDER_NECK'
  | 'LOWER_BACK'
  | 'HIP'
  | 'FOOT_SOLE'
  | 'ACHILLES_TENDON'
  | 'FULL_BODY'
  | 'OTHER';

export type ConstraintSeverity = 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type ConstraintSourceType = 'USER_REPORTED' | 'DOCTOR_ADVICE' | 'MEDICAL_REPORT' | 'MEASUREMENT' | 'OTHER';
export type ConstraintStatus = 'ACTIVE' | 'INACTIVE' | 'RESOLVED' | 'ARCHIVED';

export type GoalType =
  | 'WEIGHT'
  | 'WAIST'
  | 'TRAINING_HABIT'
  | 'AEROBIC_CAPACITY'
  | 'STRENGTH'
  | 'SWIMMING'
  | 'BASKETBALL_CONDITIONING'
  | 'SLEEP'
  | 'OTHER';

export type GoalUnit =
  | 'KG'
  | 'CM'
  | 'SESSIONS_PER_WEEK'
  | 'MINUTES'
  | 'MINUTES_PER_DAY'
  | 'METERS'
  | 'LAPS'
  | 'SCORE'
  | 'PERCENT'
  | 'NONE';

export type GoalStatus = 'ACTIVE' | 'PAUSED' | 'COMPLETED' | 'CANCELLED' | 'ARCHIVED';

export interface ApiFieldError {
  field: string;
  message: string;
}

export interface ApiErrorResponse {
  code: string;
  message: string;
  fields?: ApiFieldError[];
  timestamp?: string;
}

export interface UserProfile {
  id: string;
  displayName: string;
  sex: Sex;
  birthDate?: string;
  heightCm?: number;
  baselineWeightKg?: number;
  timezone: string;
  createdAt: string;
  updatedAt: string;
}

export type UserProfileRequest = Omit<UserProfile, 'id' | 'createdAt' | 'updatedAt'>;

export interface HealthConstraint {
  id: string;
  constraintType: ConstraintType;
  bodyRegion: BodyRegion;
  severity: ConstraintSeverity;
  title: string;
  description?: string;
  sourceType: ConstraintSourceType;
  sourceNote?: string;
  status: ConstraintStatus;
  effectiveFrom?: string;
  effectiveTo?: string;
  archiveReason?: string;
  createdAt: string;
  updatedAt: string;
  archivedAt?: string;
}

export type HealthConstraintRequest = Pick<
  HealthConstraint,
  | 'constraintType'
  | 'bodyRegion'
  | 'severity'
  | 'title'
  | 'description'
  | 'sourceType'
  | 'sourceNote'
  | 'effectiveFrom'
  | 'effectiveTo'
>;

export interface Goal {
  id: string;
  goalType: GoalType;
  title: string;
  targetValue?: number;
  unit: GoalUnit;
  baselineValue?: number;
  targetDate?: string;
  status: GoalStatus;
  priority: number;
  archiveReason?: string;
  createdAt: string;
  updatedAt: string;
  archivedAt?: string;
}

export type GoalRequest = Pick<
  Goal,
  'goalType' | 'title' | 'targetValue' | 'unit' | 'baselineValue' | 'targetDate' | 'priority'
>;
