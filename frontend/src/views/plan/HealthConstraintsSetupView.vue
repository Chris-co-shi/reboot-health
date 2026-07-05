<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import {
  ApiClientError,
  archiveHealthConstraint,
  changeHealthConstraintStatus,
  createHealthConstraint,
  listHealthConstraints,
  updateHealthConstraint,
} from '@/services/m2aApi';
import type {
  BodyRegion,
  ConstraintSeverity,
  ConstraintSourceType,
  ConstraintStatus,
  ConstraintType,
  HealthConstraint,
  HealthConstraintRequest,
} from '@/types/m2a';

const constraintTypes: ConstraintType[] = [
  'HYPERTENSION',
  'CERVICAL_LIMITATION',
  'SHOULDER_NECK_DISCOMFORT',
  'LOWER_BACK_STRAIN',
  'HIP_MOBILITY_LIMITATION',
  'FOOT_SOLE_ISSUE',
  'ACHILLES_DISCOMFORT',
  'FORBIDDEN_MOVEMENT',
  'TRAINING_PRECAUTION',
  'OTHER',
];
const bodyRegions: BodyRegion[] = [
  'CARDIOVASCULAR',
  'CERVICAL_SPINE',
  'SHOULDER_NECK',
  'LOWER_BACK',
  'HIP',
  'FOOT_SOLE',
  'ACHILLES_TENDON',
  'FULL_BODY',
  'OTHER',
];
const severities: ConstraintSeverity[] = ['INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
const sourceTypes: ConstraintSourceType[] = ['USER_REPORTED', 'DOCTOR_ADVICE', 'MEDICAL_REPORT', 'MEASUREMENT', 'OTHER'];

const loading = ref(false);
const saving = ref(false);
const includeArchived = ref(false);
const items = ref<HealthConstraint[]>([]);
const editingId = ref<string>();
const archiveTarget = ref<HealthConstraint>();
const archiveReason = ref('');
const archiveDialogVisible = computed({
  get: () => Boolean(archiveTarget.value),
  set: (visible: boolean) => {
    if (!visible) {
      archiveTarget.value = undefined;
    }
  },
});

const form = reactive<HealthConstraintRequest>(newForm());

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
    await changeHealthConstraintStatus(item.id, status);
    ElMessage.success('状态已更新');
    await loadItems();
  } catch (error) {
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

function actionsFor(status: ConstraintStatus) {
  if (status === 'ACTIVE') {
    return [
      { label: '停用', status: 'INACTIVE' as const },
      { label: '已解决', status: 'RESOLVED' as const },
    ];
  }
  if (status === 'INACTIVE') {
    return [
      { label: '启用', status: 'ACTIVE' as const },
      { label: '已解决', status: 'RESOLVED' as const },
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
    constraintType: 'HYPERTENSION',
    bodyRegion: 'CARDIOVASCULAR',
    severity: 'HIGH',
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
          <p class="eyebrow">健康约束</p>
          <h3>{{ editingId ? '编辑约束' : '新增约束' }}</h3>
        </div>
        <el-button v-if="editingId" @click="resetForm">取消编辑</el-button>
      </div>

      <el-form label-position="top" class="entity-form" @submit.prevent="submit">
        <div class="form-grid">
          <el-form-item label="类型">
            <el-select v-model="form.constraintType">
              <el-option v-for="item in constraintTypes" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="部位">
            <el-select v-model="form.bodyRegion">
              <el-option v-for="item in bodyRegions" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="严重程度">
            <el-select v-model="form.severity">
              <el-option v-for="item in severities" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="来源">
            <el-select v-model="form.sourceType">
              <el-option v-for="item in sourceTypes" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="标题">
          <el-input v-model="form.title" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="4" maxlength="2000" show-word-limit />
        </el-form-item>
        <el-form-item label="来源备注">
          <el-input v-model="form.sourceNote" maxlength="1000" show-word-limit />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="生效开始">
            <el-date-picker v-model="form.effectiveFrom" type="date" value-format="YYYY-MM-DD" />
          </el-form-item>
          <el-form-item label="生效结束">
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
        <el-table-column prop="constraintType" label="类型" min-width="170" />
        <el-table-column prop="severity" label="严重程度" width="110" />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ACTIVE' ? 'success' : row.status === 'ARCHIVED' ? 'info' : 'warning'" effect="plain">
              {{ row.status }}
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
