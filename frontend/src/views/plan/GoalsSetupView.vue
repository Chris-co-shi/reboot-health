<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import {
  ApiClientError,
  archiveGoal,
  changeGoalStatus,
  createGoal,
  listGoals,
  updateGoal,
} from '@/services/m2aApi';
import type { Goal, GoalRequest, GoalStatus, GoalType, GoalUnit } from '@/types/m2a';

const goalTypes: GoalType[] = [
  'WEIGHT',
  'WAIST',
  'TRAINING_HABIT',
  'AEROBIC_CAPACITY',
  'STRENGTH',
  'SWIMMING',
  'BASKETBALL_CONDITIONING',
  'SLEEP',
  'OTHER',
];
const units: GoalUnit[] = ['KG', 'CM', 'SESSIONS_PER_WEEK', 'MINUTES', 'MINUTES_PER_DAY', 'METERS', 'LAPS', 'SCORE', 'PERCENT', 'NONE'];

const loading = ref(false);
const saving = ref(false);
const includeArchived = ref(false);
const items = ref<Goal[]>([]);
const editingId = ref<string>();
const archiveTarget = ref<Goal>();
const archiveReason = ref('');
const archiveDialogVisible = computed({
  get: () => Boolean(archiveTarget.value),
  set: (visible: boolean) => {
    if (!visible) {
      archiveTarget.value = undefined;
    }
  },
});

const form = reactive<GoalRequest>(newForm());

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
    await changeGoalStatus(item.id, status);
    ElMessage.success('状态已更新');
    await loadItems();
  } catch (error) {
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

function actionsFor(status: GoalStatus) {
  if (status === 'ACTIVE') {
    return [
      { label: '暂停', status: 'PAUSED' as const },
      { label: '完成', status: 'COMPLETED' as const },
      { label: '取消', status: 'CANCELLED' as const },
    ];
  }
  if (status === 'PAUSED') {
    return [
      { label: '恢复', status: 'ACTIVE' as const },
      { label: '完成', status: 'COMPLETED' as const },
      { label: '取消', status: 'CANCELLED' as const },
    ];
  }
  return [];
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
    targetValue: 80,
    unit: 'KG',
    baselineValue: 94,
    targetDate: '',
    priority: 1,
  };
}

function showError(error: unknown) {
  if (error instanceof ApiClientError) {
    ElMessage.error(`${error.code}: ${error.message}`);
    return;
  }
  ElMessage.error('请求失败');
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

      <el-form label-position="top" class="entity-form" @submit.prevent="submit">
        <div class="form-grid">
          <el-form-item label="目标类型">
            <el-select v-model="form.goalType">
              <el-option v-for="item in goalTypes" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="单位">
            <el-select v-model="form.unit">
              <el-option v-for="item in units" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="优先级">
            <el-input-number v-model="form.priority" :min="1" :max="5" />
          </el-form-item>
        </div>
        <el-form-item label="标题">
          <el-input v-model="form.title" maxlength="100" show-word-limit />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="目标值">
            <el-input-number v-model="form.targetValue" :min="0" :precision="3" :disabled="form.unit === 'NONE'" />
          </el-form-item>
          <el-form-item label="基线值">
            <el-input-number v-model="form.baselineValue" :min="0" :precision="3" :disabled="form.unit === 'NONE'" />
          </el-form-item>
          <el-form-item label="目标日期">
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
        <el-table-column prop="goalType" label="类型" min-width="170" />
        <el-table-column prop="unit" label="单位" width="150" />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ACTIVE' ? 'success' : row.status === 'ARCHIVED' ? 'info' : 'warning'" effect="plain">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="260" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button v-if="row.status !== 'ARCHIVED'" size="small" @click="startEdit(row)">编辑</el-button>
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
