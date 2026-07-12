<script setup lang="ts">
const capabilities = [
  '任务与运行诊断',
  '运维与告警入口',
  '审计摘要',
];
</script>

<template>
  <main class="admin-shell">
    <header>
      <p class="eyebrow">REBOOT HEALTH</p>
      <h1>运营管理台</h1>
      <p class="lede">
        Phase 3B Admin Shell。正式管理能力将在后续已批准的 Slice 中通过 Health Platform 管理 API 接入。
      </p>
    </header>

    <section aria-labelledby="scope-title">
      <h2 id="scope-title">目标边界</h2>
      <ul>
        <li v-for="capability in capabilities" :key="capability">{{ capability }}</li>
      </ul>
    </section>
  </main>
</template>
