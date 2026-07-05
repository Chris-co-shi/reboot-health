<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { getSingletonPlan, listPlanVersions, M2bApiClientError } from '@/services/m2bApi';
import { planVersionStatusLabels } from '@/constants/m2bLabels';
import type { Plan, PlanVersionStatus, PlanVersionSummary } from '@/types/m2b';

const loading = ref(false);
const plan = ref<Plan>();
const versions = ref<PlanVersionSummary[]>([]);
const status = ref<PlanVersionStatus | ''>('');

const statusOptions: Array<{ label: string; value: PlanVersionStatus | '' }> = [
  { label: '全部', value: '' },
  { label: planVersionStatusLabels.DRAFT, value: 'DRAFT' },
  { label: planVersionStatusLabels.CONFIRMED, value: 'CONFIRMED' },
  { label: planVersionStatusLabels.SUPERSEDED, value: 'SUPERSEDED' },
  { label: planVersionStatusLabels.CANCELLED, value: 'CANCELLED' },
];

onMounted(load);

async function load() {
  loading.value = true;
  try {
    plan.value = await getSingletonPlan();
    versions.value = await listPlanVersions(plan.value.id, status.value || undefined);
  } catch (error) {
    if (error instanceof M2bApiClientError && error.status === 404) {
      versions.value = [];
      return;
    }
    showError(error);
  } finally {
    loading.value = false;
  }
}

function showError(error: unknown) {
  if (error instanceof M2bApiClientError) {
    ElMessage.error(`${error.code}: ${error.message}`);
    return;
  }
  ElMessage.error('版本历史加载失败');
}

function statusLabel(row: PlanVersionSummary) {
  return planVersionStatusLabels[row.status];
}
</script>

<template>
  <section class="panel">
    <div class="section-title">
      <div>
        <p class="eyebrow">版本历史</p>
        <h3>{{ plan?.title ?? '长期计划' }}</h3>
      </div>
      <div class="setup-actions">
        <el-select v-model="status" style="width: 140px" @change="load">
          <el-option v-for="option in statusOptions" :key="option.value || 'ALL'" :label="option.label" :value="option.value" />
        </el-select>
        <RouterLink class="action-link" to="/plan/drafts/new">新建草案</RouterLink>
      </div>
    </div>

    <el-table v-loading="loading" :data="versions" class="entity-table">
      <el-table-column prop="title" label="标题" min-width="180" />
      <el-table-column label="周期" min-width="190">
        <template #default="{ row }">{{ row.startDate }} 至 {{ row.endDate }}</template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">{{ statusLabel(row) }}</template>
      </el-table-column>
      <el-table-column label="版本" width="140">
        <template #default="{ row }">v{{ row.versionNumber }} / r{{ row.periodRevision }}</template>
      </el-table-column>
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <div class="table-actions">
            <RouterLink v-if="row.status === 'DRAFT'" class="action-link small-link" :to="`/plan/drafts/${row.id}/edit`">编辑</RouterLink>
            <RouterLink class="action-link small-link" :to="`/plan/versions/${row.id}`">查看</RouterLink>
            <RouterLink
              v-if="row.status === 'CONFIRMED' || row.status === 'SUPERSEDED'"
              class="action-link small-link"
              :to="`/plan/versions/${row.id}/copy`"
            >
              复制
            </RouterLink>
          </div>
        </template>
      </el-table-column>
    </el-table>
  </section>
</template>
