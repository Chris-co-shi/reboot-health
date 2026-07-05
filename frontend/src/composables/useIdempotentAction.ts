import { ref } from 'vue';
import { M2bApiClientError } from '@/services/m2bApi';

/**
 * 管理单次用户操作的 Idempotency-Key 生命周期。
 *
 * <p>网络错误后保留 key 供重试；明确成功或明确业务失败后清除 key，避免页面重复提交产生多个业务命令。</p>
 */
export function useIdempotentAction<TArgs extends unknown[], TResult>(
  action: (idempotencyKey: string, ...args: TArgs) => Promise<TResult>,
) {
  const loading = ref(false);
  const currentKey = ref<string>();

  async function run(...args: TArgs): Promise<TResult> {
    if (!currentKey.value) {
      currentKey.value = crypto.randomUUID();
    }
    loading.value = true;
    try {
      const result = await action(currentKey.value, ...args);
      currentKey.value = undefined;
      return result;
    } catch (error) {
      if (error instanceof M2bApiClientError && error.status > 0) {
        currentKey.value = undefined;
      }
      throw error;
    } finally {
      loading.value = false;
    }
  }

  function resetKey() {
    currentKey.value = undefined;
  }

  return { loading, run, resetKey };
}
