import { defineStore } from 'pinia';

export const useAppStatusStore = defineStore('appStatus', {
  state: () => ({
    phase: 'M1-skeleton',
    businessReady: false,
  }),
});
