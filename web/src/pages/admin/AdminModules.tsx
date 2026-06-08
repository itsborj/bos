import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { ActivationState, BackendOverride, BrandResponse, MediaModelOption, MediaProviderOption, PluginInfo, ProviderInfo, ProviderModelLive, SocialConnectionResponse } from '../../api/types';

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
  mediaModuleId?: string;
  mediaModality?: 'image' | 'video';
  mediaProviderOptions?: MediaProviderOption[];
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

function varPlaceholder(varName: string): string {
  const n = varName.toUpperCase();
  if (n === 'IMAGE_GEN_PROVIDER') return 'openai  /  gemini  /  custom';
  if (n === 'VIDEO_GEN_PROVIDER') return 'gemini  /  seedance  /  local_ffmpeg  /  custom';
  if (n === 'IMAGE_GEN_WORKER_URL' || n === 'VIDEO_GEN_API_URL') return 'https://...';
  if (n.endsWith('_API_KEY') || n.endsWith('_TOKEN')) return '••••••••';
  return varName;
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
  if (n === 'IMAGE_GEN_PROVIDER')
    return { label: 'Image Provider', sensitive: false, hint: 'openai · gemini · custom  (openai and gemini use the API key from Admin → AI Providers)' };
  if (n === 'IMAGE_GEN_WORKER_URL')
    return { label: 'Worker URL', sensitive: false, hint: 'Required when provider is custom — full HTTPS URL of your image generation worker' };
  if (n === 'IMAGE_GEN_API_KEY')
    return { label: 'Worker API Key', sensitive: true, hint: 'Required when provider is custom — bearer token for the worker endpoint' };
  if (n === 'VIDEO_GEN_PROVIDER')
    return { label: 'Video Provider', sensitive: false, hint: 'gemini · seedance · local_ffmpeg · custom  (gemini uses your platform key; local_ffmpeg needs no credentials; Kling coming soon)' };
  if (n === 'VIDEO_GEN_API_URL')
    return { label: 'Provider API URL', sensitive: false, hint: 'Required for seedance or custom — HTTPS endpoint for your video provider' };
  if (n === 'VIDEO_GEN_API_KEY')
    return { label: 'Provider API Key', sensitive: true, hint: 'Required for seedance or custom — bearer token for the provider' };
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

const _PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  openrouter: 'OpenRouter',
  gemini: 'Google Gemini',
  nvidia: 'NVIDIA',
  bytedance: 'ByteDance ModelArk',
};

function providerLabel(provider: string): string {
  return _PROVIDER_LABELS[provider] ?? titleCase(provider);
}

function buildMediaProviderOptions(
  models: ProviderModelLive[],
  modality: 'image' | 'video',
): MediaProviderOption[] {
  const grouped: Record<string, MediaModelOption[]> = {};
  models
    .filter(m => m.modality === modality)
    .forEach(m => {
      (grouped[m.provider] ??= []).push({ value: m.model_id, label: m.name || m.model_id });
    });

  const dynamic: MediaProviderOption[] = Object.entries(grouped).map(([provider, models]) => ({
    provider,
    label: providerLabel(provider),
    models,
  }));

  // local_ffmpeg is always available for video; no key needed, no models to list
  const builtIn: MediaProviderOption[] = modality === 'video'
    ? [{ provider: 'local_ffmpeg', label: 'Local FFmpeg (built-in)', models: [] }]
    : [];

  return [...builtIn, ...dynamic];
}

function providerConnected(provider: ProviderInfo): boolean {
  return Boolean(provider.connected || provider.has_byok_key || provider.has_platform_key || provider.auth_mode === 'oauth');
}

function pluginOrgActivation(plugin: PluginInfo): ActivationState | undefined {
  return plugin.activation_by_brand?.find(a => a.brand_id === null);
}

function pluginActivation(plugin: PluginInfo, brandId?: string | null): ActivationState | undefined {
  const brandRow = brandId ? plugin.activation_by_brand?.find(a => a.brand_id === brandId) : undefined;
  return brandRow || pluginOrgActivation(plugin);
}

function isPluginActive(plugin: PluginInfo, brandId?: string | null): boolean {
  return pluginActivation(plugin, brandId)?.status === 'active';
}

function pluginConnectorFromPlugin(plugin: PluginInfo, label?: string): ConnectorSummary {
  const requiredCount = plugin.requires_platform_vars.length;
  const configured = requiredCount > 0 ? plugin.credentials_configured : true;
  const sourceText = requiredCount === 0
    ? 'No credentials required'
    : configured ? (plugin.credential_source === 'env_var' ? 'Via .env' : 'Connected') : 'Not configured';
  const canConfigure = requiredCount > 0 && !(plugin.credential_source === 'env_var' && !['media.image', 'media.video'].includes(plugin.plugin_id));
  return {
    id: plugin.plugin_id,
    label: label || plugin.name,
    detail: plugin.status === 'error'
      ? (plugin.reason || 'Plugin failed to load')
      : configured
        ? `${sourceText}${requiredCount ? ` · ${requiredCount} credential${requiredCount !== 1 ? 's' : ''}` : ''}`
        : plugin.missing_vars.length ? `Missing ${plugin.missing_vars.join(', ')}` : 'Needs credential setup',
    description: plugin.implements.length ? `${plugin.implements.join(', ')} specialist.` : '',
    implements: plugin.implements,
    missingVars: plugin.missing_vars,
    status: plugin.status === 'error' ? 'needs_setup' : configured ? (requiredCount ? 'connected' : 'available') : 'needs_setup',
    statusText: plugin.status === 'error' ? 'Error' : sourceText,
    actionLabel: canConfigure ? (configured && requiredCount ? 'Update' : 'Configure') : undefined,
    actionType: 'plugin',
    pluginId: plugin.plugin_id,
    removable: requiredCount > 0 && configured && plugin.credential_source === 'database',
  };
}

type PlatformMeta = Record<string, { label: string; icon: string }>;

function buildPlatformMeta(plugins: PluginInfo[]): PlatformMeta {
  const meta: PlatformMeta = {};
  plugins.forEach(plugin => {
    (plugin.connections || []).forEach(conn => {
      if (conn.platform && !meta[conn.platform]) {
        meta[conn.platform] = {
          label: conn.display_name || titleCase(conn.platform),
          icon: conn.icon || '⚙️',
        };
      }
    });
  });
  return meta;
}

function oauthConnector(
  connections: SocialConnection[],
  platform: string,
  platformMeta: PlatformMeta,
): ConnectorSummary {
  const live = connections.filter(conn => conn.platform === platform && conn.status !== 'revoked');
  const meta = platformMeta[platform] || { label: titleCase(platform), icon: '⚙️' };
  return {
    id: `oauth.${platform}`,
    label: `${meta.icon} ${meta.label}`,
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

function summarizeInstalledPlugin(plugin: PluginInfo, connections: SocialConnection[], platformMeta: PlatformMeta, brandId?: string | null): SpecialistSummary {
  const active = isPluginActive(plugin, brandId);
  const declaredPlatforms = [...new Set([...(plugin.requires_social_connection || []), ...((plugin.connections || []).map(c => c.platform))].filter(Boolean))];
  const connectors = compactConnectors([
    pluginConnectorFromPlugin(plugin),
    ...declaredPlatforms.map(platform => oauthConnector(connections, platform, platformMeta)),
  ]);
  const hasCredentialDebt = connectors.some(c => c.status === 'needs_setup');
  const readiness: SpecialistSummary['readiness'] = plugin.status === 'error' || (active && hasCredentialDebt)
    ? 'needs_setup'
    : active ? 'ready' : 'installed';
  const firstImageModule = plugin.capability_ids.find(id => id.includes('image'));
  const firstVideoModule = plugin.capability_ids.find(id => id.includes('video'));
  const mediaModuleId = plugin.plugin_id === 'media.image' ? (firstImageModule || 'media.image.generate')
    : plugin.plugin_id === 'media.video' ? (firstVideoModule || 'media.video.generate')
      : undefined;
  return {
    key: plugin.plugin_id,
    name: plugin.name,
    description: plugin.status === 'error'
      ? (plugin.reason || 'Plugin failed to load.')
      : plugin.implements.length ? `${plugin.implements.join(', ')} specialist.` : '',
    jobs: plugin.implements.length ? plugin.implements : plugin.capability_ids,
    specialties: plugin.capability_ids,
    readiness,
    readinessText: plugin.status === 'error'
      ? (plugin.reason || 'Plugin error')
      : active
        ? (hasCredentialDebt ? 'Active — configure credentials or run connection check' : 'Active for selected Brand')
        : 'Installed — activate for selected Brand',
    risk: 'Plugin-owned policy; external actions require approval when declared',
    moduleCount: plugin.capability_ids.length,
    moduleIds: plugin.capability_ids,
    capabilityKeys: plugin.capability_ids,
    llmModuleIds: plugin.capability_ids,
    mediaModuleId,
    mediaModality: plugin.plugin_id === 'media.image' ? 'image' : plugin.plugin_id === 'media.video' ? 'video' : undefined,
    mediaProviderOptions: plugin.media_provider_options || [],
    connectors,
    nextStep: active ? 'Use the CMO to run this specialist when its skill contract applies.' : 'Activate this plugin for the selected Brand.',
    pluginId: plugin.plugin_id,
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
  const [connections, setConnections] = useState<SocialConnection[]>([]);
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [brands, setBrands] = useState<BrandResponse[]>([]);
  const [selectedBrandId, setSelectedBrandId] = useState<string | null>(null);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [availableModels, setAvailableModels] = useState<ProviderModelLive[]>([]);
  const [backendOverrides, setBackendOverrides] = useState<BackendOverride[]>([]);
  const [loading, setLoading] = useState(true);
  const [configuringPlugin, setConfiguringPlugin] = useState<PluginInfo | null>(null);
  const [configuringAI, setConfiguringAI] = useState<SpecialistSummary | null>(null);
  const [selectedMediaProvider, setSelectedMediaProvider] = useState('');
  const [selectedMediaModel, setSelectedMediaModel] = useState('');
  const [credFields, setCredFields] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [strictOverride, setStrictOverride] = useState(false);
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

  const [activatingPlugin, setActivatingPlugin] = useState<string | null>(null);

  const refreshPlugins = async () => {
    const { plugins: p } = await api.listPlugins().catch(() => ({ plugins: [] as PluginInfo[] }));
    setPlugins(p);
  };

  async function handleToggleActivation(pluginId: string, currentlyActive: boolean) {
    setActivatingPlugin(pluginId);
    try {
      if (currentlyActive) {
        await api.deactivatePlugin(pluginId, selectedBrandId);
      } else {
        await api.activatePlugin(pluginId, selectedBrandId);
      }
      await refreshPlugins();
      showToast(currentlyActive ? `${pluginId} deactivated` : `${pluginId} activated`);
    } catch {
      showToast(`Failed to ${currentlyActive ? 'deactivate' : 'activate'} ${pluginId}`);
    } finally {
      setActivatingPlugin(null);
    }
  }

  const refreshConnections = async () => {
    const socialConnections = await api.listSocialConnections().catch(() => [] as SocialConnection[]);
    setConnections(socialConnections as SocialConnection[]);
  };

  const refreshBackendOverrides = async () => {
    const { overrides } = await api.getBackendOverrides().catch(() => ({ overrides: [] as BackendOverride[] }));
    setBackendOverrides(overrides);
  };

  const platformMeta = useMemo(() => buildPlatformMeta(plugins), [plugins]);

  useEffect(() => {
    const statuses = ['facebook', 'gmail', 'google_calendar', 'google_drive', 'youtube', 'tiktok'] as const;
    const reason = searchParams.get('reason') || '';
    const messages = statuses.flatMap(platform => {
      const status = searchParams.get(platform);
      if (!status) return [];
      const pmeta = platformMeta[platform] || { label: titleCase(platform) };
      const label = pmeta.label;
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
      const [brandResult, socialConnections, providerResult, modelResult, overrideResult] = await Promise.all([
        api.getBrands().catch(() => ({ brands: [] as BrandResponse[], total: 0 })),
        api.listSocialConnections().catch(() => [] as SocialConnection[]),
        api.getProviders().catch(() => ({ providers: [] as ProviderInfo[] })),
        api.getAvailableModels().catch(() => ({ models: [] as ProviderModelLive[] })),
        api.getBackendOverrides().catch(() => ({ overrides: [] as BackendOverride[] })),
      ]);
      setBrands(brandResult.brands ?? []);
      setSelectedBrandId(prev => prev ?? brandResult.brands?.[0]?.id ?? null);
      setConnections(socialConnections as SocialConnection[]);
      setProviders(providerResult.providers ?? []);
      setAvailableModels(modelResult.models ?? []);
      setBackendOverrides(overrideResult.overrides ?? []);
      await refreshPlugins();
    }
    load().catch(() => {}).finally(() => setLoading(false));
  }, []);

  const specialists = useMemo(() => {
    const brandConnections = selectedBrandId
      ? connections.filter(conn => conn.brand_id === selectedBrandId)
      : connections;
    return plugins
      .filter(plugin => !plugin.plugin_id.toLowerCase().includes('test_stub'))
      .map(plugin => {
        const s = summarizeInstalledPlugin(plugin, brandConnections, platformMeta, selectedBrandId);
        if (s.mediaModality) {
          return { ...s, mediaProviderOptions: s.mediaProviderOptions?.length ? s.mediaProviderOptions : buildMediaProviderOptions(availableModels, s.mediaModality) };
        }
        return s;
      })
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [connections, plugins, selectedBrandId, availableModels]);

  const providerReady = useMemo(() => new Set(providers.filter(providerConnected).map(p => p.provider)), [providers]);
  const overrideMap = useMemo(() => new Map(backendOverrides.map(override => [override.target, override])), [backendOverrides]);

  const modelChoices = useMemo(() => {
    const seen = new Set<string>();
    const choices: ModelChoice[] = [];
    availableModels.forEach(m => {
      const value = modelValue(m.provider, m.model_id);
      if (seen.has(value)) return;
      seen.add(value);
      const noKey = !providerReady.has(m.provider);
      const name = m.provider === 'openrouter' ? m.name : `${providerLabel(m.provider)} · ${m.model_id}`;
      const freeTag = m.is_free ? ' · Free' : '';
      choices.push({
        value,
        provider: m.provider,
        model_id: m.model_id,
        label: `${name}${freeTag}${noKey ? ' — no key' : ''}`,
        capability: undefined,
      });
    });
    return choices.sort((a, b) => {
      const aReady = providerReady.has(a.provider) ? 0 : 1;
      const bReady = providerReady.has(b.provider) ? 0 : 1;
      // Free models first within same readiness tier
      const aFree = availableModels.find(m => m.provider === a.provider && m.model_id === a.model_id)?.is_free ? 0 : 1;
      const bFree = availableModels.find(m => m.provider === b.provider && m.model_id === b.model_id)?.is_free ? 0 : 1;
      return aReady - bReady || aFree - bFree || a.provider.localeCompare(b.provider) || a.model_id.localeCompare(b.model_id);
    });
  }, [availableModels, providerReady]);

  function choicesForSpecialist(_s: SpecialistSummary): ModelChoice[] {
    return modelChoices;
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

  function currentMediaLabel(s: SpecialistSummary): string {
    if (!s.mediaModuleId) return '';
    const override = overrideMap.get(s.mediaModuleId);
    if (!override?.provider) return 'Not assigned';
    const provLabel = s.mediaProviderOptions?.find(p => p.provider === override.provider)?.label ?? override.provider;
    return override.model_id ? `${provLabel} · ${override.model_id}` : provLabel;
  }

  function openConfigureMediaAI(s: SpecialistSummary) {
    const override = s.mediaModuleId ? overrideMap.get(s.mediaModuleId) : undefined;
    setSelectedMediaProvider(override?.provider ?? '');
    setSelectedMediaModel(override?.model_id ?? '');
    setSaveError('');
    setConfiguringAI(s);
  }

  async function handleSaveMediaAIModel() {
    if (!configuringAI?.mediaModuleId) return;
    setSaving(true);
    setSaveError('');
    try {
      if (!selectedMediaProvider) {
        await api.deleteBackendOverride(configuringAI.mediaModuleId);
      } else {
        await api.putBackendOverride(configuringAI.mediaModuleId, {
          provider: selectedMediaProvider,
          model_id: selectedMediaModel || null,
          tool_id: null,
          modality: configuringAI.mediaModality ?? 'image',
          strict: true,
        });
      }
      await refreshBackendOverrides();
      setConfiguringAI(null);
      setSelectedMediaProvider('');
      setSelectedMediaModel('');
      showToast('✅ AI model saved');
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : 'Failed to save AI model');
    } finally {
      setSaving(false);
    }
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
    const current = currentAIValue(s);
    setSelectedModel(current);
    const firstOverride = s.llmModuleIds.map(t => overrideMap.get(t)).find(Boolean);
    setStrictOverride(firstOverride?.strict ?? false);
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
          strict: strictOverride,
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
        <div style={{ position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)', background: 'var(--obsidian)', color: 'var(--ivory)', padding: '10px 20px', borderRadius: 0, fontSize: 13, fontWeight: 600, zIndex: 9999, border: '.5px solid var(--border-dark)' }}>
          {toast}
        </div>
      )}

      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">Specialists</div>
          <div className="admin-page-subtitle">
            Installed plugin packages only. Core tools are hidden here; activation is scoped to the selected Brand.
          </div>
        </div>
        {brands.length > 0 && (
          <select className="select" value={selectedBrandId ?? ''} onChange={e => setSelectedBrandId(e.target.value || null)} style={{ maxWidth: 260 }}>
            {brands.map(brand => <option key={brand.id} value={brand.id}>{brand.name}</option>)}
          </select>
        )}
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
                        placeholder={varPlaceholder(varName)}
                        value={credFields[varName] ?? ''}
                        onChange={e => setCredFields(f => ({ ...f, [varName]: e.target.value }))}
                        style={{ width: '100%', fontFamily: sensitive ? 'monospace' : undefined }}
                        autoComplete="off"
                      />
                    </div>
                  );
                })}
                {/* Optional URL + Key fields for custom/seedance image and video providers */}
                {configuringPlugin.plugin_id === 'media.image' && (() => {
                  const prov = (credFields['IMAGE_GEN_PROVIDER'] || '').toLowerCase();
                  if (prov && prov !== 'openai' && prov !== 'gemini') return (
                    <>
                      {(['IMAGE_GEN_WORKER_URL', 'IMAGE_GEN_API_KEY'] as const).map(varName => {
                        const { label, sensitive, hint } = varLabel(varName);
                        return (
                          <div key={varName}>
                            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{label}</label>
                            {hint && <div style={{ color: 'var(--text2)', fontSize: 11, marginBottom: 5 }}>{hint}</div>}
                            <input
                              type={sensitive ? 'password' : 'text'}
                              className="input"
                              placeholder={varPlaceholder(varName)}
                              value={credFields[varName] ?? ''}
                              onChange={e => setCredFields(f => ({ ...f, [varName]: e.target.value }))}
                              style={{ width: '100%', fontFamily: sensitive ? 'monospace' : undefined }}
                              autoComplete="off"
                            />
                          </div>
                        );
                      })}
                    </>
                  );
                  return null;
                })()}
                {configuringPlugin.plugin_id === 'media.video' && (() => {
                  const prov = (credFields['VIDEO_GEN_PROVIDER'] || '').toLowerCase();
                  if (prov && prov !== 'gemini' && prov !== 'local_ffmpeg') return (
                    <>
                      {(['VIDEO_GEN_API_URL', 'VIDEO_GEN_API_KEY'] as const).map(varName => {
                        const { label, sensitive, hint } = varLabel(varName);
                        return (
                          <div key={varName}>
                            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{label}</label>
                            {hint && <div style={{ color: 'var(--text2)', fontSize: 11, marginBottom: 5 }}>{hint}</div>}
                            <input
                              type={sensitive ? 'password' : 'text'}
                              className="input"
                              placeholder={varPlaceholder(varName)}
                              value={credFields[varName] ?? ''}
                              onChange={e => setCredFields(f => ({ ...f, [varName]: e.target.value }))}
                              style={{ width: '100%', fontFamily: sensitive ? 'monospace' : undefined }}
                              autoComplete="off"
                            />
                          </div>
                        );
                      })}
                    </>
                  );
                  return null;
                })()}
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

      {configuringAI && (() => {
        const isMedia = Boolean(configuringAI.mediaModality);
        const isMixed = !isMedia && selectedModel === '__mixed__';

        const providerOptions = configuringAI.mediaProviderOptions ?? [];
        const mediaModelOptions = selectedMediaProvider
          ? (providerOptions.find(p => p.provider === selectedMediaProvider)?.models ?? [])
          : [];

        function isMediaProviderConnected(provider: string): boolean {
          if (provider === 'local_ffmpeg') return true;
          return providers.some(p => p.provider === provider && (p.has_byok_key || p.has_platform_key));
        }

        const builtInOptions = providerOptions.filter(p => p.provider === 'local_ffmpeg');
        const connectedOptions = providerOptions.filter(p => p.provider !== 'local_ffmpeg' && p.provider !== 'custom' && isMediaProviderConnected(p.provider));
        const needsKeyOptions = providerOptions.filter(p => p.provider !== 'local_ffmpeg' && p.provider !== 'custom' && !isMediaProviderConnected(p.provider));
        const customOptions = providerOptions.filter(p => p.provider === 'custom');

        const selectedProviderLabel = providerOptions.find(p => p.provider === selectedMediaProvider)?.label ?? selectedMediaProvider;
        const selectedNeedsKey = Boolean(selectedMediaProvider && selectedMediaProvider !== 'local_ffmpeg' && selectedMediaProvider !== 'custom' && !isMediaProviderConnected(selectedMediaProvider));
        const selectedIsCustom = selectedMediaProvider === 'custom';

        const dismiss = () => { setConfiguringAI(null); setSelectedMediaProvider(''); setSelectedMediaModel(''); setSaveError(''); };
        return (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
            <div className="admin-card" style={{ width: '100%', maxWidth: 520, margin: 0 }}>
              <div style={{ fontWeight: 850, fontSize: 17, marginBottom: 4 }}>Configure AI — {configuringAI.name}</div>
              <div style={{ color: 'var(--text2)', fontSize: 13, marginBottom: 18 }}>
                {isMedia
                  ? `Choose which provider generates ${configuringAI.mediaModality}s. API keys are managed in AI Providers.`
                  : 'Choose the exact LLM/model this specialist should use. Leave on auto-route to let BOS choose the best available model.'}
              </div>

              {isMedia ? (
                <>
                  <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Provider</label>
                  <select
                    className="select"
                    value={selectedMediaProvider}
                    onChange={e => { setSelectedMediaProvider(e.target.value); setSelectedMediaModel(''); }}
                  >
                    <option value="">Not assigned — auto-route</option>
                    {builtInOptions.length > 0 && (
                      <optgroup label="── Built-in · No key needed ──">
                        {builtInOptions.map(p => (
                          <option key={p.provider} value={p.provider}>{p.label}</option>
                        ))}
                      </optgroup>
                    )}
                    {connectedOptions.length > 0 && (
                      <optgroup label="── Connected ──">
                        {connectedOptions.map(p => (
                          <option key={p.provider} value={p.provider}>{p.label} ✓</option>
                        ))}
                      </optgroup>
                    )}
                    {needsKeyOptions.length > 0 && (
                      <optgroup label="── Add key in AI Providers ──">
                        {needsKeyOptions.map(p => (
                          <option key={p.provider} value={p.provider}>{p.label}</option>
                        ))}
                      </optgroup>
                    )}
                    {customOptions.length > 0 && (
                      <optgroup label="── Custom ──">
                        {customOptions.map(p => (
                          <option key={p.provider} value={p.provider}>{p.label}</option>
                        ))}
                      </optgroup>
                    )}
                  </select>

                  {selectedNeedsKey && (
                    <div style={{ marginTop: 10, padding: '10px 12px', background: 'var(--ivory)', border: '.5px solid var(--border-warm)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                      <div style={{ fontSize: 12, color: 'var(--text2)' }}>
                        No API key for <strong>{selectedProviderLabel}</strong> — add one first.
                      </div>
                      <button
                        className="btn btn-ghost btn-sm"
                        style={{ fontSize: 12, whiteSpace: 'nowrap' }}
                        onClick={() => { dismiss(); navigate('/admin/providers'); }}
                      >
                        AI Providers →
                      </button>
                    </div>
                  )}

                  {selectedIsCustom && (
                    <div style={{ marginTop: 10, padding: '10px 12px', background: 'var(--ivory)', border: '.5px solid var(--border-warm)', fontSize: 12, color: 'var(--text2)' }}>
                      Custom provider credentials (URL + API key) are configured in the connector settings on this card.
                    </div>
                  )}

                  {selectedMediaProvider && mediaModelOptions.length > 0 && (
                    <>
                      <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginTop: 14, marginBottom: 6 }}>Model</label>
                      <select className="select" value={selectedMediaModel} onChange={e => setSelectedMediaModel(e.target.value)}>
                        <option value="">Default for provider</option>
                        {mediaModelOptions.map(m => (
                          <option key={m.value} value={m.value}>{m.label}</option>
                        ))}
                      </select>
                    </>
                  )}
                </>
              ) : (
                <>
                  {isMixed ? (
                    <div style={{ background: 'var(--ivory)', border: '.5px solid var(--border-warm)', padding: '12px 14px', marginBottom: 14 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Mixed model settings detected</div>
                      <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 10 }}>
                        The {configuringAI.llmModuleIds.length} tools in this specialist have different model overrides. Select a model below to apply one setting to all, or reset everything to auto-route.
                      </div>
                      <button className="btn btn-ghost btn-sm" onClick={() => setSelectedModel('')}>Reset all to auto-route</button>
                    </div>
                  ) : null}

                  <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Model</label>
                  <select className="select" value={selectedModel} onChange={e => setSelectedModel(e.target.value)}>
                    <option value="">Auto-route best available</option>
                    {isMixed && <option value="__mixed__" disabled>Mixed model settings</option>}
                    {choicesForSpecialist(configuringAI).map(choice => (
                      <option key={choice.value} value={choice.value}>{choice.label}</option>
                    ))}
                  </select>
                  {selectedModel && !isMixed && (
                    <div style={{ marginTop: 14, padding: '10px 12px', background: 'var(--ivory)', border: '.5px solid var(--border-warm)' }}>
                      <label style={{ display: 'flex', gap: 10, alignItems: 'flex-start', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={strictOverride}
                          onChange={e => setStrictOverride(e.target.checked)}
                          style={{ marginTop: 2 }}
                        />
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 600 }}>Strict pin</div>
                          <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 2 }}>
                            When enabled, runs fail if this exact model is unavailable — no fallback. Leave unchecked to fall back to auto-route if the key is removed or the provider goes down.
                          </div>
                        </div>
                      </label>
                    </div>
                  )}
                  <div style={{ color: 'var(--text2)', fontSize: 12, marginTop: 10 }}>
                    Applies to {configuringAI.llmModuleIds.length} LLM tool{configuringAI.llmModuleIds.length !== 1 ? 's' : ''} in this specialist.
                  </div>
                </>
              )}

              {saveError && <div style={{ color: 'var(--error)', fontSize: 13, marginTop: 12 }}>{saveError}</div>}
              <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
                <button className="btn btn-ghost" onClick={dismiss}>Cancel</button>
                <button
                  className="btn btn-primary"
                  onClick={isMedia ? handleSaveMediaAIModel : handleSaveAIModel}
                  disabled={saving || (!isMedia && isMixed)}
                >
                  {saving ? 'Saving…' : (isMedia ? (selectedMediaProvider ? 'Save AI model' : 'Remove assignment') : (selectedModel ? 'Save AI model' : 'Reset to auto-route'))}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {specialists.length === 0 ? (
        <div className="admin-card"><div className="empty-state"><div className="empty-state-icon">◎</div><div className="empty-state-title">No specialists installed</div><div className="empty-state-text">Install capability or plugin packages to see specialists here.</div></div></div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 14 }}>
          {specialists.map(s => {
            const hasAI = s.llmModuleIds.length > 0 || Boolean(s.mediaModuleId);
            const mediaSet = s.mediaModuleId ? Boolean(overrideMap.get(s.mediaModuleId)?.provider) : false;
            const aiLabel = s.mediaModuleId ? currentMediaLabel(s) : currentAILabel(s);
            const aiNotSet = Boolean(s.mediaModuleId && !mediaSet);

            return (
              <div key={s.key} className="admin-card" style={{ margin: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>

                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ fontWeight: 750, fontSize: 15 }}>{s.name}</div>
                    <div style={{ color: 'var(--text2)', fontSize: 12, marginTop: 3, lineHeight: 1.4 }}>{s.description}</div>
                  </div>
                  <span className={`badge badge-${s.readiness === 'needs_setup' ? 'warning' : 'success'}`} style={{ flexShrink: 0 }}>
                    {s.readiness === 'needs_setup' ? 'Needs setup' : s.readiness === 'ready' ? 'Ready' : 'Available'}
                  </span>
                </div>

                {/* AI row — primary action */}
                {hasAI && (
                  <div style={{ padding: '10px 12px', border: '.5px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 11, color: 'var(--text2)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 3 }}>AI model</div>
                      <div style={{ fontSize: 13, color: aiNotSet ? 'var(--text2)' : 'inherit' }}>
                        {aiLabel}
                      </div>
                    </div>
                    <button
                      className={`btn btn-sm ${aiNotSet ? 'btn-dark' : 'btn-ghost'}`}
                      style={{ fontSize: 12, whiteSpace: 'nowrap' }}
                      onClick={() => s.mediaModuleId ? openConfigureMediaAI(s) : openConfigureAI(s)}
                    >
                      {aiNotSet ? 'Set up' : 'Change'}
                    </button>
                  </div>
                )}

                {/* Accounts / connectors */}
                {s.connectors.length > 0 && (
                  <div style={{ display: 'grid', gap: 6 }}>
                    <div style={{ fontSize: 11, color: 'var(--text2)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Accounts</div>
                    {s.connectors.map(connector => (
                      <div key={connector.id} style={{ border: '.5px solid var(--border)', padding: '8px 10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div style={{ fontSize: 13, fontWeight: 600 }}>{connector.label}</div>
                          <div style={{ color: 'var(--text2)', fontSize: 11, marginTop: 2, overflowWrap: 'anywhere' }}>{connector.detail}</div>
                        </div>
                        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
                          <span className={`badge badge-${connectorBadgeClass(connector.status)}`}>{connector.statusText}</span>
                          {connector.actionLabel && connector.actionType === 'brands' && (
                            <button className="btn btn-ghost btn-sm" style={{ fontSize: 11 }} onClick={() => navigate('/admin/brands')}>
                              {connector.actionLabel}
                            </button>
                          )}
                          {connector.actionLabel && connector.actionType === 'plugin' && connector.pluginId && (
                            <button
                              className="btn btn-ghost btn-sm"
                              style={{ fontSize: 11 }}
                              onClick={() => s.mediaModuleId ? openConfigureMediaAI(s) : openConfigure(connector.pluginId!)}
                            >
                              {connector.actionLabel}
                            </button>
                          )}
                          {connector.removable && connector.pluginId && (
                            <button className="btn btn-ghost btn-sm" style={{ fontSize: 11, color: 'var(--text2)' }} onClick={() => handleRemoveCredentials(connector.pluginId!)}>
                              Remove
                            </button>
                          )}
                          {savedPlugin === connector.pluginId && <span style={{ color: 'var(--success)', fontSize: 11 }}>✓</span>}
                          {connector.actionType === 'plugin' && connector.pluginId && (() => {
                            const plug = plugins.find(p => p.plugin_id === connector.pluginId);
                            if (!plug || plug.status === 'error') return null;
                            const active = isPluginActive(plug, selectedBrandId);
                            const toggling = activatingPlugin === connector.pluginId;
                            return (
                              <button
                                className="btn btn-ghost btn-sm"
                                style={{ fontSize: 11, color: active ? 'var(--text2)' : 'var(--accent)', opacity: toggling ? 0.5 : 1 }}
                                disabled={toggling}
                                onClick={() => handleToggleActivation(plug.plugin_id, active)}
                              >
                                {toggling ? '…' : active ? 'Deactivate' : 'Activate'}
                              </button>
                            );
                          })()}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Footer — secondary info */}
                <div style={{ marginTop: 'auto', paddingTop: 8, borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 11, color: 'var(--text2)' }}>{s.readinessText}</span>
                  <span className="badge badge-muted" style={{ fontSize: 11 }}>{s.moduleCount} tool{s.moduleCount !== 1 ? 's' : ''}</span>
                </div>

              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
