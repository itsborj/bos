import { api } from '../api/client';
import type { BrandResponse, OnboardingStatus, PluginInfo, ProviderInfo, SocialConnectionResponse } from '../api/types';

export type StreamActivationChecklistItem = {
  key: string;
  label: string;
  ok: boolean;
  detail: string;
  requiredBy: string;
  to: string;
  state?: Record<string, string>;
};

export type StreamActivationChecklistResult = {
  items: StreamActivationChecklistItem[];
  completed: number;
  ready: boolean;
};

function connectionReady(connections: SocialConnectionResponse[], platform: string): boolean {
  return connections.some(c => c.platform === platform && (c.status === 'connected' || c.status === 'active'));
}

function connectionStatus(connections: SocialConnectionResponse[], platform: string): string | null {
  return connections.find(c => c.platform === platform)?.status || null;
}

function pluginActive(plugin: PluginInfo, brandId?: string): boolean {
  const brandRow = brandId ? plugin.activation_by_brand?.find(a => a.brand_id === brandId) : undefined;
  const orgRow = plugin.activation_by_brand?.find(a => a.brand_id === null);
  return (brandRow || orgRow)?.status === 'active';
}

export function buildStreamActivationChecklist(input: {
  brandId?: string;
  brandName?: string;
  providers?: ProviderInfo[];
  brand?: BrandResponse | null;
  onboardingStatus?: OnboardingStatus | null;
  connections?: SocialConnectionResponse[];
  plugins?: PluginInfo[];
  brandKitReady?: boolean;
  driveRootName?: string | null;
  driveLogoCount?: number;
}): StreamActivationChecklistResult {
  const brandId = input.brandId;
  const brandName = input.brandName || input.brand?.name || '';
  const connections = input.connections || [];
  const providers = input.providers || [];
  const plugins = input.plugins || [];
  const installedUsablePlugins = plugins.filter(p => p.status === 'installed' && !p.plugin_id.toLowerCase().includes('test_stub'));
  const activePlugins = installedUsablePlugins.filter(p => pluginActive(p, brandId));
  const aiProviderReady = providers.some(p => p.connected || p.has_platform_key || p.has_byok_key);
  const onboarding = input.onboardingStatus || null;
  const profileReady = Boolean(onboarding?.brand_profile_configured);
  const liveCampaignReady = Boolean(onboarding?.live_campaign_present);
  const driveConnected = Boolean(onboarding?.drive_connected || connectionReady(connections, 'google_drive'));
  const driveStatus = onboarding?.drive_connection_status || connectionStatus(connections, 'google_drive');
  const driveNeedsReauth = driveStatus === 'needs_reauth';
  const gmailConnected = connectionReady(connections, 'gmail');
  const calendarConnected = connectionReady(connections, 'google_calendar');
  const connectedPublishPlatforms = onboarding?.client_readiness?.publish_channels || [];
  const workspaceConfigured = Boolean(onboarding?.workspace_configured || brandId);
  const driveRootName = onboarding?.drive_root_name || input.driveRootName || null;
  const driveLogoCount = onboarding?.brand_mark_configured ? 1 : (input.driveLogoCount || 0);
  const brandKitReady = onboarding ? onboarding.campaign_brand_kit_approved : Boolean(input.brandKitReady);
  const capabilityReady = onboarding?.client_readiness?.capabilities.ok ?? (activePlugins.length > 0 && activePlugins.every(plugin => plugin.credentials_configured));
  const capabilityLabel = onboarding?.client_readiness?.capabilities.label || (activePlugins.length > 0 ? `${activePlugins.length} capability plugin(s) active.` : 'Installed capabilities exist but none are active for this brand/org.');
  const directChecklistCoversMissingPlatform = (platform: string): boolean => {
    if (platform === 'google_drive') return !driveConnected || !driveRootName || driveLogoCount <= 0;
    if (platform === 'gmail') return !gmailConnected;
    if (platform === 'google_calendar') return !calendarConnected;
    return false;
  };
  const activePluginProblems = activePlugins.filter(plugin => {
    const missingVars = plugin.missing_vars || [];
    const missingSocial = (plugin.requires_social_connection || [])
      .filter(platform => !connectionReady(connections, platform))
      .filter(platform => !directChecklistCoversMissingPlatform(platform));
    const directlyTrackedDebt = (plugin.requires_social_connection || []).some(platform => directChecklistCoversMissingPlatform(platform));
    const unattributedCredentialProblem = !plugin.credentials_configured && missingVars.length === 0 && missingSocial.length === 0 && !directlyTrackedDebt;
    return plugin.status !== 'installed' || missingVars.length > 0 || missingSocial.length > 0 || unattributedCredentialProblem;
  });
  const onboardingLinkState = brandId ? { brand_id: brandId, brand_name: brandName } : undefined;
  const onboardingTo = brandId ? `/admin/onboarding?brand_id=${encodeURIComponent(brandId)}&brand_name=${encodeURIComponent(brandName)}` : '/admin/onboarding';
  const brandBase = brandId ? `/admin/brands/${encodeURIComponent(brandId)}` : '/admin/brands';

  const items: StreamActivationChecklistItem[] = [
    {
      key: 'ai-provider',
      label: 'AI provider connected',
      ok: aiProviderReady,
      detail: aiProviderReady ? 'At least one platform or BYOK provider is available.' : 'Connect a model provider before CMO/Stream can generate briefs or artifacts.',
      requiredBy: 'CMO generation, decision briefs, Stream artifact generation',
      to: '/admin/providers',
    },
    {
      key: 'brand-selected',
      label: 'Client/brand selected',
      ok: Boolean(brandId),
      detail: brandId ? `${brandName || 'Brand'} is the active operating scope.` : 'Choose the brand whose Stream should be activated.',
      requiredBy: 'Brand-scoped Stream activation',
      to: '/admin/brands',
    },
    {
      key: 'workspace-configured',
      label: 'Workspace configured',
      ok: workspaceConfigured,
      detail: workspaceConfigured ? 'Workspace/client operating context exists.' : 'Finish the base onboarding workspace setup before running admin workflows.',
      requiredBy: 'Admin setup banner, CMO, campaign operations',
      to: '/admin/setup',
    },
    {
      key: 'brand-profile',
      label: 'Brand profile imported',
      ok: profileReady,
      detail: profileReady ? 'Brand profile is imported and available.' : 'Import the organization/client brief so CMO has brand context.',
      requiredBy: 'Admin → Setup & Readiness',
      to: onboardingTo,
      state: onboardingLinkState,
    },
    {
      key: 'live-campaign',
      label: 'Live campaign extracted',
      ok: liveCampaignReady,
      detail: liveCampaignReady ? 'A live campaign exists for this brand.' : 'Create or extract the first live campaign from the onboarding brief.',
      requiredBy: 'Admin → Setup brand readiness',
      to: onboardingTo,
      state: onboardingLinkState,
    },
    {
      key: 'brand-kit',
      label: 'Brand Creative Brief approved',
      ok: brandKitReady,
      detail: brandKitReady ? 'Identity, visual language, creative boundaries, and campaign guidance are approved.' : 'Generate and approve the Brand Creative Brief.',
      requiredBy: 'Stream readiness and brand-aware creative generation',
      to: brandId ? `${brandBase}?tab=brand-kit#campaign-brand-kit` : onboardingTo,
      state: onboardingLinkState,
    },
    {
      key: 'drive-connected',
      label: 'Google Drive connected',
      ok: driveConnected,
      detail: driveConnected ? 'Drive OAuth is connected for the active brand.' : driveNeedsReauth ? 'Reconnect Google Drive for this brand. The saved token expired or was revoked.' : 'Connect Google Drive so approved brand assets and generated media can be stored.',
      requiredBy: 'Setup & readiness and image/video rendering',
      to: brandId ? `${brandBase}?tab=integrations#integration-google_drive` : '/admin/brands',
    },
    {
      key: 'publish-channel',
      label: 'At least one publish channel connected',
      ok: connectedPublishPlatforms.length > 0,
      detail: connectedPublishPlatforms.length > 0 ? `Connected: ${connectedPublishPlatforms.join(', ')}.` : 'Connect Facebook, YouTube, TikTok, or Google Business before BOS can publish approved work.',
      requiredBy: 'Setup & readiness publish channels and approved artifact execution',
      to: brandId ? `${brandBase}?tab=integrations#publish-channels` : '/admin/brands',
    },
    {
      key: 'gmail',
      label: 'Gmail connected',
      ok: gmailConnected,
      detail: gmailConnected ? 'Gmail is connected for Stream outreach monitoring.' : 'Connect Gmail before BOS can watch replies or queue Gmail sends.',
      requiredBy: 'Gmail reply monitoring',
      to: brandId ? `${brandBase}?tab=integrations#integration-gmail` : '/admin/brands',
    },
    {
      key: 'google-calendar',
      label: 'Google Calendar connected',
      ok: calendarConnected,
      detail: calendarConnected ? 'Calendar is connected for live booking availability.' : 'Connect Google Calendar before Booking Pages can check live availability.',
      requiredBy: 'Booking Pages live availability',
      to: brandId ? `${brandBase}?tab=integrations#integration-google_calendar` : '/admin/brands',
    },
  ];

  const driveInsertIndex = items.findIndex(item => item.key === 'drive-connected') + 1;
  if (driveConnected) {
    items.splice(driveInsertIndex, 0, {
      key: 'drive-folder',
      label: 'Brand Kit Drive folder selected',
      ok: Boolean(driveRootName),
      detail: driveRootName ? `Using Drive folder: ${driveRootName}.` : 'Choose one validated Brand Kit folder in Integrations.',
      requiredBy: 'Brand Kit asset storage and media rendering',
      to: brandId ? `${brandBase}?tab=integrations#integration-google_drive` : '/admin/brands',
    });
    if (driveRootName) {
      items.splice(driveInsertIndex + 1, 0, {
        key: 'brand-logo',
        label: 'Logo/wordmark present in selected Drive folder',
        ok: driveLogoCount > 0,
        detail: driveLogoCount > 0 ? `${driveLogoCount} logo/wordmark file(s) found.` : 'Add an image named like *_logo, *_wordmark, or *_brandmark.',
        requiredBy: 'Brand Kit asset validation and branded image/video output',
        to: brandId ? `${brandBase}?tab=brand-kit#brand-kit-assets` : '/admin/brands',
      });
    }
  }

  if (installedUsablePlugins.length > 0) {
    items.push({
      key: 'capabilities',
      label: 'At least one installed capability activated',
      ok: capabilityReady,
      detail: capabilityLabel,
      requiredBy: 'Admin → Setup & Readiness capability gate',
      to: '/admin/modules',
    });
    if (activePlugins.length > 0) {
      items.push({
        key: 'capability-prerequisites',
        label: 'Active capability prerequisites configured',
        ok: capabilityReady && activePluginProblems.length === 0,
        detail: capabilityReady && activePluginProblems.length === 0 ? 'Active capabilities have no additional credential or social blockers beyond the checklist items above.' : `${activePluginProblems.length} active capability plugin(s) are missing credentials, environment variables, or required social connections.`,
        requiredBy: 'Admin → Capabilities safe activation',
        to: '/admin/modules',
      });
    }
  }

  const completed = items.filter(item => item.ok).length;
  return { items, completed, ready: items.length > 0 && completed === items.length };
}

export async function loadStreamActivationChecklist(brandId?: string, brandName?: string): Promise<StreamActivationChecklistResult> {
  const [providers, brands, onboarding, connections, pluginResult] = await Promise.all([
    api.getProviders(brandId).catch(() => ({ providers: [] as ProviderInfo[] })),
    api.getBrands().catch(() => ({ brands: [] as BrandResponse[], total: 0 })),
    brandId ? api.getOnboardingStatus(brandId).catch(() => null) : Promise.resolve(null),
    api.listSocialConnections(brandId).catch(() => [] as SocialConnectionResponse[]),
    api.listPlugins(brandId).catch(() => ({ plugins: [] as PluginInfo[] })),
  ]);

  const brand = (brands.brands || []).find(b => b.id === brandId) || null;
  return buildStreamActivationChecklist({
    brandId,
    brandName,
    providers: providers.providers || [],
    brand,
    onboardingStatus: onboarding,
    connections,
    plugins: pluginResult.plugins || [],
  });
}
