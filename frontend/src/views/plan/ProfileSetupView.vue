<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { ApiClientError, getProfile, saveProfile } from '@/services/m2aApi';
import type { Sex, UserProfileRequest } from '@/types/m2a';

const sexOptions: Array<{ label: string; value: Sex }> = [
  { label: '男', value: 'MALE' },
  { label: '女', value: 'FEMALE' },
  { label: '其他', value: 'OTHER' },
  { label: '未指定', value: 'UNSPECIFIED' },
];

const loading = ref(false);
const saving = ref(false);
const initialized = ref(false);
const lastUpdatedAt = ref<string>();

const form = reactive<UserProfileRequest>({
  displayName: '',
  sex: 'MALE',
  birthDate: '',
  heightCm: undefined,
  baselineWeightKg: undefined,
  timezone: resolveBrowserTimezone(),
});

const statusText = computed(() => (initialized.value ? '已初始化' : '未初始化'));

onMounted(loadProfile);

async function loadProfile() {
  loading.value = true;
  try {
    const profile = await getProfile();
    Object.assign(form, {
      displayName: profile.displayName,
      sex: profile.sex,
      birthDate: profile.birthDate ?? '',
      heightCm: profile.heightCm,
      baselineWeightKg: profile.baselineWeightKg,
      timezone: profile.timezone,
    });
    lastUpdatedAt.value = profile.updatedAt;
    initialized.value = true;
  } catch (error) {
    if (error instanceof ApiClientError && error.code === 'PROFILE_NOT_INITIALIZED') {
      initialized.value = false;
      return;
    }
    showError(error);
  } finally {
    loading.value = false;
  }
}

async function submit() {
  saving.value = true;
  try {
    const saved = await saveProfile({
      ...form,
      birthDate: form.birthDate || undefined,
    });
    lastUpdatedAt.value = saved.updatedAt;
    initialized.value = true;
    ElMessage.success('档案已保存');
  } catch (error) {
    showError(error);
  } finally {
    saving.value = false;
  }
}

function resolveBrowserTimezone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai';
  } catch {
    return 'Asia/Shanghai';
  }
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
  <section class="panel">
    <div class="section-title">
      <div>
        <p class="eyebrow">个人档案</p>
        <h3>基础信息</h3>
      </div>
      <el-tag :type="initialized ? 'success' : 'info'" effect="plain">{{ statusText }}</el-tag>
    </div>

    <el-skeleton v-if="loading" :rows="5" animated />

    <el-form v-else label-position="top" class="entity-form" @submit.prevent="submit">
      <div class="form-grid">
        <el-form-item label="显示名称">
          <el-input v-model="form.displayName" maxlength="60" show-word-limit />
        </el-form-item>
        <el-form-item label="性别">
          <el-select v-model="form.sex">
            <el-option v-for="item in sexOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="出生日期">
          <el-date-picker v-model="form.birthDate" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="身高 cm">
          <el-input-number v-model="form.heightCm" :min="100" :max="250" :precision="2" />
        </el-form-item>
        <el-form-item label="基线体重 kg">
          <el-input-number v-model="form.baselineWeightKg" :min="30" :max="300" :precision="2" />
        </el-form-item>
        <el-form-item label="时区">
          <el-input v-model="form.timezone" maxlength="64" />
        </el-form-item>
      </div>

      <div class="form-footer">
        <span class="muted-text">基线体重不会作为实时当前体重使用。</span>
        <el-button type="primary" native-type="submit" :loading="saving">保存档案</el-button>
      </div>
      <p v-if="lastUpdatedAt" class="muted-text">最后更新：{{ lastUpdatedAt }}</p>
    </el-form>
  </section>
</template>
