import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { PluginInfo, SocialConnectionResponse } from '../../api/types';

function varLabel(varName: string): { label: string; sensitive: boolean; hint: string } {
  const n = varName.toUpperCase();
  if (n.endsWith('_API_TOKEN') || n.endsWith('_TOKEN'))
    return { label: 'API Token', sensitive: true, hint: 'Get from ClickUp → Settings → Apps' };
  if (n.endsWith('_SECRET') || n.endsWith('_CLIENT_SECRET'))
    return { label: varName.replace(/_/g, ' ').replace(/^\w+ /, ''), sensitive: true, hint: '' };
  if (n.includes('TEAM_ID') || n.includes('WORKSPACE_ID'))
    return { label: 'Workspace ID', sensitive: false, hint: 'In your ClickUp URL: app.clickup.com/{ID}/...' };
  if (n.includes('LIST_ID'))
    return { label: 'Default List ID', sensitive: false, hint: 'Navigate to the list in ClickUp — the ID is in the URL' };
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
  if (n === 'IMAGE_GEN_API_KEY')
    return { label: 'Image Gen API Key', sensitive: true, hint: 'Bearer token for your Cloudflare Workers AI endpoint' };
  if (n === 'IMAGE_GEN_WORKER_URL')
    return { label: 'Worker URL', sensitive: false, hint: 'Full URL of your Cloudflare Worker, e.g. https://image-gen.yourname.workers.dev' };
  if (n.endsWith('_API_KEY'))
    return { label: 'API Key', sensitive: true, hint: '' };
  if (n.endsWith('_URL') || n.endsWith('_ENDPOINT'))
    return { label: varName.replace(/^[A-Z_]+?_/, '').replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase()), sensitive: false, hint: '' };
  return {
    label: varName.replace(/^[A-Z_]+?_/, '').replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase()),
    sensitive: false,
    hint: '',
  };
}

function pluginDisplayName(plugin: PluginInfo): string {
  const id = plugin.plugin_id.toLowerCase();
  if (id.includes('clickup')) return 'ClickUp';
  if (id.includes('google_ads') || id.includes('google-ads')) return 'Google Ads';
  if (id.includes('search_console') || id.includes('search-console')) return 'Google Search Console';
  if (id.includes('gmail')) return 'Gmail';
  if (id.includes('google_analytics') || id.includes('google-analytics')) return 'Google Analytics';
  return plugin.name;
}

function pluginDescription(plugin: PluginInfo): string {
  const id = plugin.plugin_id.toLowerCase();
  if (id.includes('clickup')) return 'Read campaign task status and create tasks from approved plans.';
  if (id.includes('google_ads') || id.includes('google-ads')) return 'Pull paid search performance and draft ad copy.';
  if (id.includes('search_console') || id.includes('search-console')) return 'Read organic search performance and SEO signals.';
  if (id.includes('gmail')) return 'Send outreach and read reply intelligence.';
  if (id.includes('google_analytics')) return 'Read website analytics and conversion signals.';
  return `${plugin.implements.join(', ')} specialist.`;
}

type ConfigModal = {
  plugin: PluginInfo;
  fields: Record<string, string>;
};

const OAUTH_PLATFORMS: Record<string, { label: string; icon: string }> = {
  gmail:           { label: 'Gmail',           icon: '✉️' },
  google_calendar: { label: 'Google Calendar', icon: '📅' },
};

export function AdminConnectors() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [socialConns, setSocialConns] = useState<SocialConnectionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modal, setModal] = useState<ConfigModal | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [saved, setSaved] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navigate = useNavigate();

  function showToast(msg: string) {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 4000);
  }

  useEffect(() => {
    const gm = searchParams.get('gmail');
    const gc = searchParams.get('google_calendar');
    const reason = searchParams.get('reason') || '';
    if (gm || gc) {
      setSearchParams({});
      if (gm === 'connected') showToast('✅ Gmail connected');
      else if (gm) showToast(`⚠️ Gmail failed — ${reason.replace(/_/g, ' ')}`);
      if (gc === 'connected') showToast('✅ Google Calendar connected');
      else if (gc) showToast(`⚠️ Google Calendar failed — ${reason.replace(/_/g, ' ')}`);
    }
  }, []);

  async function load() {
    setLoading(true);
    setError('');
    try {
      const [{ plugins: p }, conns] = await Promise.all([
        api.listPlugins(),
        api.listSocialConnections(),
      ]);
      setPlugins(p.filter(p => p.requires_platform_vars.length > 0));
      setSocialConns(conns);
    } catch {
      setError('Could not load connectors. Make sure the API is running.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function openConfigure(plugin: PluginInfo) {
    const fields: Record<string, string> = {};
    plugin.requires_platform_vars.forEach(v => { fields[v] = ''; });
    setSaveError('');
    setSaved(null);
    setModal({ plugin, fields });
  }

  async function handleSave() {
    if (!modal) return;
    setSaving(true);
    setSaveError('');
    try {
      await api.savePluginCredentials(modal.plugin.plugin_id, modal.fields);
      setSaved(modal.plugin.plugin_id);
      setModal(null);
      await load();
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : 'Failed to save credentials');
    } finally {
      setSaving(false);
    }
  }

  async function handleRemove(pluginId: string) {
    await api.deletePluginCredentials(pluginId).catch(() => {});
    await load();
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
          <div className="admin-page-title">Connectors</div>
          <div className="admin-page-subtitle">
            Connect external platforms so CMO specialists can read data and take approved actions.
          </div>
        </div>
      </div>

      {error && (
        <div className="admin-card" style={{ borderColor: 'var(--error)', color: 'var(--error)', fontSize: 13 }}>{error}</div>
      )}

      {/* OAuth connections — read-only summary, managed per brand */}
      {socialConns.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <div className="label">Google Account Connections</div>
            <button className="btn btn-ghost btn-sm" style={{ fontSize: 12 }} onClick={() => navigate('/admin/brands')}>Manage in Brands →</button>
          </div>
          <div style={{ display: 'grid', gap: 8 }}>
            {socialConns.map(c => {
              const meta = OAUTH_PLATFORMS[c.platform] || { label: c.platform, icon: '⚙️' };
              return (
                <div key={c.id} className="admin-card" style={{ margin: 0, padding: '12px 16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span style={{ fontSize: 15 }}>{meta.icon}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 700 }}>{c.page_name || c.page_id}</div>
                      <div style={{ fontSize: 11, color: 'var(--text2)' }}>{meta.label}</div>
                    </div>
                    <span className="badge badge-success" style={{ fontSize: 10 }}>Connected</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Plugin connectors — API key based */}
      <div className="label" style={{ marginBottom: 10 }}>Plugin Connectors</div>

      {modal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <div className="admin-card" style={{ width: '100%', maxWidth: 480, margin: 0 }}>
            <div style={{ fontWeight: 850, fontSize: 17, marginBottom: 4 }}>
              Configure {pluginDisplayName(modal.plugin)}
            </div>
            <div style={{ color: 'var(--text2)', fontSize: 13, marginBottom: 20 }}>
              Credentials are encrypted at rest and never returned via API.
            </div>
            <div style={{ display: 'grid', gap: 16 }}>
              {modal.plugin.requires_platform_vars.map(varName => {
                const { label, sensitive, hint } = varLabel(varName);
                return (
                  <div key={varName}>
                    <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                      {label}
                    </label>
                    {hint && (
                      <div style={{ color: 'var(--text2)', fontSize: 11, marginBottom: 6 }}>{hint}</div>
                    )}
                    <input
                      type={sensitive ? 'password' : 'text'}
                      className="input"
                      placeholder={varName}
                      value={modal.fields[varName] ?? ''}
                      onChange={e => setModal(m => m ? { ...m, fields: { ...m.fields, [varName]: e.target.value } } : m)}
                      style={{ width: '100%', fontFamily: sensitive ? 'monospace' : undefined }}
                      autoComplete="off"
                    />
                  </div>
                );
              })}
            </div>
            {saveError && (
              <div style={{ color: 'var(--error)', fontSize: 13, marginTop: 12 }}>{saveError}</div>
            )}
            <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => setModal(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                {saving ? 'Saving…' : 'Save credentials'}
              </button>
            </div>
          </div>
        </div>
      )}

      {plugins.length === 0 && !error ? (
        <div className="admin-card">
          <div className="empty-state">
            <div className="empty-state-icon">⊞</div>
            <div className="empty-state-title">No connectors installed</div>
            <div className="empty-state-text">Install plugin packages under api/plugins/ to connect external platforms.</div>
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 12 }}>
          {plugins.map(plugin => {
            const configured = plugin.credentials_configured;
            const name = pluginDisplayName(plugin);
            const description = pluginDescription(plugin);
            return (
              <div key={plugin.plugin_id} className="admin-card" style={{ margin: 0 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'flex-start' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                      <div style={{ fontWeight: 850, fontSize: 15 }}>{name}</div>
                      <span className={`badge badge-${configured ? 'success' : 'warning'}`}>
                        {configured ? (plugin.credential_source === 'env_var' ? 'Via .env' : 'Connected') : 'Not configured'}
                      </span>
                      {saved === plugin.plugin_id && (
                        <span style={{ color: 'var(--success)', fontSize: 12 }}>✓ Saved</span>
                      )}
                    </div>
                    <div style={{ color: 'var(--text2)', fontSize: 13 }}>{description}</div>

                    {!configured && plugin.missing_vars.length > 0 && (
                      <div style={{ marginTop: 10 }}>
                        <div className="label" style={{ marginBottom: 5 }}>Missing</div>
                        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                          {plugin.missing_vars.map(v => (
                            <span key={v} className="badge badge-muted" style={{ fontFamily: 'monospace', fontSize: 11 }}>{v}</span>
                          ))}
                        </div>
                      </div>
                    )}

                    {configured && (
                      <div style={{ marginTop: 10 }}>
                        <div className="label" style={{ marginBottom: 5 }}>Implements</div>
                        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                          {plugin.implements.map(j => (
                            <span key={j} className="badge badge-info">{j}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
                    {plugin.credential_source !== 'env_var' && (
                      <button
                        className="btn btn-primary"
                        style={{ fontSize: 13, whiteSpace: 'nowrap' }}
                        onClick={() => openConfigure(plugin)}
                      >
                        {configured ? 'Update' : 'Configure'}
                      </button>
                    )}
                    {configured && plugin.credential_source === 'database' && (
                      <button
                        className="btn btn-ghost"
                        style={{ fontSize: 12, color: 'var(--text2)' }}
                        onClick={() => handleRemove(plugin.plugin_id)}
                      >
                        Remove
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
