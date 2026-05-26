import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { BackendOverride, CapabilityInfo, ModuleInfo, PluginInfo, ProviderInfo, SocialConnectionResponse } from '../../api/types';

const OAUTH_PLATFORMS: Record<string, { label: string; icon: string }> = {
  facebook:        { label: 'Facebook',        icon: '📘' },
  gmail:           { label: 'Gmail',           icon: '✉️' },
  google_calendar: { label: 'Google Calendar', icon: '📅' },
  google_drive:    { label: 'Google Drive',    icon: '▣' },
  youtube:         { label: 'YouTube',         icon: '▶️' },
  tiktok:          { label: 'TikTok',          icon: '🎵' },
};

type ConnectorSummary = {
  id: string;
  label: string;
  detail: string;
  description?: string;
  implements?: string[];
  missingVars?: string[];
  status: 'connected' | 'needs_setup' | 'available';
  statusText: string;
  actionLabel?: string;
  actionType?: 'plugin' | 'brands';
  pluginId?: string;
  removable?: boolean;
};

type SpecialistSummary = {
  key: string;
  name: string;
  description: string;
  jobs: string[];
  specialties: string[];
  readiness: 'ready' | 'needs_setup' | 'installed';
  readinessText: string;
  risk: string;
  moduleCount: number;
  moduleIds: string[];
  capabilityKeys: string[];
  llmModuleIds: string[];
  connectors: ConnectorSummary[];
  nextStep?: string;
  pluginId?: string;
};

type ModelChoice = {
  value: string;
  provider: string;
  model_id: string;
  label: string;
  capability?: string;
};

type SocialConnection = SocialConnectionResponse;
type ClickUpStep = 'token' | 'workspace';
type ClickUpWorkspace = { id: string; name: string };

function titleCase(value: string): string {
  return value
    .replace(/[_.-]/g, ' ')
    .split(' ')
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function implementedJobs(mod: ModuleInfo): string[] {
  const value = `${mod.id} ${mod.capability}`.toLowerCase();
  const jobs = new Set<string>();
  if (/plan|strategy|launch|campaign/.test(value)) jobs.add('marketing.plan');
  if (/copy|draft|send|email|creative|outreach|execute|publish|asset/.test(value)) jobs.add('marketing.execute');
  if (/analytics|tracking|seo|report|receive|inbox|optimi[sz]e|audit|read|performance/.test(value)) jobs.add('marketing.optimize');
  if (/booking|calendar|scheduling/.test(value)) jobs.add('scheduling.booking');
  if (!jobs.size && mod.vertical === 'marketing') jobs.add('marketing.execute');
  return [...jobs];
}

function groupKey(mod: ModuleInfo): string {
  const id = mod.id.toLowerCase();
  const capability = mod.capability.toLowerCase();
  const text = `${id} ${capability} ${mod.platform_hint}`.toLowerCase();
  if (text.includes('gmail') || text.includes('email')) return 'email';
  if (text.includes('google_ads') || text.includes('google ads')) return 'paid-search';
  if (text.includes('search_console') || text.includes('seo')) return 'seo';
  if (text.includes('google_analytics') || text.includes('analytics') || text.includes('tracking')) return 'analytics';
  if (text.includes('clickup')) return 'project-management';
  if (text.includes('youtube')) return 'youtube';
  if (text.includes('tiktok')) return 'tiktok';
  if (text.includes('facebook') || text.includes('instagram') || text.includes('meta')) return 'social';
  if (text.includes('google_calendar') || text.includes('calendar') || text.includes('booking') || mod.vertical === 'scheduling') return 'scheduling';
  if (id.startsWith('media.image') || text.includes('image generation')) return 'media-image';
  if (id.startsWith('media.video') || text.includes('video generation')) return 'media-video';
  if (id.startsWith('creative.')) return 'creative-factory';
  if (text.includes('drive') || mod.vertical === 'media' || id.startsWith('media.')) return 'media';
  return mod.vertical || 'specialist';
}

function varLabel(varName: string): { label: string; sensitive: boolean; hint: string } {
  const n = varName.toUpperCase();
  if (n.endsWith('_API_TOKEN') || n.endsWith('_TOKEN'))
    return { label: 'API Token', sensitive: true, hint: n.includes('CLICKUP') ? 'Get from ClickUp → Settings → Apps → API Token' : '' };
  if (n.endsWith('_SECRET') || n.endsWith('_CLIENT_SECRET'))
    return { label: varName.replace(/_/g, ' ').replace(/^\w+ /, ''), sensitive: true, hint: '' };
  if (n.includes('TEAM_ID') || n.includes('WORKSPACE_ID'))
    return { label: 'Workspace ID', sensitive: false, hint: 'Found in the platform URL, e.g. app.clickup.com/{ID}/...' };
  if (n.includes('LIST_ID'))
    return { label: 'Default List ID', sensitive: false, hint: 'Navigate to the list — the ID is in the URL' };
  if (n.includes('SITE_URL'))
    return { label: 'Site URL', sensitive: false, hint: 'e.g. sc-domain:example.com or https://www.example.com/' };
  if (n.includes('CUSTOMER_ID'))
    return { label: 'Customer ID', sensitive: false, hint: 'Google Ads account ID without dashes' };
  if (n.includes('DEVELOPER_TOKEN'))
    return { label: 'Developer Token', sensitive: true, hint: '' };
  if (n.includes('CLIENT_ID'))
    return { label: 'Client ID', sensitive: false, hint: '' };
  if (n.includes('REFRESH_TOKEN'))
    return { label: 'Refresh Token', sensitive: true, hint: '' };
  if (n === 'IMAGE_GEN_WORKER_URL')
    return { label: 'Worker URL', sensitive: false, hint: 'The full HTTPS URL of your image generation worker endpoint' };
  if (n === 'IMAGE_GEN_API_KEY')
    return { label: 'Image Gen API Key', sensitive: true, hint: 'Bearer token used to authenticate requests to the worker' };
  if (n === 'VIDEO_GEN_PROVIDER')
    return { label: 'Video Provider', sensitive: false, hint: 'Provider label, e.g. runway, kling, custom_http, or local_ffmpeg' };
  if (n === 'VIDEO_GEN_API_URL')
    return { label: 'Video API URL', sensitive: false, hint: 'HTTPS endpoint for your video provider; use local for FFmpeg fallback' };
  if (n === 'VIDEO_GEN_API_KEY')
    return { label: 'Video API Key', sensitive: true, hint: 'Bearer token for the configured video provider' };
  if (n.endsWith('_API_KEY'))
    return { label: 'API Key', sensitive: true, hint: '' };
  if (n.endsWith('_URL') || n.endsWith('_ENDPOINT'))
    return { label: varName.replace(/^[A-Z_]+?_/, '').replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase()), sensitive: false, hint: '' };
  return { label: varName.replace(/^[A-Z_]+?_/, '').replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase()), sensitive: false, hint: '' };
}

function modelValue(provider: string, modelId: string): string {
  return `${provider}::${modelId}`;
}

function parseModelValue(value: string): { provider: string; model_id: string } | null {
  const [provider, ...rest] = value.split('::');
  const model_id = rest.join('::');
  return provider && model_id ? { provider, model_id } : null;
}

function providerLabel(provider: string): string {
  if (provider === 'openai') return 'OpenAI Chat';
  return provider;
}

function providerConnected(provider: ProviderInfo): boolean {
  return Boolean(provider.connected || provider.has_byok_key || provider.has_platform_key || provider.auth_mode === 'oauth');
}

function moduleBase(modules: ModuleInfo[]) {
  return {
    moduleCount: modules.length,
    moduleIds: modules.map(m => m.id),
    capabilityKeys: [...new Set(modules.map(m => m.capability))].sort(),
    llmModuleIds: modules.filter(m => m.uses_llm !== false).map(m => m.id),
  };
}


function pluginDisplayName(plugin: PluginInfo): string {
  const id = plugin.plugin_id.toLowerCase();
  if (id.includes('clickup')) return 'ClickUp';
  if (id.includes('google_ads') || id.includes('google-ads')) return 'Google Ads';
  if (id.includes('search_console') || id.includes('search-console')) return 'Google Search Console';
  if (id.includes('gmail')) return 'Gmail';
  if (id.includes('google_analytics') || id.includes('google-analytics')) return 'Google Analytics';
  if (id.includes('media.image')) return 'Image Generation';
  if (id.includes('media.video')) return 'Video Generation';
  if (id.includes('creative.factory')) return 'Creative Factory';
  if (id.includes('meta')) return 'Meta Channel';
  if (id.includes('tiktok')) return 'TikTok Specialist';
  return plugin.name;
}

function pluginDescription(plugin: PluginInfo): string {
  const id = plugin.plugin_id.toLowerCase();
  if (id.includes('clickup')) return 'Read campaign task status and create tasks from approved plans.';
  if (id.includes('google_ads') || id.includes('google-ads')) return 'Pull paid search performance and draft ad copy.';
  if (id.includes('search_console') || id.includes('search-console')) return 'Read organic search performance and SEO signals.';
  if (id.includes('gmail')) return 'Send outreach and read reply intelligence.';
  if (id.includes('google_analytics') || id.includes('google-analytics')) return 'Read website analytics and conversion signals.';
  if (id.includes('media.image')) return 'media.generate specialist.';
  if (id.includes('media.video')) return 'media.generate specialist.';
  if (id.includes('creative.factory')) return 'Creative production orchestration specialist.';
  return `${plugin.implements.join(', ')} specialist.`;
}

function pluginConnector(plugins: PluginInfo[], pluginId: string, label?: string): ConnectorSummary | null {
  const plugin = plugins.find(p => p.plugin_id === pluginId);
  if (!plugin) return null;
  const configured = plugin.credentials_configured;
  const sourceText = configured ? (plugin.credential_source === 'env_var' ? 'Via .env' : 'Connected') : 'Not configured';
  return {
    id: plugin.plugin_id,
    label: label || pluginDisplayName(plugin),
    detail: configured
      ? `${sourceText}${plugin.requires_platform_vars.length ? ` · ${plugin.requires_platform_vars.length} credential${plugin.requires_platform_vars.length !== 1 ? 's' : ''}` : ''}`
      : plugin.missing_vars.length ? `Missing ${plugin.missing_vars.join(', ')}` : 'Needs credential setup',
    description: pluginDescription(plugin),
    implements: plugin.implements,
    missingVars: plugin.missing_vars,
    status: configured ? 'connected' : 'needs_setup',
    statusText: sourceText,
    actionLabel: plugin.credential_source === 'env_var' ? undefined : (configured ? 'Update' : 'Configure'),
    actionType: plugin.credential_source === 'env_var' ? undefined : 'plugin',
    pluginId: plugin.plugin_id,
    removable: configured && plugin.credential_source === 'database',
  };
}

function oauthConnector(connections: SocialConnection[], platform: string, label?: string): ConnectorSummary {
  const live = connections.filter(conn => conn.platform === platform && conn.status !== 'revoked');
  const meta = OAUTH_PLATFORMS[platform] || { label: label || titleCase(platform), icon: '⚙️' };
  return {
    id: `oauth.${platform}`,
    label: `${meta.icon} ${label || meta.label}`,
    detail: live.length
      ? `${live.length} account${live.length !== 1 ? 's' : ''} connected${live[0]?.page_name ? ` · ${live[0].page_name}` : ''}`
      : `Connect from Brands / Clients`,
    status: live.length ? 'connected' : 'needs_setup',
    statusText: live.length ? 'Connected' : 'Not connected',
    actionLabel: live.length ? 'Manage' : 'Connect',
    actionType: 'brands',
  };
}

function compactConnectors(connectors: Array<ConnectorSummary | null>): ConnectorSummary[] {
  const seen = new Set<string>();
  return connectors.filter((connector): connector is ConnectorSummary => {
    if (!connector || seen.has(connector.id)) return false;
    seen.add(connector.id);
    return true;
  });
}

function readinessFromConnectors(connectors: ConnectorSummary[], fallback: 'ready' | 'needs_setup' | 'installed' = 'installed') {
  if (!connectors.length) return fallback;
  return connectors.every(c => c.status !== 'needs_setup') ? 'ready' : 'needs_setup';
}

function summarizeGroup(key: string, modules: ModuleInfo[], connections: SocialConnection[], plugins: PluginInfo[]): SpecialistSummary {
  const jobs = [...new Set(modules.flatMap(implementedJobs))];
  const moduleText = modules.map(m => `${m.id} ${m.platform_hint}`).join(' ').toLowerCase();
  const base = moduleBase(modules);

  if (key === 'email') {
    const connectors = compactConnectors([
      oauthConnector(connections, 'gmail', 'Gmail account'),
      pluginConnector(plugins, 'channel.gmail'),
    ]);
    const readiness = connectors.some(connector => connector.status === 'connected') ? 'ready' : 'needs_setup';
    const accountCount = connections.filter(conn => conn.platform === 'gmail' && conn.status !== 'revoked').length;
    return {
      key,
      name: 'Email Specialist',
      description: 'Plans email campaigns, drafts outreach, reads reply context, and prepares approved Gmail send actions.',
      jobs: ['marketing.plan', 'marketing.execute', 'marketing.optimize'],
      specialties: ['campaign planning', 'drafting', 'inbox intelligence', 'optimization'],
      readiness,
      readinessText: readiness === 'ready'
        ? `${accountCount || 1} email connector${(accountCount || 1) !== 1 ? 's' : ''} ready`
        : 'Connect Gmail or configure draft credentials to unlock email actions',
      risk: moduleText.includes('send') ? 'Draft by default; real sends require explicit owner approval' : 'Draft / review',
      ...base,
      connectors,
      nextStep: readiness === 'ready' ? 'Use the CMO to plan, draft, approve, then send.' : 'Connect Gmail, verify sender identity, then create a test draft.',
    };
  }

  if (key === 'paid-search') {
    const connectors = compactConnectors([pluginConnector(plugins, 'channel.google_ads')]);
    const readiness = readinessFromConnectors(connectors, 'needs_setup');
    return {
      key,
      name: 'Paid Search Specialist',
      description: 'Reviews paid-search performance and prepares optimization or ad-draft artifacts.',
      jobs,
      specialties: ['paid search', 'budget efficiency', 'ad drafts'],
      readiness,
      readinessText: readiness === 'ready' ? 'Google Ads connected' : 'Configure Google Ads API credentials',
      risk: 'Read and draft first; spend changes require approval',
      ...base,
      connectors,
    };
  }

  if (key === 'seo') {
    const hasSearchConsole = moduleText.includes('search_console');
    const connectors = compactConnectors([hasSearchConsole ? pluginConnector(plugins, 'channel.search_console') : null]);
    const readiness = hasSearchConsole ? readinessFromConnectors(connectors, 'needs_setup') : 'installed';
    return {
      key,
      name: hasSearchConsole ? 'Google Search Console Specialist' : 'SEO Specialist',
      description: hasSearchConsole
        ? 'Reads Google Search Console properties, query/page performance, URL inspection, sitemap signals, and SEO opportunities.'
        : 'Audits search visibility, content opportunities, and organic growth constraints.',
      jobs: jobs.length ? jobs : ['marketing.optimize'],
      specialties: hasSearchConsole
        ? ['organic search', 'query/page performance', 'URL inspection', 'sitemaps', 'SEO opportunities']
        : ['SEO', 'content opportunities', 'technical review'],
      readiness,
      readinessText: hasSearchConsole
        ? (readiness === 'ready' ? 'Search Console connected' : 'Add Google Search Console credentials to enable live organic search reads')
        : 'Installed',
      risk: hasSearchConsole ? 'Read-only; no website edits, sitemap changes, or indexing requests' : 'Diagnostic / recommendation',
      ...base,
      connectors,
      nextStep: hasSearchConsole
        ? (readiness === 'ready' ? 'Ask the CMO to check Search Console performance or find SEO opportunities.' : 'Configure Search Console credentials, then run the property inventory check.')
        : undefined,
      pluginId: hasSearchConsole ? 'channel.search_console' : undefined,
    };
  }

  if (key === 'analytics') {
    const connectors = compactConnectors([pluginConnector(plugins, 'channel.google_analytics')]);
    const readiness = readinessFromConnectors(connectors, 'installed');
    return {
      key,
      name: 'Analytics Specialist',
      description: 'Diagnoses measurement, tracking, and performance signals for optimization work.',
      jobs,
      specialties: ['tracking', 'measurement', 'performance signals'],
      readiness,
      readinessText: readiness === 'ready' ? 'Analytics connected' : connectors.length ? 'Configure analytics credentials' : 'Installed',
      risk: 'Read-only / diagnostic',
      ...base,
      connectors,
    };
  }

  if (key === 'project-management') {
    const connectors = compactConnectors([pluginConnector(plugins, 'channel.clickup')]);
    const readiness = readinessFromConnectors(connectors, 'needs_setup');
    return {
      key,
      name: 'Project Management',
      description: 'Reads campaign task status from ClickUp and creates tasks from approved plans.',
      jobs: ['marketing.execute', 'marketing.optimize'],
      specialties: ['task tracking', 'campaign execution', 'status intelligence'],
      readiness,
      readinessText: readiness === 'ready' ? 'ClickUp connected' : 'Add ClickUp credentials to enable task read/create',
      risk: 'Read by default; task creation requires explicit approval',
      ...base,
      connectors,
      nextStep: readiness === 'ready' ? 'Ask the CMO to check ClickUp or create tasks.' : undefined,
      pluginId: 'channel.clickup',
    };
  }

  if (key === 'creative-factory') {
    const connectors = compactConnectors([
      oauthConnector(connections, 'google_drive', 'Google Drive assets'),
    ]);
    const readiness = readinessFromConnectors(connectors, 'installed');
    return {
      key,
      name: 'Creative Factory',
      description: 'Plans creative production, routes work to media specialists, and assembles reusable creative bundles.',
      jobs: jobs.length ? jobs : ['marketing.plan', 'marketing.execute'],
      specialties: ['creative orchestration', 'production briefs', 'asset assembly'],
      readiness,
      readinessText: readiness === 'ready' ? 'Asset library connected' : 'Connect Google Drive for durable creative assets',
      risk: 'Orchestrates only - generation and publishing stay in specialist plugins',
      ...base,
      connectors,
      nextStep: readiness === 'ready' ? 'Ask the CMO to create a creative pack or bundle.' : undefined,
      pluginId: 'creative.factory',
    };
  }

  if (key === 'media-image') {
    const imageConnector = pluginConnector(plugins, 'media.image');
    const connectors = compactConnectors([
      imageConnector,
      oauthConnector(connections, 'google_drive', 'Google Drive assets'),
    ]);
    const readiness = imageConnector?.status === 'connected' ? 'ready' : 'needs_setup';
    return {
      key,
      name: 'Creative / Image Specialist',
      description: 'Generates and manages channel-agnostic image creatives, ad assets, social images, hero images, and banners.',
      jobs: jobs.length ? jobs : ['media.generate'],
      specialties: ['image generation', 'visual creative', 'asset library'],
      readiness,
      readinessText: readiness === 'ready' ? 'Image generation connected' : 'Configure image generation provider credentials',
      risk: 'Generate only — distribution stays in channel plugins',
      ...base,
      connectors,
      nextStep: readiness === 'ready' ? 'Ask the CMO to generate an image or ad creative.' : undefined,
      pluginId: 'media.image',
    };
  }

  if (key === 'media-video') {
    const videoConnector = pluginConnector(plugins, 'media.video');
    const connectors = compactConnectors([
      videoConnector,
      oauthConnector(connections, 'google_drive', 'Google Drive assets'),
    ]);
    const hasExternalProvider = videoConnector?.status === 'connected';
    const readiness = 'ready';
    return {
      key,
      name: 'Video Generation',
      description: 'Generates channel-agnostic video assets and short-form motion creative with a configurable provider.',
      jobs: jobs.length ? jobs : ['media.generate'],
      specialties: ['video generation', 'shortform video', 'motion creative'],
      readiness,
      readinessText: hasExternalProvider ? 'Video provider connected' : 'Local FFmpeg video rendering is ready; configure provider credentials only for an external video API',
      risk: 'Generate only - distribution stays in channel plugins',
      ...base,
      connectors,
      nextStep: 'Ask the CMO to generate a video or short.',
      pluginId: 'media.video',
    };
  }

  if (key === 'media') {
    const connectors = compactConnectors([
      oauthConnector(connections, 'google_drive', 'Google Drive assets'),
    ]);
    const readiness = readinessFromConnectors(connectors, 'installed');
    return {
      key,
      name: 'Media Assets',
      description: 'Stores and retrieves reusable creative assets for specialist and channel workflows.',
      jobs: jobs.length ? jobs : ['media.generate'],
      specialties: ['asset library', 'media handoff'],
      readiness,
      readinessText: readiness === 'ready' ? 'Asset library connected' : 'Connect Google Drive for durable creative assets',
      risk: 'Storage and handoff only',
      ...base,
      connectors,
    };
  }

  if (key === 'social') {
    const connectors = compactConnectors([
      pluginConnector(plugins, 'channel.meta'),
      oauthConnector(connections, 'facebook', 'Facebook page'),
      oauthConnector(connections, 'google_drive', 'Google Drive assets'),
    ]);
    const readiness = readinessFromConnectors(connectors, 'needs_setup');
    return {
      key,
      name: 'Social Specialist',
      description: 'Drafts, reviews, reads, and publishes approved social content through installed channel plugins.',
      jobs,
      specialties: ['facebook pages', 'instagram', 'social publishing', 'post intelligence'],
      readiness,
      readinessText: readiness === 'ready' ? 'Social connectors ready' : 'Connect Meta credentials and brand accounts',
      risk: 'Draft/read first; publishing requires explicit approval',
      ...base,
      connectors,
      pluginId: 'channel.meta',
    };
  }

  if (key === 'youtube') {
    const connectors = compactConnectors([oauthConnector(connections, 'youtube', 'YouTube channel')]);
    const readiness = readinessFromConnectors(connectors, 'needs_setup');
    return {
      key,
      name: 'YouTube Specialist',
      description: 'Validates YouTube connections and prepares approved video publishing actions.',
      jobs,
      specialties: ['youtube', 'shorts', 'video publishing', 'video performance'],
      readiness,
      readinessText: readiness === 'ready' ? 'YouTube connected' : 'Connect YouTube from Brands / Clients',
      risk: 'Connection checks are read-only; publishing requires explicit approval',
      ...base,
      connectors,
    };
  }

  if (key === 'tiktok') {
    const connectors = compactConnectors([
      pluginConnector(plugins, 'channel.tiktok'),
      oauthConnector(connections, 'tiktok', 'TikTok account'),
    ]);
    const readiness = readinessFromConnectors(connectors, 'needs_setup');
    return {
      key,
      name: 'TikTok Specialist',
      description: 'Validates TikTok connections and prepares manual export or approved posting workflows.',
      jobs,
      specialties: ['tiktok', 'shortform video', 'manual export'],
      readiness,
      readinessText: readiness === 'ready' ? 'TikTok connected' : 'Configure TikTok app credentials and account access',
      risk: 'Posting requires a video asset and explicit approval',
      ...base,
      connectors,
      pluginId: 'channel.tiktok',
    };
  }

  if (key === 'scheduling') {
    const connectors = compactConnectors([oauthConnector(connections, 'google_calendar', 'Google Calendar')]);
    const readiness = readinessFromConnectors(connectors, 'needs_setup');
    return {
      key,
      name: 'Scheduling Specialist',
      description: 'Reads availability and prepares approved booking/calendar actions.',
      jobs: jobs.length ? jobs : ['scheduling.booking'],
      specialties: ['calendar booking', 'availability', 'meeting scheduling'],
      readiness,
      readinessText: readiness === 'ready' ? 'Calendar connected' : 'Connect Google Calendar from Brands / Clients',
      risk: 'Booking actions require explicit approval',
      ...base,
      connectors,
    };
  }

  return {
    key,
    name: `${titleCase(key)} Specialist`,
    description: 'Installed specialist implementation available to the CMO when its skill contract applies.',
    jobs,
    specialties: [...new Set(modules.map(m => m.platform_hint).filter(Boolean))],
    readiness: 'installed',
    readinessText: 'Installed',
    risk: 'Draft / review',
    ...base,
    connectors: [],
  };
}

function connectorBadgeClass(status: ConnectorSummary['status']): string {
  if (status === 'connected') return 'success';
  if (status === 'needs_setup') return 'warning';
  return 'muted';
}

export function AdminModules() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [connections, setConnections] = useState<SocialConnection[]>([]);
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [capabilities, setCapabilities] = useState<CapabilityInfo[]>([]);
  const [backendOverrides, setBackendOverrides] = useState<BackendOverride[]>([]);
  const [loading, setLoading] = useState(true);
  const [configuringPlugin, setConfiguringPlugin] = useState<PluginInfo | null>(null);
  const [configuringAI, setConfiguringAI] = useState<SpecialistSummary | null>(null);
  const [credFields, setCredFields] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [savedPlugin, setSavedPlugin] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [cuStep, setCuStep] = useState<ClickUpStep>('token');
  const [cuToken, setCuToken] = useState('');
  const [cuWorkspaces, setCuWorkspaces] = useState<ClickUpWorkspace[]>([]);
  const [cuSelected, setCuSelected] = useState('');
  const [cuResolving, setCuResolving] = useState(false);
  const [cuError, setCuError] = useState('');

  function showToast(message: string) {
    setToast(message);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 4000);
  }

  const refreshPlugins = async () => {
    const { plugins: p } = await api.listPlugins().catch(() => ({ plugins: [] as PluginInfo[] }));
    setPlugins(p);
  };

  const refreshConnections = async () => {
    const socialConnections = await api.listSocialConnections().catch(() => [] as SocialConnection[]);
    setConnections(socialConnections as SocialConnection[]);
  };

  const refreshBackendOverrides = async () => {
    const { overrides } = await api.getBackendOverrides().catch(() => ({ overrides: [] as BackendOverride[] }));
    setBackendOverrides(overrides);
  };

  useEffect(() => {
    const statuses = ['facebook', 'gmail', 'google_calendar', 'google_drive', 'youtube', 'tiktok'] as const;
    const reason = searchParams.get('reason') || '';
    const messages = statuses.flatMap(platform => {
      const status = searchParams.get(platform);
      if (!status) return [];
      const label = OAUTH_PLATFORMS[platform]?.label || titleCase(platform);
      if (status === 'connected') return [`✅ ${label} connected`];
      if (status === 'denied') return [`${label} connection cancelled`];
      return [`⚠️ ${label} failed — ${reason.replace(/_/g, ' ') || status}`];
    });
    if (!messages.length) return;
    window.setTimeout(() => {
      setSearchParams({});
      showToast(messages.join(' · '));
      void refreshConnections();
    }, 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    async function load() {
      const [{ verticals }, socialConnections, providerResult, capabilityResult, overrideResult] = await Promise.all([
        api.getVerticals(),
        api.listSocialConnections().catch(() => [] as SocialConnection[]),
        api.getProviders().catch(() => ({ providers: [] as ProviderInfo[] })),
        api.getCapabilities().catch(() => ({ capabilities: [] as CapabilityInfo[] })),
        api.getBackendOverrides().catch(() => ({ overrides: [] as BackendOverride[] })),
      ]);
      const results = await Promise.all(
        verticals.map(v => api.getModules(v.vertical).then(r => r.modules).catch(() => [] as ModuleInfo[]))
      );
      setModules(results.flat());
      setConnections(socialConnections as SocialConnection[]);
      setProviders(providerResult.providers ?? []);
      setCapabilities(capabilityResult.capabilities ?? []);
      setBackendOverrides(overrideResult.overrides ?? []);
      await refreshPlugins();
    }
    load().catch(() => {}).finally(() => setLoading(false));
  }, []);

  const specialists = useMemo(() => {
    const visible = modules.filter(mod => !mod.id.toLowerCase().includes('test_stub') && !mod.internal);
    const grouped = new Map<string, ModuleInfo[]>();
    visible.forEach(mod => {
      const key = groupKey(mod);
      grouped.set(key, [...(grouped.get(key) ?? []), mod]);
    });
    return [...grouped.entries()]
      .map(([key, mods]) => summarizeGroup(key, mods, connections, plugins))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [modules, connections, plugins]);

  const providerReady = useMemo(() => new Set(providers.filter(providerConnected).map(p => p.provider)), [providers]);
  const overrideMap = useMemo(() => new Map(backendOverrides.map(override => [override.target, override])), [backendOverrides]);

  const modelChoices = useMemo(() => {
    const seen = new Set<string>();
    const choices: ModelChoice[] = [];
    capabilities.forEach(capability => {
      if (capability.modality !== 'text') return;
      capability.model_options.forEach(option => {
        if (option.status !== 'healthy' || !providerReady.has(option.provider)) return;
        const value = modelValue(option.provider, option.model_id);
        if (seen.has(value)) return;
        seen.add(value);
        choices.push({
          value,
          provider: option.provider,
          model_id: option.model_id,
          label: `${providerLabel(option.provider)} · ${option.model_id}`,
          capability: capability.key,
        });
      });
    });
    return choices.sort((a, b) => a.provider.localeCompare(b.provider) || a.model_id.localeCompare(b.model_id));
  }, [capabilities, providerReady]);

  function choicesForSpecialist(s: SpecialistSummary): ModelChoice[] {
    const allowed = new Set(s.capabilityKeys);
    const scoped = modelChoices.filter(choice => choice.capability && allowed.has(choice.capability));
    return scoped.length ? scoped : modelChoices;
  }

  function overrideValue(target: string): string {
    const override = overrideMap.get(target);
    return override?.provider && override.model_id ? modelValue(override.provider, override.model_id) : '';
  }

  function currentAIValue(s: SpecialistSummary): string {
    const values = s.llmModuleIds.map(target => overrideValue(target));
    const selected = [...new Set(values.filter(Boolean))];
    if (selected.length === 0) return '';
    if (selected.length === 1 && values.every(Boolean)) return selected[0];
    return '__mixed__';
  }

  function currentAILabel(s: SpecialistSummary): string {
    const value = currentAIValue(s);
    if (!value) return 'Auto-route best available';
    if (value === '__mixed__') return 'Mixed model settings';
    return value.replace('::', ' · ');
  }

  async function handleClickUpResolve() {
    if (!cuToken.trim()) return;
    setCuResolving(true);
    setCuError('');
    try {
      const { workspaces } = await api.resolvePluginWorkspaces('channel.clickup', cuToken.trim());
      if (!workspaces.length) {
        setCuError('No workspaces found for this token.');
        return;
      }
      setCuWorkspaces(workspaces);
      setCuSelected(workspaces[0].id);
      setCuStep('workspace');
    } catch (e: unknown) {
      setCuError(e instanceof Error ? e.message : 'Could not reach ClickUp — check your token.');
    } finally {
      setCuResolving(false);
    }
  }

  async function handleSaveCredentials() {
    if (!configuringPlugin) return;
    setSaving(true);
    setSaveError('');
    try {
      const vars = configuringPlugin.plugin_id === 'channel.clickup'
        ? { CLICKUP_API_TOKEN: cuToken.trim(), CLICKUP_TEAM_ID: cuSelected }
        : credFields;
      await api.savePluginCredentials(configuringPlugin.plugin_id, vars);
      setSavedPlugin(configuringPlugin.plugin_id);
      await refreshPlugins();
      setConfiguringPlugin(null);
      setCredFields({});
      showToast('✅ Connector credentials saved');
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : 'Failed to save credentials');
    } finally {
      setSaving(false);
    }
  }

  async function handleRemoveCredentials(pluginId: string) {
    await api.deletePluginCredentials(pluginId).catch(() => undefined);
    setSavedPlugin(null);
    await refreshPlugins();
  }

  function openConfigure(pluginId: string) {
    const plugin = plugins.find(p => p.plugin_id === pluginId);
    if (!plugin) return;
    const initial: Record<string, string> = {};
    plugin.requires_platform_vars.forEach(v => { initial[v] = ''; });
    setCredFields(initial);
    setSaveError('');
    setSavedPlugin(null);
    if (plugin.plugin_id === 'channel.clickup') {
      setCuStep('token');
      setCuToken('');
      setCuWorkspaces([]);
      setCuSelected('');
      setCuError('');
    }
    setConfiguringPlugin(plugin);
  }

  function openConfigureAI(s: SpecialistSummary) {
    setSelectedModel(currentAIValue(s));
    setSaveError('');
    setConfiguringAI(s);
  }

  async function handleSaveAIModel() {
    if (!configuringAI || selectedModel === '__mixed__') return;
    setSaving(true);
    setSaveError('');
    try {
      if (!selectedModel) {
        await Promise.all(configuringAI.llmModuleIds.map(target => api.deleteBackendOverride(target)));
      } else {
        const parsed = parseModelValue(selectedModel);
        if (!parsed) return;
        await Promise.all(configuringAI.llmModuleIds.map(target => api.putBackendOverride(target, {
          provider: parsed.provider,
          model_id: parsed.model_id,
          tool_id: null,
          modality: 'text',
          strict: true,
        })));
      }
      await refreshBackendOverrides();
      setConfiguringAI(null);
      setSelectedModel('');
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : 'Failed to save AI model');
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="admin-page"><div className="loading-full"><span className="spinner" /></div></div>;
  }

  return (
    <div className="admin-page">
      {toast && (
        <div style={{ position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)', background: 'var(--fg)', color: 'var(--bg)', padding: '10px 20px', borderRadius: 8, fontSize: 13, fontWeight: 600, zIndex: 9999, boxShadow: '0 4px 20px rgba(0,0,0,.2)' }}>
          {toast}
        </div>
      )}

      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">Specialists</div>
          <div className="admin-page-subtitle">
            One setup surface for what each specialist can do, which accounts or credentials it needs, and which AI/model it uses.
          </div>
        </div>
      </div>

      {configuringPlugin && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <div className="admin-card" style={{ width: '100%', maxWidth: 500, margin: 0 }}>
            <div style={{ fontWeight: 850, fontSize: 17, marginBottom: 4 }}>Configure {configuringPlugin.name}</div>
            <div style={{ color: 'var(--text2)', fontSize: 13, marginBottom: 20 }}>Credentials are encrypted and stored in BOS. They are never returned via API.</div>

            {configuringPlugin.plugin_id === 'channel.clickup' ? (
              <div style={{ display: 'grid', gap: 16 }}>
                {cuStep === 'token' && (
                  <div>
                    <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>API Token</label>
                    <div style={{ color: 'var(--text2)', fontSize: 11, marginBottom: 6 }}>Get from ClickUp → Settings → Apps → API Token</div>
                    <input
                      type="password"
                      className="input"
                      placeholder="pk_..."
                      value={cuToken}
                      onChange={e => { setCuToken(e.target.value); setCuError(''); }}
                      style={{ width: '100%', fontFamily: 'monospace' }}
                      autoComplete="off"
                    />
                    {cuError && <div style={{ color: 'var(--error)', fontSize: 12, marginTop: 6 }}>{cuError}</div>}
                  </div>
                )}
                {cuStep === 'workspace' && (
                  <div>
                    <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Select Workspace</label>
                    <div style={{ color: 'var(--text2)', fontSize: 11, marginBottom: 6 }}>Choose the ClickUp workspace to connect.</div>
                    <select
                      className="input"
                      value={cuSelected}
                      onChange={e => setCuSelected(e.target.value)}
                      style={{ width: '100%' }}
                    >
                      {cuWorkspaces.map(w => (
                        <option key={w.id} value={w.id}>{w.name} ({w.id})</option>
                      ))}
                    </select>
                    <button className="btn btn-ghost" style={{ marginTop: 8, fontSize: 12 }} onClick={() => { setCuStep('token'); setCuWorkspaces([]); }}>
                      ← Use a different token
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ display: 'grid', gap: 14 }}>
                {configuringPlugin.requires_platform_vars.map(varName => {
                  const { label, sensitive, hint } = varLabel(varName);
                  return (
                    <div key={varName}>
                      <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{label}</label>
                      {hint && <div style={{ color: 'var(--text2)', fontSize: 11, marginBottom: 5 }}>{hint}</div>}
                      <input
                        type={sensitive ? 'password' : 'text'}
                        className="input"
                        placeholder={varName}
                        value={credFields[varName] ?? ''}
                        onChange={e => setCredFields(f => ({ ...f, [varName]: e.target.value }))}
                        style={{ width: '100%', fontFamily: sensitive ? 'monospace' : undefined }}
                        autoComplete="off"
                      />
                    </div>
                  );
                })}
              </div>
            )}

            {saveError && <div style={{ color: 'var(--error)', fontSize: 13, marginTop: 12 }}>{saveError}</div>}
            <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => { setConfiguringPlugin(null); setSaveError(''); }}>Cancel</button>
              {configuringPlugin.plugin_id === 'channel.clickup' && cuStep === 'token' ? (
                <button className="btn btn-primary" onClick={handleClickUpResolve} disabled={cuResolving || !cuToken.trim()}>
                  {cuResolving ? 'Fetching…' : 'Fetch Workspaces'}
                </button>
              ) : (
                <button className="btn btn-primary" onClick={handleSaveCredentials} disabled={saving || (configuringPlugin.plugin_id === 'channel.clickup' && !cuSelected)}>
                  {saving ? 'Saving…' : 'Save credentials'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {configuringAI && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <div className="admin-card" style={{ width: '100%', maxWidth: 520, margin: 0 }}>
            <div style={{ fontWeight: 850, fontSize: 17, marginBottom: 4 }}>Configure AI for {configuringAI.name}</div>
            <div style={{ color: 'var(--text2)', fontSize: 13, marginBottom: 18 }}>
              Choose the exact LLM/model this specialist should use. Leave on auto-route to let BOS choose the best available model.
            </div>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Model</label>
            <select className="select" value={selectedModel} onChange={e => setSelectedModel(e.target.value)}>
              <option value="">Auto-route best available</option>
              {selectedModel === '__mixed__' && <option value="__mixed__">Mixed model settings</option>}
              {choicesForSpecialist(configuringAI).map(choice => (
                <option key={choice.value} value={choice.value}>{choice.label}</option>
              ))}
            </select>
            <div style={{ color: 'var(--text2)', fontSize: 12, marginTop: 10 }}>
              Applies to {configuringAI.llmModuleIds.length} LLM tool{configuringAI.llmModuleIds.length !== 1 ? 's' : ''} in this specialist.
            </div>
            {saveError && <div style={{ color: 'var(--error)', fontSize: 13, marginTop: 12 }}>{saveError}</div>}
            <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => { setConfiguringAI(null); setSaveError(''); }}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSaveAIModel} disabled={saving || selectedModel === '__mixed__'}>
                {saving ? 'Saving…' : 'Save AI model'}
              </button>
            </div>
          </div>
        </div>
      )}

      {specialists.length === 0 ? (
        <div className="admin-card"><div className="empty-state"><div className="empty-state-icon">◎</div><div className="empty-state-title">No specialists installed</div><div className="empty-state-text">Install capability or plugin packages to see specialists here.</div></div></div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 14 }}>
          {specialists.map(s => (
            <div key={s.key} className="admin-card" style={{ margin: 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', marginBottom: 10 }}>
                <div>
                  <div style={{ fontWeight: 850, fontSize: 16 }}>{s.name}</div>
                  <div style={{ color: 'var(--text2)', fontSize: 12, marginTop: 3 }}>{s.description}</div>
                </div>
                <span className={`badge badge-${s.readiness === 'needs_setup' ? 'warning' : 'success'}`}>{s.readiness === 'needs_setup' ? 'Needs setup' : s.readiness === 'ready' ? 'Ready' : 'Available'}</span>
              </div>

              <div style={{ display: 'grid', gap: 10, marginTop: 14 }}>
                <div>
                  <div className="label" style={{ marginBottom: 5 }}>CMO jobs</div>
                  <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                    {s.jobs.map(job => <span key={job} className="badge badge-info">{job}</span>)}
                  </div>
                </div>
                <div>
                  <div className="label" style={{ marginBottom: 5 }}>Specialty</div>
                  <div style={{ color: 'var(--text2)', fontSize: 13 }}>{s.specialties.join(' · ') || 'General marketing'}</div>
                </div>
                <div>
                  <div className="label" style={{ marginBottom: 5 }}>Risk policy</div>
                  <div style={{ color: 'var(--text2)', fontSize: 13 }}>{s.risk}</div>
                </div>

                <div style={{ paddingTop: 10, borderTop: '1px solid var(--border)', display: 'grid', gap: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
                    <span style={{ color: 'var(--text2)', fontSize: 12 }}>Access: {s.readinessText}</span>
                    <span className="badge badge-muted">{s.moduleCount} tool{s.moduleCount !== 1 ? 's' : ''}</span>
                  </div>
                  {s.llmModuleIds.length > 0 && (
                    <div style={{ color: 'var(--text2)', fontSize: 12 }}>AI model: {currentAILabel(s)}</div>
                  )}
                  {s.nextStep && <div style={{ color: 'var(--text2)', fontSize: 12 }}>{s.nextStep}</div>}

                  {s.connectors.length > 0 && (
                    <div style={{ display: 'grid', gap: 8, marginTop: 2 }}>
                      <div className="label">Connectors</div>
                      {s.connectors.map(connector => (
                        <div key={connector.id} style={{ border: '1px solid var(--border)', borderRadius: 12, padding: '9px 10px', display: 'grid', gap: 8 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start' }}>
                            <div style={{ minWidth: 0 }}>
                              <div style={{ fontSize: 13, fontWeight: 750 }}>{connector.label}</div>
                              <div style={{ color: 'var(--text2)', fontSize: 11, marginTop: 2, overflowWrap: 'anywhere' }}>{connector.detail}</div>
                              {connector.description && (
                                <div style={{ color: 'var(--text2)', fontSize: 12, marginTop: 6 }}>{connector.description}</div>
                              )}
                            </div>
                            <span className={`badge badge-${connectorBadgeClass(connector.status)}`} style={{ whiteSpace: 'nowrap' }}>{connector.statusText}</span>
                          </div>
                          {connector.missingVars && connector.missingVars.length > 0 && (
                            <div>
                              <div className="label" style={{ marginBottom: 5 }}>Missing</div>
                              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                                {connector.missingVars.map(v => (
                                  <span key={v} className="badge badge-muted" style={{ fontFamily: 'monospace', fontSize: 11 }}>{v}</span>
                                ))}
                              </div>
                            </div>
                          )}
                          {connector.implements && connector.implements.length > 0 && (
                            <div>
                              <div className="label" style={{ marginBottom: 5 }}>Implements</div>
                              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                                {connector.implements.map(job => <span key={job} className="badge badge-info">{job}</span>)}
                              </div>
                            </div>
                          )}
                          {(connector.actionLabel || connector.removable || savedPlugin === connector.pluginId) && (
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                              {connector.actionLabel && connector.actionType === 'brands' && (
                                <button className="btn btn-ghost" style={{ fontSize: 12, padding: '4px 10px' }} onClick={() => navigate('/admin/brands')}>
                                  {connector.actionLabel}
                                </button>
                              )}
                              {connector.actionLabel && connector.actionType === 'plugin' && connector.pluginId && (
                                <button className="btn btn-ghost" style={{ fontSize: 12, padding: '4px 10px' }} onClick={() => openConfigure(connector.pluginId!)}>
                                  {connector.actionLabel}
                                </button>
                              )}
                              {connector.removable && connector.pluginId && (
                                <button className="btn btn-ghost" style={{ fontSize: 12, padding: '4px 10px', color: 'var(--text2)' }} onClick={() => handleRemoveCredentials(connector.pluginId!)}>
                                  Remove
                                </button>
                              )}
                              {savedPlugin === connector.pluginId && <span style={{ color: 'var(--success)', fontSize: 12 }}>✓ Saved</span>}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {s.llmModuleIds.length > 0 && (
                      <button
                        className="btn btn-ghost"
                        style={{ fontSize: 12, padding: '4px 10px', alignSelf: 'flex-start' }}
                        onClick={() => openConfigureAI(s)}
                      >
                        {currentAIValue(s) ? 'Update AI model' : 'Configure AI'}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
