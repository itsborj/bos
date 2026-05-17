import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import type { ModuleInfo, PluginInfo } from '../../api/types';

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
  nextStep?: string;
  pluginId?: string;
};

type SocialConnection = {
  id: string;
  brand_id: string | null;
  platform: string;
  page_name: string | null;
  page_handle: string | null;
  status: string;
};

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
  if (/copy|draft|send|email|creative|outreach|execute/.test(value)) jobs.add('marketing.execute');
  if (/analytics|tracking|seo|report|receive|inbox|optimi[sz]e|audit/.test(value)) jobs.add('marketing.optimize');
  if (!jobs.size && mod.vertical === 'marketing') jobs.add('marketing.execute');
  return [...jobs];
}

function groupKey(mod: ModuleInfo): string {
  const id = mod.id.toLowerCase();
  if (id.includes('gmail')) return 'email';
  if (id.includes('google_ads')) return 'paid-search';
  if (id.includes('search_console') || id.includes('seo')) return 'seo';
  if (id.includes('analytics') || id.includes('tracking')) return 'analytics';
  if (id.includes('clickup')) return 'project-management';
  if (mod.vertical === 'media' || id.startsWith('media.')) return 'media';
  return mod.vertical || 'specialist';
}

function varLabel(varName: string): { label: string; sensitive: boolean; hint: string } {
  const n = varName.toUpperCase();
  if (n.endsWith('_API_TOKEN') || n.endsWith('_TOKEN') || n.endsWith('_SECRET') || n.endsWith('_KEY'))
    return { label: varName.replace(/_/g, ' ').replace(/^[A-Z]+ /, '').toLowerCase().replace(/\b\w/g, c => c.toUpperCase()), sensitive: true, hint: '' };
  if (n.includes('TEAM_ID') || n.includes('WORKSPACE_ID'))
    return { label: 'Workspace ID', sensitive: false, hint: 'Found in your ClickUp URL: app.clickup.com/{ID}/...' };
  if (n.includes('LIST_ID'))
    return { label: 'Default List ID', sensitive: false, hint: 'Navigate to the list in ClickUp — the ID is in the URL' };
  if (n.includes('SITE_URL'))
    return { label: 'Site URL', sensitive: false, hint: 'e.g. sc-domain:example.com or https://www.example.com/' };
  if (n === 'IMAGE_GEN_WORKER_URL')
    return { label: 'Worker URL', sensitive: false, hint: 'The full HTTPS URL of your image generation worker endpoint' };
  if (n === 'IMAGE_GEN_API_KEY')
    return { label: 'API Key', sensitive: true, hint: 'Bearer token used to authenticate requests to the worker' };
  return { label: varName.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase()), sensitive: false, hint: '' };
}

function summarizeGroup(key: string, modules: ModuleInfo[], connections: SocialConnection[], plugins: PluginInfo[]): SpecialistSummary {
  const jobs = [...new Set(modules.flatMap(implementedJobs))];
  const moduleText = modules.map(m => `${m.id} ${m.platform_hint}`.toLowerCase()).join(' ');
  const gmailConnections = connections.filter(conn => conn.platform === 'gmail' && conn.status !== 'revoked');

  if (key === 'email') {
    const cmoJobs = ['marketing.plan', 'marketing.execute', 'marketing.optimize'];
    const connected = gmailConnections.length > 0;
    return {
      key,
      name: 'Email Specialist',
      description: 'Plans email campaigns, drafts outreach, reads reply context, and prepares approved Gmail send actions.',
      jobs: cmoJobs,
      specialties: ['campaign planning', 'drafting', 'inbox intelligence', 'optimization'],
      readiness: connected ? 'ready' : 'needs_setup',
      readinessText: connected
        ? `${gmailConnections.length} Gmail account${gmailConnections.length !== 1 ? 's' : ''} connected`
        : 'Connect Gmail from Brands / Clients to unlock inbox and send actions',
      risk: moduleText.includes('send') ? 'Draft by default; real sends require explicit owner approval' : 'Draft / review',
      moduleCount: modules.length,
      nextStep: connected ? 'Use the CMO to plan, draft, approve, then send.' : 'Connect Gmail, verify sender identity, then create a test draft.',
    };
  }

  if (key === 'paid-search') {
    return {
      key,
      name: 'Paid Search Specialist',
      description: 'Reviews paid-search performance and prepares optimization or ad-draft artifacts.',
      jobs,
      specialties: ['paid search', 'budget efficiency', 'ad drafts'],
      readiness: 'needs_setup',
      readinessText: 'Needs connector setup',
      risk: 'Read and draft first; spend changes require approval',
      moduleCount: modules.length,
    };
  }

  if (key === 'seo') {
    return {
      key,
      name: 'SEO Specialist',
      description: 'Audits search visibility, content opportunities, and organic growth constraints.',
      jobs,
      specialties: ['SEO', 'content opportunities', 'technical review'],
      readiness: 'installed',
      readinessText: 'Installed',
      risk: 'Diagnostic / recommendation',
      moduleCount: modules.length,
    };
  }

  if (key === 'analytics') {
    return {
      key,
      name: 'Analytics Specialist',
      description: 'Diagnoses measurement, tracking, and performance signals for optimization work.',
      jobs,
      specialties: ['tracking', 'measurement', 'performance signals'],
      readiness: 'installed',
      readinessText: 'Installed',
      risk: 'Read-only / diagnostic',
      moduleCount: modules.length,
    };
  }

  if (key === 'project-management') {
    const plugin = plugins.find(p => p.plugin_id === 'channel.clickup');
    const configured = plugin?.credentials_configured ?? false;
    return {
      key,
      name: 'Project Management',
      description: 'Reads campaign task status from ClickUp and creates tasks from approved plans.',
      jobs: ['marketing.execute', 'marketing.optimize'],
      specialties: ['task tracking', 'campaign execution', 'status intelligence'],
      readiness: configured ? 'ready' : 'needs_setup',
      readinessText: configured ? 'ClickUp connected' : 'Add ClickUp credentials to enable task read/create',
      risk: 'Read by default; task creation requires explicit approval',
      moduleCount: modules.length,
      nextStep: configured ? 'Ask the CMO to check clickup or create tasks.' : undefined,
      pluginId: plugin?.plugin_id,
    };
  }

  if (key === 'media') {
    const plugin = plugins.find(p => p.plugin_id === 'media.image');
    const configured = plugin?.credentials_configured ?? false;
    return {
      key,
      name: 'Image Generation',
      description: 'Generates image creatives from text prompts — Google Ads display ads, social images, hero images, and banners. Provider-agnostic: swap the worker URL to change providers without rewiring callers.',
      jobs: ['media.generate'],
      specialties: ['image generation', 'visual creative', 'ad creative'],
      readiness: configured ? 'ready' : 'needs_setup',
      readinessText: configured ? 'Image generation connected' : 'Add worker URL and API key to enable image generation',
      risk: 'Generate only — no external publishing',
      moduleCount: modules.length,
      nextStep: configured ? 'Ask the CMO to generate an image or ad creative.' : undefined,
      pluginId: plugin?.plugin_id,
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
    moduleCount: modules.length,
  };
}

export function AdminModules() {
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [connections, setConnections] = useState<SocialConnection[]>([]);
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [configuringPlugin, setConfiguringPlugin] = useState<PluginInfo | null>(null);
  const [credFields, setCredFields] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  const refreshPlugins = async () => {
    const { plugins: p } = await api.listPlugins().catch(() => ({ plugins: [] as PluginInfo[] }));
    setPlugins(p);
  };

  useEffect(() => {
    async function load() {
      const [{ verticals }, socialConnections] = await Promise.all([
        api.getVerticals(),
        api.listSocialConnections().catch(() => [] as SocialConnection[]),
      ]);
      const results = await Promise.all(
        verticals.map(v => api.getModules(v.vertical).then(r => r.modules).catch(() => [] as ModuleInfo[]))
      );
      setModules(results.flat());
      setConnections(socialConnections as SocialConnection[]);
      await refreshPlugins();
    }
    load().catch(() => {}).finally(() => setLoading(false));
  }, []);

  const specialists = useMemo(() => {
    const visible = modules.filter(mod => !mod.id.toLowerCase().includes('test_stub'));
    const grouped = new Map<string, ModuleInfo[]>();
    visible.forEach(mod => {
      const key = groupKey(mod);
      grouped.set(key, [...(grouped.get(key) ?? []), mod]);
    });
    return [...grouped.entries()].map(([key, mods]) => summarizeGroup(key, mods, connections, plugins));
  }, [modules, connections, plugins]);

  async function handleSaveCredentials() {
    if (!configuringPlugin) return;
    setSaving(true);
    setSaveError('');
    try {
      await api.savePluginCredentials(configuringPlugin.plugin_id, credFields);
      await refreshPlugins();
      setConfiguringPlugin(null);
      setCredFields({});
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  }

  function openConfigure(pluginId: string) {
    const plugin = plugins.find(p => p.plugin_id === pluginId);
    if (!plugin) return;
    const initial: Record<string, string> = {};
    plugin.requires_platform_vars.forEach(v => { initial[v] = ''; });
    setCredFields(initial);
    setSaveError('');
    setConfiguringPlugin(plugin);
  }

  if (loading) {
    return <div className="admin-page"><div className="loading-full"><span className="spinner" /></div></div>;
  }

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">Specialists</div>
          <div className="admin-page-subtitle">
            Installed marketing specialists available to the CMO. Internal module IDs, backend routing, and test harnesses are hidden from normal admin workflow.
          </div>
        </div>
      </div>

      {configuringPlugin && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="admin-card" style={{ width: '100%', maxWidth: 480, margin: 0 }}>
            <div style={{ fontWeight: 850, fontSize: 17, marginBottom: 4 }}>Configure {configuringPlugin.name}</div>
            <div style={{ color: 'var(--text2)', fontSize: 13, marginBottom: 20 }}>Credentials are encrypted and stored in BOS. They are never returned via API.</div>
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
                      style={{ width: '100%' }}
                    />
                  </div>
                );
              })}
            </div>
            {saveError && <div style={{ color: 'var(--error)', fontSize: 13, marginTop: 12 }}>{saveError}</div>}
            <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => { setConfiguringPlugin(null); setSaveError(''); }}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSaveCredentials} disabled={saving}>
                {saving ? 'Saving…' : 'Save credentials'}
              </button>
            </div>
          </div>
        </div>
      )}

      {specialists.length === 0 ? (
        <div className="admin-card"><div className="empty-state"><div className="empty-state-icon">◎</div><div className="empty-state-title">No specialists installed</div><div className="empty-state-text">Install capability or plugin packages to see specialists here.</div></div></div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 14 }}>
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
                    <span style={{ color: 'var(--text2)', fontSize: 12 }}>{s.readinessText}</span>
                    <span className="badge badge-muted">{s.moduleCount} tool{s.moduleCount !== 1 ? 's' : ''}</span>
                  </div>
                  {s.nextStep && <div style={{ color: 'var(--text2)', fontSize: 12 }}>{s.nextStep}</div>}
                  {s.pluginId && (
                    <button
                      className="btn btn-ghost"
                      style={{ fontSize: 12, padding: '4px 10px', alignSelf: 'flex-start' }}
                      onClick={() => openConfigure(s.pluginId!)}
                    >
                      {s.readiness === 'ready' ? 'Update credentials' : 'Configure'}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
