import type { ApiErrorResponse } from '@/types/m2a';
import type {
  CancelVersionRequest,
  ConfirmVersionRequest,
  CopyVersionRequest,
  CreateDraftRequest,
  CreatePlanRequest,
  Plan,
  PlanVersion,
  PlanVersionPreview,
  PlanVersionStatus,
  PlanVersionSummary,
  SaveDayRequest,
  SaveItemRequest,
  UpdateVersionRequest,
} from '@/types/m2b';

export class M2bApiClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: ApiErrorResponse['fields'];

  constructor(status: number, response: ApiErrorResponse) {
    super(response.message || response.code || '请求失败');
    this.name = 'M2bApiClientError';
    this.status = status;
    this.code = response.code;
    this.fields = response.fields;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers ?? {}),
      },
    });
  } catch {
    throw new M2bApiClientError(0, { code: 'NETWORK_ERROR', message: '无法连接到后端服务' });
  }

  const text = await response.text();
  if (!response.ok) {
    let body: ApiErrorResponse = { code: 'REQUEST_FAILED', message: response.statusText };
    try {
      if (text) {
        body = JSON.parse(text) as ApiErrorResponse;
      }
    } catch {
      body = { code: 'REQUEST_FAILED', message: response.statusText };
    }
    throw new M2bApiClientError(response.status, body);
  }
  return JSON.parse(text || 'null') as T;
}

function query(params: Record<string, string | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) {
      search.set(key, value);
    }
  });
  const text = search.toString();
  return text ? `?${text}` : '';
}

function idempotencyHeaders(idempotencyKey: string): HeadersInit {
  return { 'Idempotency-Key': idempotencyKey };
}

export function getSingletonPlan() {
  return request<Plan>('/api/v1/plans');
}

export function createPlan(payload: CreatePlanRequest, idempotencyKey: string) {
  return request<Plan>('/api/v1/plans', {
    method: 'POST',
    headers: idempotencyHeaders(idempotencyKey),
    body: JSON.stringify(payload),
  });
}

export function getCurrentPlan() {
  return request<PlanVersion>('/api/v1/plans/current');
}

export function listPlanVersions(planId: string, status?: PlanVersionStatus) {
  return request<PlanVersionSummary[]>(`/api/v1/plans/${planId}/versions${query({ status })}`);
}

export function createDraft(planId: string, payload: CreateDraftRequest, idempotencyKey: string) {
  return request<PlanVersion>(`/api/v1/plans/${planId}/versions`, {
    method: 'POST',
    headers: idempotencyHeaders(idempotencyKey),
    body: JSON.stringify(payload),
  });
}

export function getPlanVersion(versionId: string) {
  return request<PlanVersion>(`/api/v1/plan-versions/${versionId}`);
}

export function previewPlanVersion(versionId: string) {
  return request<PlanVersionPreview>(`/api/v1/plan-versions/${versionId}/preview`);
}

export function updatePlanVersion(versionId: string, payload: UpdateVersionRequest) {
  return request<PlanVersion>(`/api/v1/plan-versions/${versionId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function copyPlanVersion(sourceVersionId: string, payload: CopyVersionRequest, idempotencyKey: string) {
  return request<PlanVersion>(`/api/v1/plan-versions/${sourceVersionId}/copy`, {
    method: 'POST',
    headers: idempotencyHeaders(idempotencyKey),
    body: JSON.stringify(payload),
  });
}

export function confirmPlanVersion(versionId: string, payload: ConfirmVersionRequest, idempotencyKey: string) {
  return request<PlanVersion>(`/api/v1/plan-versions/${versionId}/confirm`, {
    method: 'POST',
    headers: idempotencyHeaders(idempotencyKey),
    body: JSON.stringify(payload),
  });
}

export function cancelPlanVersion(versionId: string, payload: CancelVersionRequest, idempotencyKey: string) {
  return request<PlanVersion>(`/api/v1/plan-versions/${versionId}/cancel`, {
    method: 'POST',
    headers: idempotencyHeaders(idempotencyKey),
    body: JSON.stringify(payload),
  });
}

export function createPlanDay(versionId: string, payload: SaveDayRequest, idempotencyKey: string) {
  return request<PlanVersion>(`/api/v1/plan-versions/${versionId}/days`, {
    method: 'POST',
    headers: idempotencyHeaders(idempotencyKey),
    body: JSON.stringify(payload),
  });
}

export function updatePlanDay(dayId: string, payload: SaveDayRequest) {
  return request<PlanVersion>(`/api/v1/plan-days/${dayId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function deletePlanDay(dayId: string, expectedRevision: number) {
  return request<PlanVersion>(`/api/v1/plan-days/${dayId}${query({ expectedRevision: String(expectedRevision) })}`, {
    method: 'DELETE',
  });
}

export function createPlanItem(dayId: string, payload: SaveItemRequest, idempotencyKey: string) {
  return request<PlanVersion>(`/api/v1/plan-days/${dayId}/items`, {
    method: 'POST',
    headers: idempotencyHeaders(idempotencyKey),
    body: JSON.stringify(payload),
  });
}

export function updatePlanItem(itemId: string, payload: SaveItemRequest) {
  return request<PlanVersion>(`/api/v1/plan-items/${itemId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function deletePlanItem(itemId: string, expectedRevision: number) {
  return request<PlanVersion>(`/api/v1/plan-items/${itemId}${query({ expectedRevision: String(expectedRevision) })}`, {
    method: 'DELETE',
  });
}
