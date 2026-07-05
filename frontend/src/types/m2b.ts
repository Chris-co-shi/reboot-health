import type { GoalStatus } from '@/types/m2a';

export type PlanVersionStatus = 'DRAFT' | 'CONFIRMED' | 'SUPERSEDED' | 'CANCELLED';

export type PlanItemType =
  | 'BODYWEIGHT'
  | 'GYM'
  | 'SWIMMING'
  | 'BASKETBALL'
  | 'RECOVERY'
  | 'REST'
  | 'CARDIO'
  | 'NUTRITION'
  | 'MEASUREMENT'
  | 'OTHER';

export interface GoalSummarySnapshot {
  goalId: string;
  title?: string;
  goalType?: string;
  status?: GoalStatus;
  targetValue?: number;
  unit?: string;
  baselineValue?: number;
  targetDate?: string;
}

export interface HealthConstraintSnapshotItem {
  id: string;
  constraintType: string;
  bodyRegion: string;
  severity: string;
  title: string;
  description?: string;
  sourceType: string;
  sourceNote?: string;
  status: string;
  effectiveFrom?: string;
  effectiveTo?: string;
}

export interface HealthConstraintSnapshot {
  schemaVersion: number;
  generatedAt: string;
  items: HealthConstraintSnapshotItem[];
}

export interface Plan {
  id: string;
  title: string;
  summary?: string;
  createdAt: string;
  updatedAt: string;
}

export interface PlanItem {
  id: string;
  dayId: string;
  goalId?: string;
  itemType: PlanItemType;
  title: string;
  description?: string;
  plannedSets?: number;
  plannedReps?: number;
  plannedDurationMinutes?: number;
  plannedDistanceMeters?: number;
  plannedRpe?: number;
  sortOrder: number;
  createdAt: string;
  updatedAt: string;
}

export interface PlanDay {
  id: string;
  versionId: string;
  dayDate: string;
  title: string;
  note?: string;
  sortOrder: number;
  createdAt: string;
  updatedAt: string;
  items: PlanItem[];
}

export interface PlanVersion {
  id: string;
  planId: string;
  versionNumber: number;
  periodRevision: number;
  status: PlanVersionStatus;
  startDate: string;
  endDate: string;
  title: string;
  summary?: string;
  copiedFromVersionId?: string;
  supersedesVersionId?: string;
  revision: number;
  confirmedAt?: string;
  supersededAt?: string;
  cancelledAt?: string;
  cancelReason?: string;
  createdAt: string;
  updatedAt: string;
  goalIds: string[];
  goals: GoalSummarySnapshot[];
  healthConstraints: HealthConstraintSnapshot;
  days: PlanDay[];
}

export type PlanVersionSummary = Omit<
  PlanVersion,
  | 'goalIds'
  | 'goals'
  | 'healthConstraints'
  | 'days'
  | 'summary'
  | 'copiedFromVersionId'
  | 'supersedesVersionId'
  | 'supersededAt'
  | 'cancelledAt'
  | 'cancelReason'
>;

export interface CreatePlanRequest {
  title: string;
  summary?: string;
}

export interface CreateDraftRequest {
  startDate: string;
  title: string;
  summary?: string;
  goalIds: string[];
}

export interface UpdateVersionRequest {
  title: string;
  summary?: string;
  goalIds: string[];
  expectedRevision: number;
}

export interface CopyVersionRequest {
  startDate: string;
  title?: string;
  summary?: string;
  expectedSourceStatus?: PlanVersionStatus;
}

export interface CancelVersionRequest {
  cancelReason: string;
  expectedRevision: number;
}

export interface ConfirmVersionRequest {
  expectedRevision: number;
}

export interface PlanVersionPreview {
  detail: PlanVersion;
  goals: GoalSummarySnapshot[];
  healthConstraints: HealthConstraintSnapshot;
  validationIssues: string[];
  canConfirm: boolean;
}

export interface SaveDayRequest {
  dayDate: string;
  title: string;
  note?: string;
  sortOrder: number;
  expectedRevision: number;
}

export interface SaveItemRequest {
  goalId?: string;
  itemType: PlanItemType;
  title: string;
  description?: string;
  plannedSets?: number;
  plannedReps?: number;
  plannedDurationMinutes?: number;
  plannedDistanceMeters?: number;
  plannedRpe?: number;
  sortOrder: number;
  expectedRevision: number;
}

export interface ActiveGoalOption {
  id: string;
  title: string;
  status: GoalStatus;
}
