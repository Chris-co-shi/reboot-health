import { createRouter, createWebHistory } from 'vue-router';
import TodayView from '@/views/TodayView.vue';
import PlanView from '@/views/PlanView.vue';
import RecordsView from '@/views/RecordsView.vue';
import TrendsView from '@/views/TrendsView.vue';
import AdjustmentsView from '@/views/AdjustmentsView.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/today' },
    { path: '/today', name: 'today', component: TodayView },
    { path: '/plan', name: 'plan', component: PlanView },
    { path: '/records', name: 'records', component: RecordsView },
    { path: '/trends', name: 'trends', component: TrendsView },
    { path: '/adjustments', name: 'adjustments', component: AdjustmentsView },
  ],
});

export default router;
