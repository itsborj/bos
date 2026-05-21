import type {
  ApiKeyCreated,
  BillingSummary,
  BackendOverride,
  BrandListResponse,
  BrandResponse,
  CapabilityInfo,
  ChatHistoryItem,
  ChatResponse,
  ChatStreamEvent,
  BrandKitResponse,
  DecisionBriefListResponse,
  DecisionBriefOut,
  EvaluateOutcomeOut,
  HandoffBriefOut,
  IngestResponse,
  KeyListItem,
  MemoryEventListResponse,
  ModuleInfo,
  ObjectiveListResponse,
  ObjectiveOut,
  OnboardingStatus,
  OutcomeListResponse,
  PendingDecisionListResponse,
  ProviderInfo,
  AgentStateResponse,
  RunListResponse,
  RunResponse,
  StreamListResponse,
  StreamRefreshOut,
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
    approval_status?: string;
    created_after?: string;
    created_before?: string;
    limit?: number;
    offset?: number;
  }) =>
    request<RunListResponse>('/runs' + buildQuery(params as Record<string, string | number | undefined>)),

  getRun: (runId: string) =>
    request<RunResponse>(`/runs/${runId}`),

  getAgentState: () =>
    request<AgentStateResponse>('/agent/state'),

  getStream: (include_read = false) =>
    request<StreamListResponse>('/stream' + buildQuery({ include_read: include_read ? 'true' : undefined })),

  refreshStream: () =>
    request<StreamRefreshOut>('/stream/refresh', { method: 'POST' }),

  dismissStreamUpdate: (updateId: string) =>
    request<import('./types').StreamUpdateOut>(`/stream/${updateId}`, { method: 'DELETE' }),

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

  async *chatStream(
    message: string,
    history: ChatHistoryItem[],
    brandId?: string | null,
    campaignId?: string | null,
  ): AsyncGenerator<ChatStreamEvent> {
    const key = getApiKey();
    const resp = await fetch(`${BASE}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(key ? { 'X-API-Key': key } : {}),
      },
      body: JSON.stringify({ message, history, brand_id: brandId ?? null, campaign_id: campaignId ?? null }),
    });
    if (!resp.ok) throw new Error(`Chat stream failed: ${resp.status}`);
    const reader = resp.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() ?? '';
      for (const part of parts) {
        const line = part.trim();
        if (line.startsWith('data: ')) {
          try {
            yield JSON.parse(line.slice(6)) as ChatStreamEvent;
          } catch {
            // malformed event — skip
          }
        }
      }
    }
  },

  getBrands: () =>
    request<BrandListResponse>('/brands'),

  createBrand: (body: { name: string; voice?: string; tone?: string; values?: string[]; domain?: string; website_url?: string; social_handles?: Record<string, string> }) =>
    request<BrandResponse>('/brands', { method: 'POST', body: JSON.stringify(body) }),

  getBrand: (brandId: string) =>
    request<BrandResponse>(`/brands/${brandId}`),

  updateBrand: (brandId: string, body: Partial<{ name: string; voice: string; tone: string; values: string[]; domain: string; website_url: string; social_handles: Record<string, string>; pm_config: import('./types').PmConfig | null }>) =>
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

  facebookPendingPages: (session_id: string) =>
    request<{ pages: { id: string; name: string }[] }>(`/social/facebook/pending-pages?session_id=${session_id}`),

  facebookSelectPage: (session_id: string, page_id: string) =>
    request<{ status: string; page_id: string; page_name: string }>('/social/facebook/select-page', {
      method: 'POST',
      body: JSON.stringify({ session_id, page_id }),
    }),

  disconnectSocial: (connection_id: string) =>
    request<{ status: string }>(`/social/connections/${connection_id}`, { method: 'DELETE' }),

  listPlugins: () =>
    request<{ plugins: import('./types').PluginInfo[] }>('/plugins'),

  savePluginCredentials: (pluginId: string, vars: Record<string, string>) =>
    request<{ ok: boolean; plugin_id: string }>(`/plugins/${encodeURIComponent(pluginId)}/credentials`, {
      method: 'POST',
      body: JSON.stringify({ vars }),
    }),

  resolvePluginWorkspaces: (pluginId: string, apiToken: string) =>
    request<{ workspaces: { id: string; name: string }[] }>(`/plugins/${encodeURIComponent(pluginId)}/resolve-workspaces`, {
      method: 'POST',
      body: JSON.stringify({ api_token: apiToken }),
    }),

  deletePluginCredentials: (pluginId: string) =>
    request<void>(`/plugins/${encodeURIComponent(pluginId)}/credentials`, { method: 'DELETE' }),

  listCalendarPages: (brand_id?: string) =>
    request<import('./types').CalendarPageResponse[]>(
      `/calendar/pages${brand_id ? `?brand_id=${brand_id}` : ''}`
    ),

  createCalendarPage: (body: {
    brand_id?: string;
    connection_id?: string;
    slug: string;
    title: string;
    description?: string;
    duration_minutes?: number;
    buffer_minutes?: number;
    timezone?: string;
    max_days_ahead?: number;
    is_active?: boolean;
  }) =>
    request<import('./types').CalendarPageResponse>('/calendar/pages', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateCalendarPage: (pageId: string, body: Partial<{ title: string; description: string; duration_minutes: number; buffer_minutes: number; timezone: string; max_days_ahead: number; is_active: boolean; connection_id: string }>) =>
    request<import('./types').CalendarPageResponse>(`/calendar/pages/${pageId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteCalendarPage: (pageId: string) =>
    request<{ status: string }>(`/calendar/pages/${pageId}`, { method: 'DELETE' }),

  listBookings: (page_id?: string, brand_id?: string) => {
    const params = new URLSearchParams();
    if (page_id) params.set('page_id', page_id);
    if (brand_id) params.set('brand_id', brand_id);
    const qs = params.toString();
    return request<import('./types').BookingResponse[]>(`/calendar/bookings${qs ? `?${qs}` : ''}`);
  },

  cancelBooking: (bookingId: string) =>
    request<{ status: string }>(`/calendar/bookings/${bookingId}`, { method: 'DELETE' }),

  // Gate 2 — Objectives
  getObjectives: (params?: { brand_id?: string; status?: string; limit?: number }) =>
    request<ObjectiveListResponse>('/objectives' + buildQuery(params as Record<string, string | number | undefined>)),

  getActiveObjective: (brand_id?: string) =>
    request<ObjectiveOut>('/objectives/active' + buildQuery({ brand_id })),

  createObjective: (body: { brand_id?: string; summary: string; success_metric: string; horizon: string; status?: string; created_from?: string }) =>
    request<ObjectiveOut>('/objectives', { method: 'POST', body: JSON.stringify(body) }),

  patchObjective: (id: string, body: Partial<{ status: string; summary: string; success_metric: string; horizon: string }>) =>
    request<ObjectiveOut>(`/objectives/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),

  // Gate 2 — Outcomes
  getOutcomes: (params?: { brand_id?: string; objective_id?: string; limit?: number }) =>
    request<OutcomeListResponse>('/outcomes' + buildQuery(params as Record<string, string | number | undefined>)),

  evaluateOutcome: (body: { brand_id?: string; objective_id?: string; summary: string; metrics?: Record<string, unknown>; topic_tags?: string[]; confidence_source?: string; source_ref?: string }) =>
    request<EvaluateOutcomeOut>('/outcomes/evaluate', { method: 'POST', body: JSON.stringify(body) }),

  // Gate 2 — Memory events
  getMemoryEvents: (params?: { brand_id?: string; objective_id?: string; event_type?: string; limit?: number }) =>
    request<MemoryEventListResponse>('/memory/events' + buildQuery(params as Record<string, string | number | undefined>)),

  // Gate 2 — Decision briefs
  getDecisionBriefs: (params?: { brand_id?: string; objective_id?: string; limit?: number }) =>
    request<DecisionBriefListResponse>('/decision-briefs' + buildQuery(params as Record<string, string | number | undefined>)),

  generateDecisionBrief: (body: { brand_id?: string; objective_id?: string }) =>
    request<DecisionBriefOut>('/decision-briefs/generate', { method: 'POST', body: JSON.stringify(body) }),

  // Gate 2 — Pending decisions
  getPendingDecisions: (params?: { brand_id?: string; objective_id?: string; status?: string }) =>
    request<PendingDecisionListResponse>('/pending-decisions' + buildQuery(params as Record<string, string | number | undefined>)),

  resolvePendingDecision: (id: string, resolution_summary?: string) =>
    request<{ status: string }>(`/pending-decisions/${id}/resolve`, { method: 'POST', body: JSON.stringify({ resolution_summary }) }),

  // Gate 2 — Handoff brief
  getHandoffBrief: (brand_id?: string) =>
    request<HandoffBriefOut>('/handoff/brief' + buildQuery({ brand_id })),
};
