import type { PlanItemType, PlanVersionStatus } from '@/types/m2b';
import type { SelectOption } from '@/constants/m2aLabels';

export const planVersionStatusLabels: Record<PlanVersionStatus, string> = {
  DRAFT: '草案',
  CONFIRMED: '已确认',
  SUPERSEDED: '已替代',
  CANCELLED: '已取消',
};

export const planItemTypeLabels: Record<PlanItemType, string> = {
  BODYWEIGHT: '徒手',
  GYM: '健身房',
  SWIMMING: '游泳',
  BASKETBALL: '篮球',
  RECOVERY: '恢复',
  REST: '休息',
  OTHER: '其他',
};

export const planItemTypeOptions: Array<SelectOption<PlanItemType>> = [
  { label: planItemTypeLabels.BODYWEIGHT, value: 'BODYWEIGHT' },
  { label: planItemTypeLabels.GYM, value: 'GYM' },
  { label: planItemTypeLabels.SWIMMING, value: 'SWIMMING' },
  { label: planItemTypeLabels.BASKETBALL, value: 'BASKETBALL' },
  { label: planItemTypeLabels.RECOVERY, value: 'RECOVERY' },
  { label: planItemTypeLabels.REST, value: 'REST' },
  { label: planItemTypeLabels.OTHER, value: 'OTHER' },
];
