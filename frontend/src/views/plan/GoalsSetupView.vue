<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import type { FormInstance, FormRules } from 'element-plus';
import {
  goalStatusLabels,
  goalTypeLabels,
  goalTypeOptions,
  goalUnitLabels,
  optionsForGoalType,
} from '@/constants/m2aLabels';
import {
  ApiClientError,
  archiveGoal,
  changeGoalStatus,
  createGoal,
  listGoals,
  updateGoal,
} from '@/services/m2aApi';
import type { Goal, GoalRequest, GoalStatus } from '@/types/m2a';

interface GoalAction {
  label: string;
  status: GoalStatus;
}

const loading = ref(false);
const saving = ref(false);
const includeArchived = ref(false);
const items = ref<Goal[]>([]);
const editingId = ref<string>();
const archiveTarget = ref<Goal>();
const archiveReason = ref('');
const formRef = ref<FormInstance>();
const fieldErrors = reactive<Record<string, string>>({});
const archiveDialogVisible = computed({
  get: () => Boolean(archiveTarget.value),
  set: (visible: boolean) => {
    if (!visible) {
      archiveTarget.value = undefined;
    }
  },
});

const form = reactive<GoalRequest>(newForm());
const unitOptions = computed(() => optionsForGoalType(form.goalType));
const rules = reactive<FormRules<GoalRequest>>({
  title: [
    { required: true, message: '请输入标题', trigger: 'blur' },
    { min: 1, max: 100, message: '标题需为 1-100 个字符', trigger: 'blur' },
  ],
});

watch(
  () => form.goalType,
  () => {
    const allowed = unitOptions.value.map((option) => option.value);
    if (!allowed.includes(form.unit)) {
      form.unit = unitOptions.value[0].value;
    }
  }
);

watch(
  () => form.unit,
  (unit) => {
    if (unit === 'NONE') {
      form.targetValue = undefined;
      form.baselineValue = undefined;
    }
  }
);

onMounted(loadItems);

async function loadItems() {
  loading.value = true;
  try {
    items.value = await listGoals({ includeArchived: includeArchived.value });
  } catch (error) {
    showError(error);
  } finally {
    loading.value = false;
  }
}

async function submit() {
  clearFieldErrors();
  const valid = await formRef.value?.validate().catch(() => false);
  if (valid === false) {
    return;
  }
  saving.value = true;
  try {
    if (editingId.value) {
      await updateGoal(editingId.value, normalizeForm());
      ElMessage.success('目标已更新');
    } else {
      await createGoal(normalizeForm());
      ElMessage.success('目标已创建');
    }
    resetForm();
    await loadItems();
  } catch (error) {
    showError(error);
  } finally {
    saving.value = false;
  }
}

function startEdit(item: Goal) {
  if (!canEditGoal(item)) {
    return;
  }
  editingId.value = item.id;
  Object.assign(form, {
    goalType: item.goalType,
    title: item.title,
    targetValue: item.targetValue,
    unit: item.unit,
    baselineValue: item.baselineValue,
    targetDate: item.targetDate ?? '',
    priority: item.priority,
  });
}

async function updateStatus(item: Goal, status: GoalStatus) {
  try {
    if (status === 'COMPLETED' || status === 'CANCELLED') {
      await ElMessageBox.confirm('确认将该目标改为终态？终态目标不能继续编辑。', '确认状态变化', { type: 'warning' });
    }
    await changeGoalStatus(item.id, status);
    ElMessage.success('状态已更新');
    await loadItems();
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return;
    }
    showError(error);
  }
}

function openArchive(item: Goal) {
  archiveTarget.value = item;
  archiveReason.value = '';
}

async function confirmArchive() {
  if (!archiveTarget.value) {
    return;
  }
  try {
    await archiveGoal(archiveTarget.value.id, archiveReason.value);
    ElMessage.success('目标已归档');
    archiveTarget.value = undefined;
    await loadItems();
  } catch (error) {
    showError(error);
  }
}

function actionsFor(status: GoalStatus): GoalAction[] {
  if (status === 'ACTIVE') {
    return [
      { label: '暂停', status: 'PAUSED' },
      { label: '完成', status: 'COMPLETED' },
      { label: '取消', status: 'CANCELLED' },
    ];
  }
  if (status === 'PAUSED') {
    return [
      { label: '恢复', status: 'ACTIVE' },
      { label: '完成', status: 'COMPLETED' },
      { label: '取消', status: 'CANCELLED' },
    ];
  }
  return [];
}

function canEditGoal(item: Goal) {
  return item.status === 'ACTIVE' || item.status === 'PAUSED';
}

function resetForm() {
  editingId.value = undefined;
  Object.assign(form, newForm());
}

function normalizeForm(): GoalRequest {
  return {
    ...form,
    targetValue: form.unit === 'NONE' ? undefined : form.targetValue,
    baselineValue: form.unit === 'NONE' ? undefined : form.baselineValue,
    targetDate: form.targetDate || undefined,
  };
}

function newForm(): GoalRequest {
  return {
    goalType: 'WEIGHT',
    title: '',
    targetValue: undefined,
    unit: 'KG',
    baselineValue: undefined,
    targetDate: '',
    priority: 1,
  };
}

function showError(error: unknown) {
  if (error instanceof ApiClientError) {
    applyFieldErrors(error);
    ElMessage.error(`${error.code}: ${error.message}`);
    return;
  }
  ElMessage.error('请求失败');
}

function applyFieldErrors(error: ApiClientError) {
  clearFieldErrors();
  error.fields?.forEach((field) => {
    fieldErrors[field.field] = field.message;
  });
}

function clearFieldErrors() {
  Object.keys(fieldErrors).forEach((key) => {
    delete fieldErrors[key];
  });
}

function goalTypeLabel(item: Goal) {
  return goalTypeLabels[item.goalType];
}

function goalUnitLabel(item: Goal) {
  return goalUnitLabels[item.unit];
}

function goalStatusLabel(item: Goal) {
  return goalStatusLabels[item.status];
}
</script>

<template>
  <section class="split-workspace">
    <section class="panel">
      <div class="section-title">
        <div>
          <p class="eyebrow">目标</p>
          <h3>{{ editingId ? '编辑目标' : '新增目标' }}</h3>
        </div>
        <el-button v-if="editingId" @click="resetForm">取消编辑</el-button>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        class="entity-form"
        @submit.prevent="submit"
      >
        <div class="form-grid">
          <el-form-item label="目标类型" prop="goalType" :error="fieldErrors.goalType">
            <el-select v-model="form.goalType">
              <el-option v-for="item in goalTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="单位" prop="unit" :error="fieldErrors.unit">
            <el-select v-model="form.unit">
              <el-option v-for="item in unitOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="优先级" prop="priority" :error="fieldErrors.priority">
            <el-input-number v-model="form.priority" :min="1" :max="5" />
          </el-form-item>
        </div>
        <el-form-item label="标题" prop="title" :error="fieldErrors.title">
          <el-input v-model="form.title" maxlength="100" show-word-limit />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="目标值" prop="targetValue" :error="fieldErrors.targetValue">
            <el-input-number v-model="form.targetValue" :min="0" :precision="3" :disabled="form.unit === 'NONE'" />
          </el-form-item>
          <el-form-item label="基线值" prop="baselineValue" :error="fieldErrors.baselineValue">
            <el-input-number v-model="form.baselineValue" :min="0" :precision="3" :disabled="form.unit === 'NONE'" />
          </el-form-item>
          <el-form-item label="目标日期" prop="targetDate" :error="fieldErrors.targetDate">
            <el-date-picker v-model="form.targetDate" type="date" value-format="YYYY-MM-DD" />
          </el-form-item>
        </div>
        <div class="form-footer">
          <span class="muted-text">单位组合由后端规则校验。</span>
          <el-button type="primary" native-type="submit" :loading="saving">{{ editingId ? '保存修改' : '创建目标' }}</el-button>
        </div>
      </el-form>
    </section>

    <section class="panel">
      <div class="section-title">
        <div>
          <p class="eyebrow">目标列表</p>
          <h3>当前记录</h3>
        </div>
        <el-switch v-model="includeArchived" active-text="显示归档" @change="() => loadItems()" />
      </div>

      <el-table v-loading="loading" :data="items" class="entity-table">
        <el-table-column prop="title" label="标题" min-width="150" />
        <el-table-column label="类型" min-width="170">
          <template #default="{ row }">{{ goalTypeLabel(row) }}</template>
        </el-table-column>
        <el-table-column label="单位" width="150">
          <template #default="{ row }">{{ goalUnitLabel(row) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ACTIVE' ? 'success' : row.status === 'ARCHIVED' ? 'info' : 'warning'" effect="plain">
              {{ goalStatusLabel(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="260" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button v-if="canEditGoal(row)" size="small" @click="startEdit(row)">编辑</el-button>
              <el-button
                v-for="action in actionsFor(row.status)"
                :key="action.status"
                size="small"
                @click="updateStatus(row, action.status)"
              >
                {{ action.label }}
              </el-button>
              <el-button v-if="row.status !== 'ARCHIVED'" size="small" type="warning" @click="openArchive(row)">归档</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </section>

  <el-dialog v-model="archiveDialogVisible" title="归档目标" width="420px">
    <el-input v-model="archiveReason" type="textarea" :rows="4" maxlength="300" show-word-limit />
    <template #footer>
      <el-button @click="archiveTarget = undefined">取消</el-button>
      <el-button type="warning" :disabled="!archiveReason.trim()" @click="confirmArchive">确认归档</el-button>
    </template>
  </el-dialog>
</template>
