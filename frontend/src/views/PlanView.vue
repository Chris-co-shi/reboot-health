<script setup lang="ts">
import { RouterView, useRoute } from 'vue-router';

const route = useRoute();

const setupTabs = [
  { path: '/plan', label: '当前计划' },
  { path: '/plan/setup/profile', label: '个人档案' },
  { path: '/plan/setup/constraints', label: '健康约束' },
  { path: '/plan/setup/goals', label: '目标' },
];
</script>

<template>
  <section class="workspace">
    <div class="page-heading">
      <p class="eyebrow">M2A 设置</p>
      <h2>档案、健康约束与目标</h2>
      <p>先完成基础资料，后续计划版本会基于这些数据创建。</p>
    </div>

    <nav class="setup-nav" aria-label="计划设置导航">
      <RouterLink
        v-for="tab in setupTabs"
        :key="tab.path"
        :class="['setup-tab', { active: route.path === tab.path }]"
        :to="tab.path"
      >
        {{ tab.label }}
      </RouterLink>
    </nav>

    <RouterView />
  </section>
</template>
