import { createRouter, createWebHistory } from 'vue-router';
import TodayView from '@/views/TodayView.vue';
import PlanView from '@/views/PlanView.vue';
import PlanOverviewView from '@/views/plan/PlanOverviewView.vue';
import ProfileSetupView from '@/views/plan/ProfileSetupView.vue';
import HealthConstraintsSetupView from '@/views/plan/HealthConstraintsSetupView.vue';
import GoalsSetupView from '@/views/plan/GoalsSetupView.vue';
import RecordsView from '@/views/RecordsView.vue';
import TrendsView from '@/views/TrendsView.vue';
import AdjustmentsView from '@/views/AdjustmentsView.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/today' },
    { path: '/today', name: 'today', component: TodayView },
    {
      path: '/plan',
      component: PlanView,
      children: [
        { path: '', name: 'plan', component: PlanOverviewView },
        { path: 'setup/profile', name: 'plan-profile', component: ProfileSetupView },
        { path: 'setup/constraints', name: 'plan-constraints', component: HealthConstraintsSetupView },
        { path: 'setup/goals', name: 'plan-goals', component: GoalsSetupView },
      ],
    },
    { path: '/records', name: 'records', component: RecordsView },
    { path: '/trends', name: 'trends', component: TrendsView },
    { path: '/adjustments', name: 'adjustments', component: AdjustmentsView },
  ],
});

export default router;
