import type {
  ApiErrorResponse,
  Goal,
  GoalRequest,
  GoalStatus,
  HealthConstraint,
  HealthConstraintRequest,
  ConstraintStatus,
  UserProfile,
  UserProfileRequest,
} from '@/types/m2a';

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: ApiErrorResponse['fields'];

  constructor(status: number, response: ApiErrorResponse) {
    super(response.message || response.code || '请求失败');
    this.name = 'ApiClientError';
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
    throw new ApiClientError(0, { code: 'NETWORK_ERROR', message: '无法连接到后端服务' });
  }

  const text = await response.text();

  if (!response.ok) {
    let body: ApiErrorResponse = { code: 'REQUEST_FAILED', message: response.statusText };
    try {
      if (text) {
        body = JSON.parse(text);
      }
    } catch {
      body = { code: 'REQUEST_FAILED', message: response.statusText };
    }
    throw new ApiClientError(response.status, body);
  }

  return JSON.parse(text || 'null');
}

function query(params: Record<string, string | boolean | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) {
      search.set(key, String(value));
    }
  });
  const text = search.toString();
  return text ? `?${text}` : '';
}

export function getProfile() {
  return request<UserProfile>('/api/v1/profile');
}

export function saveProfile(payload: UserProfileRequest) {
  return request<UserProfile>('/api/v1/profile', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function listHealthConstraints(params: { status?: ConstraintStatus; includeArchived?: boolean }) {
  return request<HealthConstraint[]>(`/api/v1/health-constraints${query(params)}`);
}

export function createHealthConstraint(payload: HealthConstraintRequest) {
  return request<HealthConstraint>('/api/v1/health-constraints', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateHealthConstraint(id: string, payload: HealthConstraintRequest) {
  return request<HealthConstraint>(`/api/v1/health-constraints/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function changeHealthConstraintStatus(id: string, status: ConstraintStatus) {
  return request<HealthConstraint>(`/api/v1/health-constraints/${id}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
}

export function archiveHealthConstraint(id: string, archiveReason: string) {
  return request<HealthConstraint>(`/api/v1/health-constraints/${id}/archive`, {
    method: 'POST',
    body: JSON.stringify({ archiveReason }),
  });
}

export function listGoals(params: { status?: GoalStatus; includeArchived?: boolean }) {
  return request<Goal[]>(`/api/v1/goals${query(params)}`);
}

export function createGoal(payload: GoalRequest) {
  return request<Goal>('/api/v1/goals', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateGoal(id: string, payload: GoalRequest) {
  return request<Goal>(`/api/v1/goals/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function changeGoalStatus(id: string, status: GoalStatus) {
  return request<Goal>(`/api/v1/goals/${id}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
}

export function archiveGoal(id: string, archiveReason: string) {
  return request<Goal>(`/api/v1/goals/${id}/archive`, {
    method: 'POST',
    body: JSON.stringify({ archiveReason }),
  });
}
