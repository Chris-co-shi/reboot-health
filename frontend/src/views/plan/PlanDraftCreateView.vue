<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import type { FormInstance, FormRules } from 'element-plus';
import { goalStatusLabels } from '@/constants/m2aLabels';
import { useIdempotentAction } from '@/composables/useIdempotentAction';
import { listGoals } from '@/services/m2aApi';
import {
  createDraft,
  createPlan,
  getSingletonPlan,
  M2bApiClientError,
} from '@/services/m2bApi';
import type { Goal } from '@/types/m2a';
import type { CreateDraftRequest, CreatePlanRequest, Plan } from '@/types/m2b';

const router = useRouter();
const loading = ref(false);
const plan = ref<Plan>();
const goals = ref<Goal[]>([]);
const planFormRef = ref<FormInstance>();
const draftFormRef = ref<FormInstance>();

const planForm = reactive<CreatePlanRequest>({
  title: '个人长期训练计划',
  summary: '',
});

const draftForm = reactive<CreateDraftRequest>({
  startDate: new Date().toISOString().slice(0, 10),
  title: '7 天人工计划草案',
  summary: '',
  goalIds: [],
});

const planRules = reactive<FormRules<CreatePlanRequest>>({
  title: [{ required: true, message: '请输入长期计划名称', trigger: 'blur' }],
});

const draftRules = reactive<FormRules<CreateDraftRequest>>({
  startDate: [{ required: true, message: '请选择开始日期', trigger: 'change' }],
  title: [{ required: true, message: '请输入草案标题', trigger: 'blur' }],
});

const activeGoals = computed(() => goals.value.filter((goal) => goal.status === 'ACTIVE' || goal.status === 'PAUSED'));

const createPlanAction = useIdempotentAction((key: string, payload: CreatePlanRequest) => createPlan(payload, key));
const createDraftAction = useIdempotentAction((key: string, planId: string, payload: CreateDraftRequest) =>
  createDraft(planId, payload, key),
);

onMounted(load);

async function load() {
  loading.value = true;
  try {
    plan.value = await getSingletonPlan().catch((error: unknown) => {
      if (error instanceof M2bApiClientError && error.status === 404) {
        return undefined;
      }
      throw error;
    });
    goals.value = await listGoals({ includeArchived: false });
  } catch (error) {
    showError(error);
  } finally {
    loading.value = false;
  }
}

async function submitPlan() {
  const valid = await planFormRef.value?.validate().catch(() => false);
  if (valid === false) {
    return;
  }
  try {
    plan.value = await createPlanAction.run({ ...planForm, summary: planForm.summary || undefined });
    ElMessage.success('长期计划已创建');
  } catch (error) {
    showError(error);
  }
}

async function submitDraft() {
  if (!plan.value) {
    ElMessage.warning('请先创建长期计划');
    return;
  }
  const valid = await draftFormRef.value?.validate().catch(() => false);
  if (valid === false) {
    return;
  }
  try {
    const draft = await createDraftAction.run(plan.value.id, {
      ...draftForm,
      summary: draftForm.summary || undefined,
      goalIds: draftForm.goalIds,
    });
    ElMessage.success('草案已创建');
    await router.push(`/plan/drafts/${draft.id}/edit`);
  } catch (error) {
    showError(error);
  }
}

function showError(error: unknown) {
  if (error instanceof M2bApiClientError) {
    ElMessage.error(`${error.code}: ${error.message}`);
    return;
  }
  ElMessage.error('操作失败');
}
</script>

<template>
  <section v-loading="loading" class="split-workspace">
    <section class="panel">
      <div class="section-title">
        <div>
          <p class="eyebrow">长期计划</p>
          <h3>{{ plan ? '长期计划已创建' : '创建长期计划身份' }}</h3>
        </div>
      </div>

      <div v-if="plan" class="readonly-summary">
        <strong>{{ plan.title }}</strong>
        <p>{{ plan.summary || '无摘要' }}</p>
      </div>

      <el-form v-else ref="planFormRef" :model="planForm" :rules="planRules" label-position="top">
        <el-form-item label="名称" prop="title">
          <el-input v-model="planForm.title" maxlength="100" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="planForm.summary" type="textarea" maxlength="1000" />
        </el-form-item>
        <el-button type="primary" :loading="createPlanAction.loading.value" @click="submitPlan">创建长期计划</el-button>
      </el-form>
    </section>

    <section class="panel">
      <div class="section-title">
        <div>
          <p class="eyebrow">计划草案</p>
          <h3>新建 7 天人工计划草案</h3>
        </div>
      </div>

      <el-form ref="draftFormRef" :model="draftForm" :rules="draftRules" label-position="top">
        <div class="form-grid">
          <el-form-item label="开始日期" prop="startDate">
            <el-date-picker v-model="draftForm.startDate" type="date" value-format="YYYY-MM-DD" />
          </el-form-item>
          <el-form-item label="标题" prop="title">
            <el-input v-model="draftForm.title" maxlength="100" />
          </el-form-item>
        </div>
        <el-form-item label="摘要">
          <el-input v-model="draftForm.summary" type="textarea" maxlength="1000" />
        </el-form-item>
        <el-form-item label="关联目标">
          <el-select v-model="draftForm.goalIds" multiple filterable placeholder="可选">
            <el-option
              v-for="goal in activeGoals"
              :key="goal.id"
              :label="`${goal.title} · ${goalStatusLabels[goal.status]}`"
              :value="goal.id"
            />
          </el-select>
        </el-form-item>
        <el-button
          type="primary"
          :disabled="!plan"
          :loading="createDraftAction.loading.value"
          @click="submitDraft"
        >
          创建草案
        </el-button>
      </el-form>
    </section>
  </section>
</template>
