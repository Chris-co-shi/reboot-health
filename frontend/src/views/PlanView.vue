<script setup lang="ts">
import { RouterView, useRoute } from 'vue-router';

const route = useRoute();

const setupTabs = [
  { path: '/plan', label: '当前计划' },
  { path: '/plan/drafts/new', label: '新建草案' },
  { path: '/plan/versions', label: '版本历史' },
  { path: '/plan/setup/profile', label: '个人档案' },
  { path: '/plan/setup/constraints', label: '健康约束' },
  { path: '/plan/setup/goals', label: '目标' },
];
</script>

<template>
  <section class="workspace">
    <div class="page-heading">
      <p class="eyebrow">M2B</p>
      <h2>计划、版本与人工确认</h2>
      <p>创建 7 天草案、确认计划版本、复制既有版本，并通过 Idempotency-Key 防止重复提交。</p>
    </div>

    <nav class="setup-nav" aria-label="计划设置导航">
      <RouterLink
        v-for="tab in setupTabs"
        :key="tab.path"
        :class="['setup-tab', { active: route.path === tab.path || (tab.path === '/plan/versions' && route.path.startsWith('/plan/versions')) }]"
        :to="tab.path"
      >
        {{ tab.label }}
      </RouterLink>
    </nav>

    <RouterView />
  </section>
</template>
