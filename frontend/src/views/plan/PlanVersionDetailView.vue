<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { goalStatusLabels } from '@/constants/m2aLabels';
import { planItemTypeLabels, planVersionStatusLabels } from '@/constants/m2bLabels';
import { useIdempotentAction } from '@/composables/useIdempotentAction';
import {
  cancelPlanVersion,
  confirmPlanVersion,
  getPlanVersion,
  M2bApiClientError,
  previewPlanVersion,
} from '@/services/m2bApi';
import type { PlanItem, PlanVersion, PlanVersionPreview } from '@/types/m2b';

const route = useRoute();
const router = useRouter();
const versionId = computed(() => String(route.params.versionId));
const loading = ref(false);
const version = ref<PlanVersion>();
const preview = ref<PlanVersionPreview>();
const cancelReason = ref('');
const cancelDialogVisible = ref(false);

const confirmAction = useIdempotentAction((key: string, id: string, expectedRevision: number) =>
  confirmPlanVersion(id, { expectedRevision }, key),
);
const cancelAction = useIdempotentAction((key: string, id: string, reason: string, expectedRevision: number) =>
  cancelPlanVersion(id, { cancelReason: reason, expectedRevision }, key),
);

const isPreview = computed(() => route.path.includes('/preview'));
const validationIssues = computed(() => preview.value?.validationIssues ?? []);
const canConfirm = computed(() => (isPreview.value ? preview.value?.canConfirm : version.value?.status === 'DRAFT') === true);
const healthConstraintItems = computed(() => version.value?.healthConstraints?.items ?? []);
const goalSummaries = computed(() => version.value?.goals ?? []);

onMounted(load);

async function load() {
  loading.value = true;
  try {
    if (isPreview.value) {
      preview.value = await previewPlanVersion(versionId.value);
      version.value = preview.value.detail;
    } else {
      version.value = await getPlanVersion(versionId.value);
      preview.value = undefined;
    }
  } catch (error) {
    showError(error);
  } finally {
    loading.value = false;
  }
}

async function confirmVersion() {
  if (!version.value) {
    return;
  }
  try {
    await ElMessageBox.confirm('确认后该计划版本不可再编辑。若同周期已有确认版本，它会被标记为已替代。', '确认计划版本', {
      type: 'warning',
    });
    version.value = await confirmAction.run(version.value.id, version.value.revision);
    preview.value = undefined;
    ElMessage.success('计划版本已确认');
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return;
    }
    showError(error);
  }
}

async function submitCancel() {
  if (!version.value || !cancelReason.value.trim()) {
    return;
  }
  try {
    version.value = await cancelAction.run(version.value.id, cancelReason.value.trim(), version.value.revision);
    preview.value = undefined;
    cancelDialogVisible.value = false;
    cancelReason.value = '';
    ElMessage.success('草案已取消');
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

function itemTypeLabel(item: PlanItem) {
  return planItemTypeLabels[item.itemType];
}
</script>

<template>
  <section v-loading="loading" class="plan-stack">
    <section class="panel">
      <div class="section-title">
        <div>
          <p class="eyebrow">{{ isPreview ? '预览确认' : '版本详情' }}</p>
          <h3>{{ version?.title ?? '计划版本' }}</h3>
          <p v-if="version">
            {{ version.startDate }} 至 {{ version.endDate }} ·
            {{ planVersionStatusLabels[version.status] }} · revision {{ version.revision }}
          </p>
        </div>
        <div class="setup-actions">
          <el-button v-if="version?.status === 'DRAFT'" @click="router.push(`/plan/drafts/${version.id}/edit`)">继续编辑</el-button>
          <el-button
            v-if="canConfirm"
            type="primary"
            :loading="confirmAction.loading.value"
            @click="confirmVersion"
          >
            确认计划
          </el-button>
          <el-button v-if="canConfirm" type="warning" plain @click="cancelDialogVisible = true">取消草案</el-button>
          <el-button v-if="version?.status === 'CONFIRMED' || version?.status === 'SUPERSEDED'" @click="router.push(`/plan/versions/${version.id}/copy`)">
            复制为新草案
          </el-button>
        </div>
      </div>
    </section>

    <section class="panel">
      <p class="eyebrow">确认上下文</p>
      <h3>关联目标</h3>
      <el-tag v-for="goal in goalSummaries" :key="goal.goalId" class="context-tag" effect="plain">
        {{ goal.title || goal.goalId }}{{ goal.status ? ` · ${goalStatusLabels[goal.status]}` : '' }}
      </el-tag>
      <p v-if="goalSummaries.length === 0" class="muted-text">未关联目标。</p>

      <h3>有效健康约束</h3>
      <el-tag v-for="constraint in healthConstraintItems" :key="constraint.id" class="context-tag" type="warning" effect="plain">
        {{ constraint.title }}
      </el-tag>
      <p v-if="healthConstraintItems.length === 0" class="muted-text">暂无有效健康约束。</p>
    </section>

    <section v-if="isPreview" class="panel">
      <p class="eyebrow">确认校验</p>
      <h3>{{ canConfirm ? '可以确认' : '暂不可确认' }}</h3>
      <el-alert
        v-for="issue in validationIssues"
        :key="issue"
        type="warning"
        show-icon
        :closable="false"
        :title="issue"
      />
      <p v-if="validationIssues.length === 0" class="muted-text">计划结构完整。</p>
    </section>

    <section v-for="day in version?.days ?? []" :key="day.id" class="panel">
      <div class="section-title">
        <div>
          <p class="eyebrow">{{ day.dayDate }}</p>
          <h3>{{ day.title }}</h3>
          <p>{{ day.note || '无备注' }}</p>
        </div>
      </div>
      <el-table :data="day.items" class="entity-table">
        <el-table-column label="类型" width="100">
          <template #default="{ row }">{{ itemTypeLabel(row) }}</template>
        </el-table-column>
        <el-table-column prop="title" label="条目" min-width="180" />
        <el-table-column prop="description" label="描述" min-width="180" />
        <el-table-column label="计划量" min-width="240">
          <template #default="{ row }">
            组 {{ row.plannedSets ?? '-' }} / 次 {{ row.plannedReps ?? '-' }} /
            分钟 {{ row.plannedDurationMinutes ?? '-' }} / 米 {{ row.plannedDistanceMeters ?? '-' }} /
            RPE {{ row.plannedRpe ?? '-' }}
          </template>
        </el-table-column>
      </el-table>
      <p v-if="day.items.length === 0" class="muted-text">休息日或暂无条目。</p>
    </section>

    <el-dialog v-model="cancelDialogVisible" title="取消草案" width="420px">
      <el-input v-model="cancelReason" type="textarea" maxlength="300" placeholder="请输入取消原因" />
      <template #footer>
        <el-button @click="cancelDialogVisible = false">返回</el-button>
        <el-button type="warning" :loading="cancelAction.loading.value" @click="submitCancel">确认取消</el-button>
      </template>
    </el-dialog>
  </section>
</template>
