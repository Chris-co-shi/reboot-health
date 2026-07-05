import { createRouter, createWebHistory } from 'vue-router';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/today' },
    { path: '/today', name: 'today', component: () => import('@/views/TodayView.vue') },
    {
      path: '/plan',
      component: () => import('@/views/PlanView.vue'),
      children: [
        { path: '', name: 'plan', component: () => import('@/views/plan/PlanOverviewView.vue') },
        { path: 'drafts/new', name: 'plan-draft-new', component: () => import('@/views/plan/PlanDraftCreateView.vue') },
        { path: 'drafts/:versionId/edit', name: 'plan-draft-edit', component: () => import('@/views/plan/PlanDraftEditView.vue') },
        { path: 'drafts/:versionId/preview', name: 'plan-draft-preview', component: () => import('@/views/plan/PlanVersionDetailView.vue') },
        { path: 'versions', name: 'plan-versions', component: () => import('@/views/plan/PlanVersionsView.vue') },
        { path: 'versions/:versionId', name: 'plan-version-detail', component: () => import('@/views/plan/PlanVersionDetailView.vue') },
        { path: 'versions/:versionId/copy', name: 'plan-version-copy', component: () => import('@/views/plan/PlanVersionCopyView.vue') },
        { path: 'setup/profile', name: 'plan-profile', component: () => import('@/views/plan/ProfileSetupView.vue') },
        { path: 'setup/constraints', name: 'plan-constraints', component: () => import('@/views/plan/HealthConstraintsSetupView.vue') },
        { path: 'setup/goals', name: 'plan-goals', component: () => import('@/views/plan/GoalsSetupView.vue') },
      ],
    },
    { path: '/records', name: 'records', component: () => import('@/views/RecordsView.vue') },
    { path: '/trends', name: 'trends', component: () => import('@/views/TrendsView.vue') },
    { path: '/adjustments', name: 'adjustments', component: () => import('@/views/AdjustmentsView.vue') },
  ],
});

export default router;
