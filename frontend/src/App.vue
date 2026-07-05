<script setup lang="ts">
import {
  Calendar,
  DataAnalysis,
  DocumentChecked,
  EditPen,
  TrendCharts,
} from '@element-plus/icons-vue';
import { RouterView, useRoute } from 'vue-router';

const route = useRoute();

const navItems = [
  { path: '/today', label: '今日', icon: Calendar },
  { path: '/plan', label: '当前计划', icon: DocumentChecked },
  { path: '/records', label: '数据记录', icon: EditPen },
  { path: '/trends', label: '趋势分析', icon: TrendCharts },
  { path: '/adjustments', label: '调整确认', icon: DataAnalysis },
];

function isActive(path: string) {
  return route.path === path || (path === '/plan' && route.path.startsWith('/plan/'));
}
</script>

<template>
  <el-container class="app-shell">
    <el-aside class="app-nav" width="232px">
      <div class="brand">
        <span class="brand-mark">RH</span>
        <div>
          <p class="brand-title">reboot-health</p>
          <p class="brand-subtitle">个人训练闭环</p>
        </div>
      </div>

      <nav class="nav-list" aria-label="主导航">
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :class="['nav-item', { active: isActive(item.path) }]"
          :to="item.path"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
    </el-aside>

    <el-container>
      <el-header class="app-header" height="64px">
        <div>
          <p class="eyebrow">M2A</p>
          <h1>健康、减脂与体能重建</h1>
        </div>
        <el-tag type="success" effect="plain">档案与目标管理</el-tag>
      </el-header>

      <el-main class="app-main">
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>
