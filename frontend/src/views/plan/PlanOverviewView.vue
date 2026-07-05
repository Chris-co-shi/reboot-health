<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { getCurrentPlan, getSingletonPlan, M2bApiClientError } from '@/services/m2bApi';
import { planVersionStatusLabels } from '@/constants/m2bLabels';
import type { Plan, PlanVersion } from '@/types/m2b';

const loading = ref(false);
const plan = ref<Plan>();
const currentVersion = ref<PlanVersion>();

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
    currentVersion.value = await getCurrentPlan().catch((error: unknown) => {
      if (error instanceof M2bApiClientError && error.status === 404) {
        return undefined;
      }
      throw error;
    });
  } catch (error) {
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
  ElMessage.error('计划数据加载失败');
}
</script>

<template>
  <section v-loading="loading" class="plan-stack">
    <section class="panel plan-overview-panel">
      <div>
        <p class="eyebrow">当前计划</p>
        <h3>{{ currentVersion?.title ?? '当前日期暂无已确认计划' }}</h3>
        <p v-if="currentVersion">
          {{ currentVersion.startDate }} 至 {{ currentVersion.endDate }} ·
          {{ planVersionStatusLabels[currentVersion.status] }} ·
          第 {{ currentVersion.versionNumber }} 版 / 周期修订 {{ currentVersion.periodRevision }}
        </p>
        <p v-else>可以先创建 7 天人工计划草案，确认后会在对应日期自然成为当前计划。</p>
      </div>
      <div class="setup-actions">
        <RouterLink class="action-link" to="/plan/drafts/new">新建草案</RouterLink>
        <RouterLink class="action-link" to="/plan/versions">版本历史</RouterLink>
        <RouterLink v-if="currentVersion" class="action-link" :to="`/plan/versions/${currentVersion.id}`">查看详情</RouterLink>
      </div>
    </section>

    <section class="placeholder-grid">
      <section class="panel">
        <p class="eyebrow">长期计划</p>
        <h3>{{ plan?.title ?? '尚未创建长期计划身份' }}</h3>
        <p>{{ plan?.summary ?? 'M2B 只维护一个长期 Plan，周期内容通过 PlanVersion 管理。' }}</p>
      </section>
      <section class="panel">
        <p class="eyebrow">基础资料</p>
        <h3>档案、健康约束与目标</h3>
        <p>确认计划时会保存当前有效健康约束快照；草案可关联进行中或暂停的目标。</p>
        <div class="setup-actions compact-actions">
          <RouterLink class="action-link" to="/plan/setup/profile">个人档案</RouterLink>
          <RouterLink class="action-link" to="/plan/setup/constraints">健康约束</RouterLink>
          <RouterLink class="action-link" to="/plan/setup/goals">目标</RouterLink>
        </div>
      </section>
    </section>
  </section>
</template>
