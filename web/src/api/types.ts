export interface MediaModelOption {
  value: string;
  label: string;
}

export interface MediaProviderOption {
  provider: string;
  label: string;
  models: MediaModelOption[];
}

export interface PluginConnectionInfo {
  platform: string;
  type: string;
  scopes: string[];
  client_id_var?: string | null;
  client_secret_var?: string | null;
  redirect_uri_var?: string | null;
  validate_capability?: string | null;
  display_name?: string | null;
  icon?: string | null;
}

export interface ActivationState {
  brand_id: string | null;  // null = org-level
  status: 'active' | 'inactive' | 'error';
  error_reason?: string | null;
}

export interface PluginInfo {
  plugin_id: string;
  name: string;
  version: string;
  source: 'external' | 'internal';
  status: 'installed' | 'error';
  reason?: string | null;
  capability_ids: string[];
  implements: string[];
  requires_platform_vars: string[];
  requires_social_connection: string[];
  credentials_configured: boolean;
  missing_vars: string[];
  credential_source: 'database' | 'env_var' | 'partial' | 'none';
  activation_by_brand: ActivationState[];
  media_provider_options?: MediaProviderOption[];
  media_modality?: 'image' | 'video' | null;
  connections?: PluginConnectionInfo[];
  supports_backend_override?: boolean;
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
  name?: string;
  vertical: string;
  capability: string;
  platform_hint: string;
  policy_default: string;
  internal?: boolean;
  uses_llm?: boolean;
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
  brand_name?: string | null;
  result?: RunResultOut;
  execution?: RunExecutionOut;
  trace?: RunTraceOut;
  created_at: string;
}

export interface RunActionResponse {
  source_run_id: string;
  source_approval_status: string;
  action: string;
  action_run: RunResponse;
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
  brand_name?: string | null;
  created_at: string;
  provider?: string | null;
  model?: string | null;
  latency_ms?: number | null;
  tokens?: number | null;
  cost?: number | null;
  result?: RunResultOut | null;
}

export interface RunListResponse {
  runs: RunListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface AgentBrandState {
  brand_id: string;
  name: string;
  pending_approvals: number;
  pm_sync_enabled: boolean;
}

export interface AgentStateResponse {
  workspace_name: string;
  brands: AgentBrandState[];
  total_pending: number;
}

export interface StreamUpdateOut {
  id: string;
  type: string;
  layout_hint: string;
  interaction: string;
  priority: 'urgent' | 'high' | 'normal' | 'low' | string;
  data_json: any;
  campaign_id?: string | null;
  source_key?: string | null;
  created_at: string;
  read_at?: string | null;
  dismissed_at?: string | null;
}

export interface StreamListResponse {
  updates: StreamUpdateOut[];
  total: number;
}

export interface StreamRefreshOut {
  created: number;
  message: string;
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

export interface FallbackModel {
  provider: string;
  model_id?: string | null;
  tool_id?: string | null;
  routing_hints?: Record<string, unknown>;
}

export interface BackendOverride {
  target: string;
  provider: string;
  model_id?: string | null;
  tool_id?: string | null;
  modality: string;
  strict: boolean;
  fallbacks: FallbackModel[];
  routing_hints: Record<string, unknown>;
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
  auth_mode: string;
  created_at: string;
}

export interface BillingSummary {
  total_runs: number;
  successful_runs: number;
  total_provider_cost: number;
  total_sell_price: number;
  total_tokens: number;
  platform_provider_cost?: number;
  byok_provider_cost?: number;
  oauth_provider_cost?: number;
  external_provider_cost?: number;
  platform_tokens?: number;
  byok_tokens?: number;
  oauth_tokens?: number;
  gross_margin?: number;
  missing_sell_price_runs?: number;
  missing_sell_price_provider_cost?: number;
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

export interface BrandKitTemplateManifest {
  version: string;
  templates: BrandKitTemplate[];
  selection_policy: {
    default_renderer: string;
    confidence_threshold: number;
    manual_review_required: boolean;
    [key: string]: unknown;
  };
}

export interface BrandKitTemplate {
  id: string;
  brand_id?: string;
  name: string;
  status: string;
  renderer: string;
  format: string;
  content_type: string;
  objective_fit?: string[];
  tone?: string[];
  copy_density?: string;
  required_slots?: string[];
  optional_slots?: string[];
  forbidden_slots?: string[];
  priority?: number;
  source?: { provider?: string; drive_file_id?: string; web_view_link?: string };
  [key: string]: unknown;
}

export interface BrandKitResource {
  id: string;
  provider: string;
  name: string;
  mime_type?: string;
  web_view_link?: string;
  resource_type: string;
  resource_label: string;
  classification: string;
  template?: BrandKitTemplate;
}

export interface BrandKitResourcesResponse {
  brand_id: string;
  brand_kit_document_id?: string | null;
  template_manifest: BrandKitTemplateManifest;
  resources: BrandKitResource[];
}

export interface BrandKitTemplateMutationResponse {
  brand_kit_document_id: string;
  template_manifest: BrandKitTemplateManifest;
}

export interface BrandKitResponse {
  run_id: string;
  document: WorkspaceDocument;
}

export interface ClientReadinessCell {
  ok: boolean;
  label: string;
}

export interface ClientReadinessAction {
  key: string;
  label: string;
}

export interface ClientReadinessSnapshot {
  brief: ClientReadinessCell;
  brand_kit: ClientReadinessCell;
  drive: ClientReadinessCell;
  capabilities: ClientReadinessCell;
  publish_channels: string[];
  blockers: string[];
  next_action?: ClientReadinessAction | null;
  drive_setup_debt: boolean;
}

export interface OnboardingStatus {
  workspace_configured: boolean;
  workspace_name?: string | null;
  brand_profile_configured: boolean;
  campaign_brand_kit_approved: boolean;
  campaign_brand_kit_document_id?: string | null;
  live_campaign_present?: boolean;
  live_campaign_id?: string | null;
  drive_connected?: boolean;
  drive_connection_status?: string | null;
  drive_root_folder_id?: string | null;
  drive_root_name?: string | null;
  brand_mark_configured?: boolean;
  brand_mark_file_id?: string | null;
  brand_mark_file_name?: string | null;
  client_readiness: ClientReadinessSnapshot;
  all_ready: boolean;
  issues: string[];
}

export interface ChatHistoryItem {
  role: 'user' | 'ai';
  text: string;
}

export interface ChatReference {
  id?: string;
  kind: 'text' | 'image' | 'document';
  source: 'inline' | 'upload' | 'google_drive';
  title?: string;
  notes?: string;
  text?: string;
  drive_file_id?: string;
  drive_file_name?: string;
  drive_web_view_link?: string;
  mime_type?: string;
  thumbnail_link?: string;
  storage_url?: string;
  sha256?: string;
  metadata_json?: Record<string, unknown>;
  extraction_status?: string;
  extraction_error?: string;
  extracted_chars?: number;
  extraction_json?: Record<string, unknown>;
  variables_json?: Record<string, unknown>;
}

export interface ReferencePatch {
  reference_id: string;
  op: 'add' | 'replace' | 'remove';
  path: string;
  value?: unknown;
  reason?: string;
}

export interface DriveReferenceUploadResponse extends ChatReference {
  drive_folder_id?: string;
}

export interface KlarAction {
  action: 'brand_switch' | 'brand_clear' | 'plan_draft' | 'plan_confirmed' | 'pending_klar' | 'evaluate_stub' | 'pending_summary' | 'brand_list' | 'council_session';
  data: Record<string, unknown>;
}

export interface CouncilPosition {
  seat_id: string;
  display_name: string;
  content: string;
  timestamp: string;
  round?: number;
}

export interface CouncilSessionState {
  session_id: string;
  status: string;
  brief?: string;
  current_round: number;
  rounds_completed: number;
  rounds: CouncilPosition[][];
  c6_injections: Array<{ round_boundary: number; content: string; timestamp: string }>;
  pending_c6_prompt: string | null;
  safety_ceiling: number;
}

export interface CouncilFinalizeResult {
  session_id: string;
  status: string;
  brief: string;
  settlement: string;
  marching_orders: string[];
  parked_decisions: string[];
  c6_injections: Array<{ round_boundary: number; content: string; timestamp: string }>;
  rounds_completed: number;
  transcript: string;
}

export interface ObjectiveOut {
  id: string;
  workspace_id: string;
  brand_id: string | null;
  status: 'draft' | 'active' | 'paused' | 'completed' | 'archived';
  summary: string;
  success_metric: string;
  horizon: string;
  created_from: string;
  created_at: string;
  updated_at: string;
}

export interface ObjectiveListResponse {
  objectives: ObjectiveOut[];
  total: number;
}

export interface OutcomeRecordOut {
  id: string;
  workspace_id: string;
  brand_id: string | null;
  objective_id: string | null;
  source_ref: string | null;
  summary: string;
  metrics_json: Record<string, unknown>;
  confidence_source: string;
  full_record: Record<string, unknown>;
  recorded_at: string;
  created_at: string;
}

export interface OutcomeListResponse {
  outcomes: OutcomeRecordOut[];
  total: number;
}

export interface EvaluateOutcomeOut {
  outcome: OutcomeRecordOut;
  memory_event_id: string;
}

export interface MemoryEventOut {
  id: string;
  workspace_id: string;
  brand_id: string | null;
  objective_id: string | null;
  event_type: string;
  topic_tags: string[];
  summary: string;
  rationale: string | null;
  source_ref: string | null;
  full_record: Record<string, unknown>;
  created_at: string;
}

export interface MemoryEventListResponse {
  events: MemoryEventOut[];
  total: number;
}

export interface DecisionBriefOut {
  id: string;
  workspace_id: string;
  brand_id: string | null;
  objective_id: string | null;
  status: string;
  summary: string;
  objective_affected: string | null;
  evidence: unknown[];
  hypothesis_ranking: unknown[];
  confidence: string;
  recommended_next: string;
  do_not_list: unknown[];
  allowed_actions: unknown[];
  source_refs: unknown[];
  full_record: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DecisionBriefListResponse {
  decision_briefs: DecisionBriefOut[];
  total: number;
}

export interface PendingDecisionOut {
  id: string;
  workspace_id: string;
  brand_id: string | null;
  objective_id: string | null;
  status: string;
  what_is_deferred: string;
  waiting_for: string;
  leading_hypothesis: string | null;
  action_blocked: string;
  source_ref: string | null;
  full_record: Record<string, unknown>;
  created_at: string;
  resolved_at: string | null;
}

export interface PendingDecisionListResponse {
  pending_decisions: PendingDecisionOut[];
  total: number;
}

export interface HandoffBriefOut {
  brand_id: string | null;
  generated_at: string;
  active_objectives: Record<string, unknown>[];
  performance_narrative: Record<string, unknown>;
  pending_decisions: PendingDecisionOut[];
  committed_actions: Record<string, unknown>[];
  known_risks: string[];
  working: string[];
  not_working: string[];
  decided_against: string[];
  recommended_first_action: string;
}

export interface ArtifactRef {
  artifact_id: string;
  title: string;
  type: 'draft_artifact' | 'plan_artifact' | 'intelligence_artifact' | 'action_result' | 'decision_artifact' | 'setup_blocker';
  status: 'pending_review' | 'approved' | 'dismissed' | 'saved' | 'failed';
  renderer: string;
  workspace_url: string;
}

export type ChatStreamEvent =
  | { type: 'step'; label: string }
  | { type: 'text_delta'; text: string }
  | { type: 'module_result'; artifact_ref: ArtifactRef }
  | { type: 'reference_patch'; patch: ReferencePatch }
  | { type: 'reply'; text: string; klar_action: KlarAction | null }
  | { type: 'done'; campaign_id?: string | null }
  | { type: 'error'; message: string };

export interface ChatResponse {
  reply: string;
  runs?: RunResponse[];
  run?: RunResponse;
  artifact_refs?: ArtifactRef[];
  module_id?: string;
  campaign_id?: string | null;
  klar_action?: KlarAction | null;
  reference_patches?: ReferencePatch[];
}

export interface BrandProfile {
  voice: string;
  tone: string;
  values: string[];
  domain: string;
  website_url: string;
  social_handles: Record<string, string>;
}

export interface PmConfig {
  plugin: string;
  sync_enabled: boolean;
  list_id: string;
  team_id?: string;
  status_map: { pending: string; approved: string; rejected: string };
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
  pm_config?: PmConfig | null;
  created_at: string;
  updated_at: string;
}

export interface BrandListResponse {
  brands: BrandResponse[];
  total: number;
}


export interface CampaignOut {
  id: string;
  name: string;
  status: string;
  brand_id?: string | null;
  objective_id?: string | null;
  audience?: string | null;
  message_angle?: string | null;
  campaign_json?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  signal?: { state: string; label: string } | null;
}

export interface CampaignRowOut {
  id: string;
  workspace_id: string;
  brand_id?: string | null;
  campaign_id: string;
  objective_id?: string | null;
  primary_kpi?: string | null;
  actual?: string | null;
  market?: string | null;
  distribution_channel?: string | null;
  channel_role?: string | null;
  time_period?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  source_type?: string | null;
  source_ref?: string | null;
  producer?: string | null;
  planned_activity?: string | null;
  actual_activity?: string | null;
  reach?: number | null;
  impressions?: number | null;
  engagement?: number | null;
  engagement_rate?: number | null;
  reach_metric?: string | null;
  engagement_metric?: string | null;
  action_metric?: string | null;
  efficiency_metric?: string | null;
  value_metric?: string | null;
  clicks?: number | null;
  leads?: number | null;
  calls?: number | null;
  qualified_calls?: number | null;
  conversions?: number | null;
  spend?: string | number | null;
  revenue?: string | number | null;
  source_health: string;
  freshness?: string | null;
  verification_status: string;
  objective_verdict: string;
  confidence?: string | null;
  what_changed?: string | null;
  top_learning?: string | null;
  recommended_action?: string | null;
  note?: string | null;
  blocker?: string | null;
  decision_needed?: string | null;
  owner?: string | null;
  next_action?: string | null;
  raw_payload?: Record<string, unknown> | null;
  evidence_refs?: unknown[] | null;
  created_at: string;
  updated_at?: string | null;
}

export interface CampaignSheetResponse {
  payload_type: 'campaign_sheet@v2' | string;
  campaign_id: string;
  campaign_name: string;
  objective_id?: string | null;
  rows: CampaignRowOut[];
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

export interface ProviderModelLive {
  provider: string;
  model_id: string;
  name: string;
  is_free: boolean;
  input_cost_per_token: number;
  output_cost_per_token: number;
  context_length: number;
  quality_tier: string;
  supports_json: boolean;
  modality: string; // "text" | "image" | "video"
}

export interface ProviderModelsResponse {
  models: ProviderModelLive[];
}

export interface CouncilSeat {
  seat_id: string;
  display_name: string;
  status: string;
  provider: string;
  model_id: string | null;
  ideology: string | null;
  config_error?: string | null;
}

export interface CouncilSeatUpdate {
  display_name: string;
  status: string;
  provider: string;
  model_id: string | null;
  ideology: string | null;
}
