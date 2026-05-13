import type {
  ApiKeyCreated,
  BillingSummary,
  BackendOverride,
  BrandListResponse,
  BrandResponse,
  CapabilityInfo,
  ChatHistoryItem,
  ChatResponse,
  BrandKitResponse,
  IngestResponse,
  KeyListItem,
  ModuleInfo,
  OnboardingStatus,
  ProviderInfo,
  RunListResponse,
  RunResponse,
  WorkspaceDocument,
  WorkspaceResponse,
} from './types';

const BASE = '/api';
const GET_CACHE_MS = 2000;
const getCache = new Map<string, { expiresAt: number; value: unknown }>();
const inflightGets = new Map<string, Promise<unknown>>();

export function getApiKey(): string | null {
  return localStorage.getItem('bos_api_key');
}

export function setApiKey(key: string): void {
  localStorage.setItem('bos_api_key', key);
}

export function clearApiKey(): void {
  localStorage.removeItem('bos_api_key');
}

function extractMessage(body: Record<string, unknown>): string {
  // FastAPI wraps HTTPException detail under "detail"
  const detail = body?.detail;
  if (detail && typeof detail === 'object') {
    const d = detail as Record<string, unknown>;
    const msg = (d.error as Record<string, unknown>)?.message;
    if (typeof msg === 'string') return msg;
    if (typeof d.message === 'string') return d.message;
  }
  if (typeof detail === 'string') return detail;
  if (typeof body?.message === 'string') return body.message as string;
  const errMsg = (body?.error as Record<string, unknown>)?.message;
  if (typeof errMsg === 'string') return errMsg;
  return '';
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const key = getApiKey();
  const method = (options.method ?? 'GET').toUpperCase();
  const cacheKey = `${key ?? ''}:${path}`;

  if (method === 'GET') {
    const cached = getCache.get(cacheKey);
    if (cached && cached.expiresAt > Date.now()) return cached.value as T;

    const pending = inflightGets.get(cacheKey);
    if (pending) return pending as Promise<T>;
  }

  const run = async (): Promise<T> => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> ?? {}),
    };
    if (key) headers['X-API-Key'] = key;

    const res = await fetch(`${BASE}${path}`, { ...options, headers });

    if (res.status === 401 || res.status === 403) {
      clearApiKey();
      window.location.href = '/auth?error=1';
      throw new Error('Unauthorized');
    }

    if (res.status === 204) return undefined as T;

    const body = await res.json().catch(() => ({})) as Record<string, unknown>;
    if (!res.ok) {
      const msg = extractMessage(body) || `Request failed (${res.status})`;
      const err = new Error(msg) as Error & { status: number };
      err.status = res.status;
      throw err;
    }

    if (method === 'GET') {
      getCache.set(cacheKey, { expiresAt: Date.now() + GET_CACHE_MS, value: body });
    } else {
      getCache.clear();
    }

    return body as T;
  };

  if (method !== 'GET') return run();

  const promise = run().finally(() => inflightGets.delete(cacheKey));
  inflightGets.set(cacheKey, promise);
  return promise;
}

export async function validateKey(key: string): Promise<{ valid: boolean; message: string }> {
  try {
    const res = await fetch(`${BASE}/workspace`, {
      headers: { 'X-API-Key': key, 'Content-Type': 'application/json' },
    });
    if (res.status === 401 || res.status === 403) {
      return { valid: false, message: 'Key not recognized — check it and try again' };
    }
    // 200 (workspace exists) or 412 (workspace not initialized) both mean key is valid
    return { valid: true, message: '' };
  } catch {
    return { valid: false, message: 'Could not reach the server' };
  }
}

function buildQuery(params?: Record<string, string | number | undefined>): string {
  if (!params) return '';
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') q.set(k, String(v));
  }
  const s = q.toString();
  return s ? '?' + s : '';
}

export const api = {
  bootstrap: () =>
    request<ApiKeyCreated>('/auth/bootstrap', { method: 'POST' }),

  getWorkspace: () =>
    request<WorkspaceResponse>('/workspace'),

  putWorkspace: (name: string) =>
    request<WorkspaceResponse>('/workspace', {
      method: 'PUT',
      body: JSON.stringify({ name }),
    }),

  putBrand: (brand: { voice?: string; tone?: string; values?: string[] }) =>
    request<WorkspaceResponse>('/workspace/brand', {
      method: 'PUT',
      body: JSON.stringify(brand),
    }),

  putProducts: (products: Array<{ id?: string; name: string; tagline?: string; benefits: string[] }>) =>
    request<WorkspaceResponse>('/workspace/products', {
      method: 'PUT',
      body: JSON.stringify({ products }),
    }),

  putAudiences: (audiences: Array<{ id?: string; name: string; demographics?: string; pain_points: string[] }>) =>
    request<WorkspaceResponse>('/workspace/audiences', {
      method: 'PUT',
      body: JSON.stringify({ audiences }),
    }),

  getVerticals: () =>
    request<{ verticals: Array<{ vertical: string; module_count: number }> }>('/verticals'),

  getModules: (vertical: string) =>
    request<{ vertical: string; modules: ModuleInfo[] }>(`/verticals/${vertical}/modules`),

  getCapabilities: () =>
    request<{ capabilities: CapabilityInfo[] }>('/capabilities'),

  getBackendOverrides: () =>
    request<{ overrides: BackendOverride[] }>('/settings/backends'),

  putBackendOverride: (target: string, body: { provider: string; model_id?: string | null; tool_id?: string | null; modality: string; strict: boolean }) =>
    request<BackendOverride>(`/settings/backends/${encodeURIComponent(target)}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  deleteBackendOverride: (target: string) =>
    request<void>(`/settings/backends/${encodeURIComponent(target)}`, { method: 'DELETE' }),

  postRun: (body: {
    module_id: string;
    policy: string;
    payload: { brief: Record<string, string> };
  }) =>
    request<RunResponse>('/runs', { method: 'POST', body: JSON.stringify(body) }),

  getRuns: (params?: {
    module_id?: string;
    status?: string;
    created_after?: string;
    created_before?: string;
    limit?: number;
    offset?: number;
  }) =>
    request<RunListResponse>('/runs' + buildQuery(params as Record<string, string | number | undefined>)),

  getRun: (runId: string) =>
    request<RunResponse>(`/runs/${runId}`),

  getProviders: (brand_id?: string) =>
    request<{ providers: ProviderInfo[] }>('/providers' + buildQuery({ brand_id })),

  getProviderKeys: (brand_id?: string) =>
    request<KeyListItem[]>('/providers/keys' + buildQuery({ brand_id })),

  registerKey: (provider: string, key: string, brand_id?: string) =>
    request<{ provider: string; brand_id?: string | null; status: string }>('/providers/keys', {
      method: 'POST',
      body: JSON.stringify({ provider, key, brand_id: brand_id || undefined }),
    }),

  startProviderLogin: (provider: string) =>
    request<{ provider: string; auth_mode: 'oauth'; login_id: string; login: { type: string; authorize_url?: string; user_code?: string; verification_uri?: string } }>('/providers/login', {
      method: 'POST',
      body: JSON.stringify({ provider }),
    }),

  completeProviderLogin: (provider: string, login_id: string, callback_url: string) =>
    request<{ provider: string; connected: boolean; auth_mode: string; expires_at?: string | null }>('/providers/login/complete', {
      method: 'POST',
      body: JSON.stringify({ provider, login_id, callback_url }),
    }),

  deleteKey: (provider: string, brand_id?: string) =>
    request<void>(`/providers/keys/${provider}` + buildQuery({ brand_id }), { method: 'DELETE' }),

  deleteProviderAuth: (provider: string) =>
    request<void>(`/providers/auth/${provider}`, { method: 'DELETE' }),

  checkKey: (provider: string, brand_id?: string) =>
    request<{ provider: string; status: string; message: string; auth_mode?: string | null }>('/providers/check', {
      method: 'POST',
      body: JSON.stringify({ provider, brand_id: brand_id || undefined }),
    }),

  getBillingSummary: () =>
    request<BillingSummary>('/billing/summary'),

  chat: (message: string, history: ChatHistoryItem[], brandId?: string | null, campaignId?: string | null) =>
    request<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify({ message, history, brand_id: brandId ?? null, campaign_id: campaignId ?? null }),
    }),

  getBrands: () =>
    request<BrandListResponse>('/brands'),

  createBrand: (body: { name: string; voice?: string; tone?: string; values?: string[]; domain?: string; website_url?: string; social_handles?: Record<string, string> }) =>
    request<BrandResponse>('/brands', { method: 'POST', body: JSON.stringify(body) }),

  getBrand: (brandId: string) =>
    request<BrandResponse>(`/brands/${brandId}`),

  updateBrand: (brandId: string, body: Partial<{ name: string; voice: string; tone: string; values: string[]; domain: string; website_url: string; social_handles: Record<string, string> }>) =>
    request<BrandResponse>(`/brands/${brandId}`, { method: 'PUT', body: JSON.stringify(body) }),

  deleteBrand: (brandId: string) =>
    request<void>(`/brands/${brandId}`, { method: 'DELETE' }),

  claimWorkspaceBrand: (brandId: string) =>
    request<{ brand: BrandResponse; claimed: Record<string, number> }>(`/brands/${brandId}/claim-workspace`, { method: 'POST' }),

  approveRun: (runId: string) =>
    request<{ run_id: string; approval_status: string }>(`/runs/${runId}/approve`, { method: 'PATCH' }),

  rejectRun: (runId: string, feedback: string) =>
    request<{ run_id: string; approval_status: string; feedback?: string }>(`/runs/${runId}/reject`, {
      method: 'PATCH',
      body: JSON.stringify({ feedback }),
    }),

  reviseRun: (runId: string, feedback?: string) =>
    request<RunResponse>(`/runs/${runId}/revise`, {
      method: 'POST',
      body: JSON.stringify({ feedback: feedback || undefined }),
    }),

  chatReviseRun: (runId: string, feedback: string, history: ChatHistoryItem[]) =>
    request<ChatResponse>(`/chat/runs/${runId}/revise`, {
      method: 'POST',
      body: JSON.stringify({ feedback, history }),
    }),

  ingestBrandDoc: (document_text: string, workspace_name?: string, brand_id?: string) =>
    request<IngestResponse>('/onboarding/ingest', {
      method: 'POST',
      body: JSON.stringify({ document_text, workspace_name: workspace_name || undefined, brand_id: brand_id || undefined }),
    }),

  getOnboardingStatus: () =>
    request<OnboardingStatus>('/onboarding/status'),

  generateBrandKit: (additional_context?: string, brand_id?: string) =>
    request<BrandKitResponse>('/onboarding/brand-kit', {
      method: 'POST',
      body: JSON.stringify({ additional_context: additional_context || undefined, brand_id: brand_id || undefined }),
    }),

  getLatestBrandKit: (status?: string, brand_id?: string) =>
    request<WorkspaceDocument>('/onboarding/brand-kit/latest' + buildQuery({ status, brand_id })),

  getDocuments: (params?: { doc_type?: string; status?: string; brand_id?: string }) =>
    request<WorkspaceDocument[]>('/workspace/documents' + buildQuery(params)),

  updateDocument: (documentId: string, body: Partial<Pick<WorkspaceDocument, 'title' | 'content_markdown' | 'status' | 'tags' | 'metadata'>>) =>
    request<WorkspaceDocument>(`/workspace/documents/${documentId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  approveDocument: (documentId: string) =>
    request<WorkspaceDocument>(`/workspace/documents/${documentId}/approve`, { method: 'POST' }),

  startSocialConnect: (brand_id: string, platform = 'gmail') =>
    request<{ session_id: string; authorize_url: string; platform: string }>('/social/connect/start', {
      method: 'POST',
      body: JSON.stringify({ brand_id, platform }),
    }),

  listSocialConnections: (brand_id?: string) =>
    request<{ id: string; brand_id: string | null; platform: string; page_id: string; page_name: string | null; page_handle: string | null; status: string }[]>(
      `/social/connections${brand_id ? `?brand_id=${brand_id}` : ''}`
    ),

  getPendingPages: (session_id: string) =>
    request<{ brand_id: string; pages: { page_id: string; page_name: string | null; page_handle: string | null }[] }>(
      `/social/connect/pages/${session_id}`
    ),

  selectSocialPage: (session_id: string, page_id: string) =>
    request<{ status: string; page_name: string; page_id: string }>('/social/connect/select-page', {
      method: 'POST',
      body: JSON.stringify({ session_id, page_id }),
    }),

  disconnectSocial: (connection_id: string) =>
    request<{ status: string }>(`/social/connections/${connection_id}`, { method: 'DELETE' }),
};
