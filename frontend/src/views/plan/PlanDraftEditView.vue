<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import type { FormInstance, FormRules } from 'element-plus';
import { goalStatusLabels } from '@/constants/m2aLabels';
import { planItemTypeLabels, planItemTypeOptions, planVersionStatusLabels } from '@/constants/m2bLabels';
import { useIdempotentAction } from '@/composables/useIdempotentAction';
import { listGoals } from '@/services/m2aApi';
import {
  createPlanItem,
  deletePlanDay,
  deletePlanItem,
  getPlanVersion,
  M2bApiClientError,
  updatePlanDay,
  updatePlanItem,
  updatePlanVersion,
} from '@/services/m2bApi';
import type { Goal } from '@/types/m2a';
import type { PlanDay, PlanItem, PlanVersion, SaveDayRequest, SaveItemRequest, UpdateVersionRequest } from '@/types/m2b';

const route = useRoute();
const router = useRouter();
const versionId = computed(() => String(route.params.versionId));
const loading = ref(false);
const savingMeta = ref(false);
const version = ref<PlanVersion>();
const goals = ref<Goal[]>([]);
const metaFormRef = ref<FormInstance>();
const itemDialogVisible = ref(false);
const itemEditingId = ref<string>();
const itemDayId = ref<string>();

const metaForm = reactive<UpdateVersionRequest>({
  title: '',
  summary: '',
  goalIds: [],
  expectedRevision: 0,
});

const itemForm = reactive<SaveItemRequest>(newItemForm());

const metaRules = reactive<FormRules<UpdateVersionRequest>>({
  title: [{ required: true, message: '请输入草案标题', trigger: 'blur' }],
});

const itemRules = reactive<FormRules<SaveItemRequest>>({
  title: [{ required: true, message: '请输入条目标题', trigger: 'blur' }],
  itemType: [{ required: true, message: '请选择类型', trigger: 'change' }],
});

const activeGoals = computed(() => goals.value.filter((goal) => goal.status === 'ACTIVE' || goal.status === 'PAUSED'));
const editable = computed(() => version.value?.status === 'DRAFT');

const createItemAction = useIdempotentAction((key: string, dayId: string, payload: SaveItemRequest) =>
  createPlanItem(dayId, payload, key),
);

onMounted(load);

async function load() {
  loading.value = true;
  try {
    version.value = await getPlanVersion(versionId.value);
    applyMetaForm();
    goals.value = await listGoals({ includeArchived: false });
  } catch (error) {
    showError(error);
  } finally {
    loading.value = false;
  }
}

function applyMetaForm() {
  if (!version.value) {
    return;
  }
  Object.assign(metaForm, {
    title: version.value.title,
    summary: version.value.summary ?? '',
    goalIds: [...version.value.goalIds],
    expectedRevision: version.value.revision,
  });
}

async function saveMeta() {
  if (!version.value) {
    return;
  }
  const valid = await metaFormRef.value?.validate().catch(() => false);
  if (valid === false) {
    return;
  }
  savingMeta.value = true;
  try {
    version.value = await updatePlanVersion(version.value.id, {
      ...metaForm,
      summary: metaForm.summary || undefined,
      expectedRevision: version.value.revision,
    });
    applyMetaForm();
    ElMessage.success('草案信息已保存');
  } catch (error) {
    showError(error);
  } finally {
    savingMeta.value = false;
  }
}

async function saveDay(day: PlanDay) {
  if (!version.value) {
    return;
  }
  const payload: SaveDayRequest = {
    dayDate: day.dayDate,
    title: day.title,
    note: day.note || undefined,
    sortOrder: day.sortOrder,
    expectedRevision: version.value.revision,
  };
  try {
    version.value = await updatePlanDay(day.id, payload);
    applyMetaForm();
    ElMessage.success('计划日已保存');
  } catch (error) {
    showError(error);
  }
}

async function removeDay(day: PlanDay) {
  try {
    await ElMessageBox.confirm('删除计划日会同时删除其条目，且只能在草案中执行。', '确认删除计划日', { type: 'warning' });
    version.value = await deletePlanDay(day.id);
    applyMetaForm();
    ElMessage.success('计划日已删除');
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return;
    }
    showError(error);
  }
}

function openCreateItem(day: PlanDay) {
  itemEditingId.value = undefined;
  itemDayId.value = day.id;
  Object.assign(itemForm, newItemForm());
  itemDialogVisible.value = true;
  createItemAction.resetKey();
}

function openEditItem(item: PlanItem) {
  itemEditingId.value = item.id;
  itemDayId.value = item.dayId;
  Object.assign(itemForm, {
    goalId: item.goalId,
    itemType: item.itemType,
    title: item.title,
    description: item.description ?? '',
    plannedSets: item.plannedSets,
    plannedReps: item.plannedReps,
    plannedDurationMinutes: item.plannedDurationMinutes,
    plannedDistanceMeters: item.plannedDistanceMeters,
    plannedRpe: item.plannedRpe,
    sortOrder: item.sortOrder,
    expectedRevision: version.value?.revision ?? 0,
  });
  itemDialogVisible.value = true;
}

async function submitItem() {
  if (!version.value || !itemDayId.value) {
    return;
  }
  const payload = normalizeItemForm(version.value.revision);
  try {
    if (itemEditingId.value) {
      version.value = await updatePlanItem(itemEditingId.value, payload);
      ElMessage.success('条目已更新');
    } else {
      version.value = await createItemAction.run(itemDayId.value, payload);
      ElMessage.success('条目已创建');
    }
    applyMetaForm();
    itemDialogVisible.value = false;
  } catch (error) {
    showError(error);
  }
}

async function removeItem(item: PlanItem) {
  try {
    await ElMessageBox.confirm('确认删除该计划条目？', '确认删除条目', { type: 'warning' });
    version.value = await deletePlanItem(item.id);
    applyMetaForm();
    ElMessage.success('条目已删除');
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return;
    }
    showError(error);
  }
}

function normalizeItemForm(expectedRevision: number): SaveItemRequest {
  return {
    ...itemForm,
    goalId: itemForm.goalId || undefined,
    description: itemForm.description || undefined,
    expectedRevision,
  };
}

function newItemForm(): SaveItemRequest {
  return {
    goalId: undefined,
    itemType: 'BODYWEIGHT',
    title: '',
    description: '',
    plannedSets: undefined,
    plannedReps: undefined,
    plannedDurationMinutes: undefined,
    plannedDistanceMeters: undefined,
    plannedRpe: undefined,
    sortOrder: 1,
    expectedRevision: 0,
  };
}

function showError(error: unknown) {
  if (error instanceof M2bApiClientError) {
    ElMessage.error(`${error.code}: ${error.message}`);
    return;
  }
  ElMessage.error('操作失败');
}

function itemTypeLabel(item: PlanItem) {
  return planItemTypeLabels[item.itemType];
}
</script>

<template>
  <section v-loading="loading" class="plan-stack">
    <section class="panel">
      <div class="section-title">
        <div>
          <p class="eyebrow">草案编辑</p>
          <h3>{{ version?.title ?? '计划草案' }}</h3>
        </div>
        <div class="setup-actions">
          <el-tag v-if="version">{{ planVersionStatusLabels[version.status] }}</el-tag>
          <el-button @click="router.push(`/plan/drafts/${versionId}/preview`)">预览确认</el-button>
        </div>
      </div>

      <el-alert
        v-if="version && !editable"
        type="warning"
        show-icon
        :closable="false"
        title="该版本不是草案，只能查看，不能编辑。"
      />

      <el-form ref="metaFormRef" :model="metaForm" :rules="metaRules" label-position="top" class="entity-form">
        <div class="form-grid">
          <el-form-item label="标题" prop="title">
            <el-input v-model="metaForm.title" :disabled="!editable" maxlength="100" />
          </el-form-item>
          <el-form-item label="关联目标">
            <el-select v-model="metaForm.goalIds" :disabled="!editable" multiple filterable placeholder="可选">
              <el-option
                v-for="goal in activeGoals"
                :key="goal.id"
                :label="`${goal.title} · ${goalStatusLabels[goal.status]}`"
                :value="goal.id"
              />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="摘要">
          <el-input v-model="metaForm.summary" :disabled="!editable" type="textarea" maxlength="1000" />
        </el-form-item>
        <el-button type="primary" :disabled="!editable" :loading="savingMeta" @click="saveMeta">保存草案信息</el-button>
      </el-form>
    </section>

    <section v-for="day in version?.days ?? []" :key="day.id" class="panel day-editor">
      <div class="day-header">
        <div class="form-grid day-fields">
          <el-input v-model="day.title" :disabled="!editable" maxlength="100" />
          <el-input v-model="day.note" :disabled="!editable" maxlength="1000" placeholder="备注" />
        </div>
        <div class="setup-actions">
          <el-tag>{{ day.dayDate }}</el-tag>
          <el-button :disabled="!editable" @click="saveDay(day)">保存计划日</el-button>
          <el-button :disabled="!editable" type="danger" plain @click="removeDay(day)">删除</el-button>
        </div>
      </div>

      <el-table :data="day.items" class="entity-table">
        <el-table-column label="类型" width="100">
          <template #default="{ row }">{{ itemTypeLabel(row) }}</template>
        </el-table-column>
        <el-table-column prop="title" label="条目" min-width="180" />
        <el-table-column label="计划量" min-width="220">
          <template #default="{ row }">
            <span>
              组 {{ row.plannedSets ?? '-' }} / 次 {{ row.plannedReps ?? '-' }} /
              分钟 {{ row.plannedDurationMinutes ?? '-' }} / 米 {{ row.plannedDistanceMeters ?? '-' }} /
              RPE {{ row.plannedRpe ?? '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button size="small" :disabled="!editable" @click="openEditItem(row)">编辑</el-button>
              <el-button size="small" :disabled="!editable" type="danger" plain @click="removeItem(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <el-button class="inline-create" :disabled="!editable" @click="openCreateItem(day)">添加条目</el-button>
    </section>

    <el-dialog v-model="itemDialogVisible" :title="itemEditingId ? '编辑计划条目' : '添加计划条目'" width="620px">
      <el-form :model="itemForm" :rules="itemRules" label-position="top">
        <div class="form-grid">
          <el-form-item label="类型" prop="itemType">
            <el-select v-model="itemForm.itemType">
              <el-option v-for="option in planItemTypeOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="标题" prop="title">
            <el-input v-model="itemForm.title" maxlength="100" />
          </el-form-item>
          <el-form-item label="关联目标">
            <el-select v-model="itemForm.goalId" clearable filterable placeholder="可选">
              <el-option
                v-for="goal in activeGoals"
                :key="goal.id"
                :label="`${goal.title} · ${goalStatusLabels[goal.status]}`"
                :value="goal.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="排序">
            <el-input-number v-model="itemForm.sortOrder" :min="1" />
          </el-form-item>
          <el-form-item label="组数">
            <el-input-number v-model="itemForm.plannedSets" :min="0" />
          </el-form-item>
          <el-form-item label="次数">
            <el-input-number v-model="itemForm.plannedReps" :min="0" />
          </el-form-item>
          <el-form-item label="分钟">
            <el-input-number v-model="itemForm.plannedDurationMinutes" :min="0" />
          </el-form-item>
          <el-form-item label="距离米">
            <el-input-number v-model="itemForm.plannedDistanceMeters" :min="0" />
          </el-form-item>
          <el-form-item label="RPE">
            <el-input-number v-model="itemForm.plannedRpe" :min="1" :max="10" :step="0.5" />
          </el-form-item>
        </div>
        <el-form-item label="描述">
          <el-input v-model="itemForm.description" type="textarea" maxlength="1000" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createItemAction.loading.value" @click="submitItem">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>
