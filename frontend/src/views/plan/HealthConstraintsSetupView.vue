<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import type { FormInstance, FormRules } from 'element-plus';
import {
  bodyRegionLabels,
  bodyRegionOptions,
  constraintSeverityLabels,
  constraintSeverityOptions,
  constraintSourceTypeOptions,
  constraintStatusLabels,
  constraintTypeLabels,
  constraintTypeOptions,
} from '@/constants/m2aLabels';
import {
  ApiClientError,
  archiveHealthConstraint,
  changeHealthConstraintStatus,
  createHealthConstraint,
  listHealthConstraints,
  updateHealthConstraint,
} from '@/services/m2aApi';
import type { ConstraintStatus, HealthConstraint, HealthConstraintRequest } from '@/types/m2a';

interface ConstraintAction {
  label: string;
  status: ConstraintStatus;
}

const loading = ref(false);
const saving = ref(false);
const includeArchived = ref(false);
const items = ref<HealthConstraint[]>([]);
const editingId = ref<string>();
const archiveTarget = ref<HealthConstraint>();
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

const form = reactive<HealthConstraintRequest>(newForm());
const rules = reactive<FormRules<HealthConstraintRequest>>({
  title: [
    { required: true, message: '请输入标题', trigger: 'blur' },
    { min: 1, max: 100, message: '标题需为 1-100 个字符', trigger: 'blur' },
  ],
  description: [{ max: 2000, message: '描述最多 2000 个字符', trigger: 'blur' }],
  sourceNote: [{ max: 1000, message: '来源备注最多 1000 个字符', trigger: 'blur' }],
});

onMounted(loadItems);

async function loadItems() {
  loading.value = true;
  try {
    items.value = await listHealthConstraints({ includeArchived: includeArchived.value });
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
      await updateHealthConstraint(editingId.value, normalizeForm());
      ElMessage.success('健康约束已更新');
    } else {
      await createHealthConstraint(normalizeForm());
      ElMessage.success('健康约束已创建');
    }
    resetForm();
    await loadItems();
  } catch (error) {
    showError(error);
  } finally {
    saving.value = false;
  }
}

function startEdit(item: HealthConstraint) {
  editingId.value = item.id;
  Object.assign(form, {
    constraintType: item.constraintType,
    bodyRegion: item.bodyRegion,
    severity: item.severity,
    title: item.title,
    description: item.description ?? '',
    sourceType: item.sourceType,
    sourceNote: item.sourceNote ?? '',
    effectiveFrom: item.effectiveFrom ?? '',
    effectiveTo: item.effectiveTo ?? '',
  });
}

async function updateStatus(item: HealthConstraint, status: ConstraintStatus) {
  try {
    if (status === 'RESOLVED') {
      await ElMessageBox.confirm('确认将该健康约束标记为已解决？', '确认状态变化', { type: 'warning' });
    }
    await changeHealthConstraintStatus(item.id, status);
    ElMessage.success('状态已更新');
    await loadItems();
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return;
    }
    showError(error);
  }
}

function openArchive(item: HealthConstraint) {
  archiveTarget.value = item;
  archiveReason.value = '';
}

async function confirmArchive() {
  if (!archiveTarget.value) {
    return;
  }
  try {
    await archiveHealthConstraint(archiveTarget.value.id, archiveReason.value);
    ElMessage.success('健康约束已归档');
    archiveTarget.value = undefined;
    await loadItems();
  } catch (error) {
    showError(error);
  }
}

function actionsFor(status: ConstraintStatus): ConstraintAction[] {
  if (status === 'ACTIVE') {
    return [
      { label: '停用', status: 'INACTIVE' },
      { label: '已解决', status: 'RESOLVED' },
    ];
  }
  if (status === 'INACTIVE') {
    return [
      { label: '启用', status: 'ACTIVE' },
      { label: '已解决', status: 'RESOLVED' },
    ];
  }
  return [];
}

function resetForm() {
  editingId.value = undefined;
  Object.assign(form, newForm());
}

function normalizeForm(): HealthConstraintRequest {
  return {
    ...form,
    description: form.description || undefined,
    sourceNote: form.sourceNote || undefined,
    effectiveFrom: form.effectiveFrom || undefined,
    effectiveTo: form.effectiveTo || undefined,
  };
}

function newForm(): HealthConstraintRequest {
  return {
    constraintType: 'TRAINING_PRECAUTION',
    bodyRegion: 'FULL_BODY',
    severity: 'MEDIUM',
    title: '',
    description: '',
    sourceType: 'USER_REPORTED',
    sourceNote: '',
    effectiveFrom: '',
    effectiveTo: '',
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

function constraintTypeLabel(item: HealthConstraint) {
  return constraintTypeLabels[item.constraintType];
}

function bodyRegionLabel(item: HealthConstraint) {
  return bodyRegionLabels[item.bodyRegion];
}

function severityLabel(item: HealthConstraint) {
  return constraintSeverityLabels[item.severity];
}

function statusLabel(item: HealthConstraint) {
  return constraintStatusLabels[item.status];
}
</script>

<template>
  <section class="split-workspace">
    <section class="panel">
      <div class="section-title">
        <div>
          <p class="eyebrow">健康约束</p>
          <h3>{{ editingId ? '编辑约束' : '新增约束' }}</h3>
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
          <el-form-item label="类型" prop="constraintType" :error="fieldErrors.constraintType">
            <el-select v-model="form.constraintType">
              <el-option v-for="item in constraintTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="部位" prop="bodyRegion" :error="fieldErrors.bodyRegion">
            <el-select v-model="form.bodyRegion">
              <el-option v-for="item in bodyRegionOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="严重程度" prop="severity" :error="fieldErrors.severity">
            <el-select v-model="form.severity">
              <el-option v-for="item in constraintSeverityOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="来源" prop="sourceType" :error="fieldErrors.sourceType">
            <el-select v-model="form.sourceType">
              <el-option v-for="item in constraintSourceTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="标题" prop="title" :error="fieldErrors.title">
          <el-input v-model="form.title" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="描述" prop="description" :error="fieldErrors.description">
          <el-input v-model="form.description" type="textarea" :rows="4" maxlength="2000" show-word-limit />
        </el-form-item>
        <el-form-item label="来源备注" prop="sourceNote" :error="fieldErrors.sourceNote">
          <el-input v-model="form.sourceNote" maxlength="1000" show-word-limit />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="生效开始" prop="effectiveFrom" :error="fieldErrors.effectiveFrom">
            <el-date-picker v-model="form.effectiveFrom" type="date" value-format="YYYY-MM-DD" />
          </el-form-item>
          <el-form-item label="生效结束" prop="effectiveTo" :error="fieldErrors.effectiveTo">
            <el-date-picker v-model="form.effectiveTo" type="date" value-format="YYYY-MM-DD" />
          </el-form-item>
        </div>
        <div class="form-footer">
          <span class="muted-text">归档后不可普通编辑。</span>
          <el-button type="primary" native-type="submit" :loading="saving">{{ editingId ? '保存修改' : '创建约束' }}</el-button>
        </div>
      </el-form>
    </section>

    <section class="panel">
      <div class="section-title">
        <div>
          <p class="eyebrow">约束列表</p>
          <h3>当前记录</h3>
        </div>
        <el-switch v-model="includeArchived" active-text="显示归档" @change="() => loadItems()" />
      </div>

      <el-table v-loading="loading" :data="items" class="entity-table">
        <el-table-column prop="title" label="标题" min-width="150" />
        <el-table-column label="类型" min-width="170">
          <template #default="{ row }">{{ constraintTypeLabel(row) }}</template>
        </el-table-column>
        <el-table-column label="部位" min-width="120">
          <template #default="{ row }">{{ bodyRegionLabel(row) }}</template>
        </el-table-column>
        <el-table-column label="严重程度" width="110">
          <template #default="{ row }">{{ severityLabel(row) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ACTIVE' ? 'success' : row.status === 'ARCHIVED' ? 'info' : 'warning'" effect="plain">
              {{ statusLabel(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="240" fixed="right">
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

  <el-dialog v-model="archiveDialogVisible" title="归档健康约束" width="420px">
    <el-input v-model="archiveReason" type="textarea" :rows="4" maxlength="300" show-word-limit />
    <template #footer>
      <el-button @click="archiveTarget = undefined">取消</el-button>
      <el-button type="warning" :disabled="!archiveReason.trim()" @click="confirmArchive">确认归档</el-button>
    </template>
  </el-dialog>
</template>
