<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import type { FormInstance, FormRules } from 'element-plus';
import { planVersionStatusLabels } from '@/constants/m2bLabels';
import { useIdempotentAction } from '@/composables/useIdempotentAction';
import { copyPlanVersion, getPlanVersion, M2bApiClientError } from '@/services/m2bApi';
import type { CopyVersionRequest, PlanVersion } from '@/types/m2b';

const route = useRoute();
const router = useRouter();
const sourceVersionId = String(route.params.versionId);
const loading = ref(false);
const source = ref<PlanVersion>();
const formRef = ref<FormInstance>();

const form = reactive<CopyVersionRequest>({
  startDate: new Date().toISOString().slice(0, 10),
  title: '',
  summary: '',
  expectedSourceStatus: undefined,
});

const rules = reactive<FormRules<CopyVersionRequest>>({
  startDate: [{ required: true, message: '请选择新周期开始日期', trigger: 'change' }],
});

const copyAction = useIdempotentAction((key: string, payload: CopyVersionRequest) =>
  copyPlanVersion(sourceVersionId, payload, key),
);

onMounted(load);

async function load() {
  loading.value = true;
  try {
    source.value = await getPlanVersion(sourceVersionId);
    form.title = `${source.value.title} - 复制`;
    form.summary = source.value.summary ?? '';
    form.expectedSourceStatus = source.value.status;
  } catch (error) {
    showError(error);
  } finally {
    loading.value = false;
  }
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (valid === false) {
    return;
  }
  try {
    const draft = await copyAction.run({
      ...form,
      title: form.title || undefined,
      summary: form.summary || undefined,
    });
    ElMessage.success('已复制为新草案');
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
  ElMessage.error('复制失败');
}
</script>

<template>
  <section v-loading="loading" class="split-workspace">
    <section class="panel">
      <p class="eyebrow">复制来源</p>
      <h3>{{ source?.title ?? '计划版本' }}</h3>
      <p v-if="source">
        {{ source.startDate }} 至 {{ source.endDate }} · {{ planVersionStatusLabels[source.status] }}
      </p>
    </section>

    <section class="panel">
      <div class="section-title">
        <div>
          <p class="eyebrow">复制草案</p>
          <h3>创建新周期草案</h3>
        </div>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="form-grid">
          <el-form-item label="新开始日期" prop="startDate">
            <el-date-picker v-model="form.startDate" type="date" value-format="YYYY-MM-DD" />
          </el-form-item>
          <el-form-item label="新标题">
            <el-input v-model="form.title" maxlength="100" />
          </el-form-item>
        </div>
        <el-form-item label="摘要">
          <el-input v-model="form.summary" type="textarea" maxlength="1000" />
        </el-form-item>
        <el-button type="primary" :loading="copyAction.loading.value" @click="submit">复制为草案</el-button>
      </el-form>
    </section>
  </section>
</template>
