export interface PluginInfo {
  plugin_id: string;
  name: string;
  version: string;
  implements: string[];
  requires_platform_vars: string[];
  credentials_configured: boolean;
  missing_vars: string[];
  credential_source: 'database' | 'env_var' | 'partial' | 'none';
}

export interface BrandOut {
  voice?: string;
  tone?: string;
  values?: string[];
}

export interface ProductOut {
  id: string;
  name: string;
  tagline?: string;
  benefits: string[];
  brand_id?: string | null;
}

export interface AudienceOut {
  id: string;
  name: string;
  demographics?: string;
  pain_points: string[];
  brand_id?: string | null;
}

export interface WorkspaceResponse {
  id: string;
  name: string;
  brand: BrandOut | null;
  products: ProductOut[];
  audiences: AudienceOut[];
  created_at: string;
  updated_at: string;
}

export interface ModuleInfo {
  id: string;
  vertical: string;
  capability: string;
  platform_hint: string;
  policy_default: string;
  constraints: {
    max_chars: number;
    must_mention: string[];
    banned_phrases: string[];
  };
}

export interface RunResultOut {
  content: string;
  self_check: string;
  platform?: string;
  headline?: string;
  description?: string;
  display_url?: string;
  dimensions?: string;
  cta?: string;
  brand_name?: string;
  brand_handle?: string;
  subject?: string;
  preheader?: string;
  block?: any; // Module-specific structured block (performance_report, facebook_campaign_plan, etc.)
}

export interface RunExecutionOut {
  provider: string;
  model: string;
  mode: string;
  attempts: number;
  latency_ms: number;
  tokens_used?: number;
  provider_cost?: number;
  sell_price?: number;
}

export interface RunTraceOut {
  capability: string;
  policy: string;
  candidates_considered: number;
  candidates_filtered: number;
  winner?: string;
  routing_reason: string;
}

export interface RunResponse {
  run_id: string;
  module_id: string;
  vertical: string;
  status: string;
  approval_status?: string | null;
  campaign_id?: string | null;
  brand_id?: string | null;
  result?: RunResultOut;
  execution?: RunExecutionOut;
  trace?: RunTraceOut;
  created_at: string;
}

export interface RunListItem {
  run_id: string;
  module_id: string;
  vertical: string;
  status: string;
  approval_status?: string | null;
  campaign_id?: string | null;
  campaign_name?: string | null;
  brand_id?: string | null;
  created_at: string;
  provider?: string | null;
  model?: string | null;
  latency_ms?: number | null;
  tokens?: number | null;
  cost?: number | null;
}

export interface RunListResponse {
  runs: RunListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface CapabilityInfo {
  key: string;
  modality: string;
  budget_ceiling: number;
  latency_target_ms: number;
  model_options: Array<{
    provider: string;
    model_id: string;
    quality_tier: string;
    input_cost_per_token: number;
    output_cost_per_token: number;
    latency_ms: number;
    supports_json: boolean;
    status: string;
  }>;
}

export interface BackendOverride {
  target: string;
  provider: string;
  model_id?: string | null;
  tool_id?: string | null;
  modality: string;
  strict: boolean;
  source: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ProviderModelInfo {
  model_id: string;
  capability?: string | null;
  quality_tier: string;
  latency_ms: number;
  supports_json: boolean;
  status: string;
}

export interface ProviderInfo {
  provider: string;
  brand_id?: string | null;
  model_count: number;
  status: string;
  auth_supported: string[];
  connected: boolean;
  auth_mode?: string | null;
  expires_at?: string | null;
  has_platform_key: boolean;
  has_byok_key: boolean;
  avg_latency_ms?: number | null;
  last_used_at?: string | null;
  last_check_status?: string | null;
  last_check_message?: string | null;
  last_check_at?: string | null;
  top_models: ProviderModelInfo[];
}

export interface KeyListItem {
  provider: string;
  brand_id?: string | null;
  created_at: string;
}

export interface BillingSummary {
  total_runs: number;
  successful_runs: number;
  total_provider_cost: number;
  total_sell_price: number;
  total_tokens: number;
}

export interface ApiKeyCreated {
  key: string;
  key_id: string;
  label: string;
  created_at: string;
}

export interface WorkspaceDocument {
  id: string;
  workspace_id: string;
  brand_id?: string | null;
  doc_type: string;
  title: string;
  content_markdown: string;
  status: string;
  tags: string[];
  metadata: Record<string, unknown>;
  source_run_id?: string | null;
  approved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface IngestResponse {
  run_id: string;
  brand_name: string;
  workspace: WorkspaceResponse;
  profile?: {
    brand_name?: string;
    voice?: string;
    tone?: string;
    values?: string[];
  };
}

export interface BrandKitResponse {
  run_id: string;
  document: WorkspaceDocument;
}

export interface OnboardingStatus {
  workspace_configured: boolean;
  workspace_name?: string | null;
  brand_profile_configured: boolean;
  campaign_brand_kit_approved: boolean;
  campaign_brand_kit_document_id?: string | null;
  all_ready: boolean;
  issues: string[];
}

export interface ChatHistoryItem {
  role: 'user' | 'ai';
  text: string;
}

export interface KlarAction {
  action: 'brand_switch' | 'brand_clear' | 'plan_draft' | 'plan_confirmed' | 'pending_klar' | 'evaluate_stub' | 'pending_summary' | 'brand_list';
  data: Record<string, unknown>;
}

export interface ArtifactRef {
  artifact_id: string;
  title: string;
  type: 'draft_artifact' | 'plan_artifact' | 'intelligence_artifact' | 'action_result' | 'decision_artifact';
  status: 'pending_review' | 'approved' | 'dismissed' | 'saved' | 'failed';
  renderer: string;
  workspace_url: string;
}

export interface ChatResponse {
  reply: string;
  runs?: RunResponse[];
  run?: RunResponse;
  artifact_refs?: ArtifactRef[];
  module_id?: string;
  klar_action?: KlarAction | null;
}

export interface BrandProfile {
  voice: string;
  tone: string;
  values: string[];
  domain: string;
  website_url: string;
  social_handles: Record<string, string>;
}

export interface BrandResponse {
  id: string;
  workspace_id: string;
  name: string;
  voice: string;
  tone: string;
  values: string[];
  domain: string;
  website_url: string;
  social_handles: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface BrandListResponse {
  brands: BrandResponse[];
  total: number;
}

export interface SocialConnectionResponse {
  id: string;
  brand_id: string | null;
  platform: string;
  page_id: string;
  page_name: string | null;
  page_handle: string | null;
  status: string;
}

export interface SocialConnectStartResponse {
  session_id: string;
  authorize_url: string;
  platform: string;
}

export interface SocialPageOption {
  page_id: string;
  page_name: string | null;
  page_handle: string | null;
}

export interface CalendarPageResponse {
  id: string;
  workspace_id: string;
  brand_id: string | null;
  connection_id: string | null;
  slug: string;
  title: string;
  description: string | null;
  duration_minutes: number;
  buffer_minutes: number;
  working_hours_json: Record<string, { start: string; end: string }> | null;
  timezone: string;
  max_days_ahead: number;
  is_active: boolean;
  embed_url: string;
  created_at: string;
  updated_at: string;
}

export interface BookingResponse {
  id: string;
  attendee_name: string;
  attendee_email: string;
  start_at: string;
  end_at: string;
  status: string;
  created_at: string;
}
