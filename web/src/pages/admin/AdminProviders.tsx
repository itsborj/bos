import { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { api } from '../../api/client';
import type { KeyListItem, ProviderInfo } from '../../api/types';

type CheckState = { status: string; message: string };
type LoginState = { login_id: string; authorize_url?: string };

function providerLabel(provider: string): string {
  if (provider === 'openai') return 'OpenAI Chat';
  return provider;
}

function credentialLabel(provider: ProviderInfo): { tone: string; text: string } {
  if (provider.auth_mode === 'oauth') return { tone: 'success', text: 'Login connected' };
  if (provider.has_byok_key) return { tone: 'info', text: 'API key stored' };
  if (provider.has_platform_key) return { tone: 'warning', text: 'Platform fallback' };
  return { tone: 'muted', text: 'Not connected' };
}

function providerStatus(provider: ProviderInfo): { tone: string; text: string } {
  if (provider.status === 'live') return { tone: 'success', text: 'Live' };
  if (provider.status === 'error') return { tone: 'danger', text: 'Error' };
  if (provider.status === 'stored_unverified') return { tone: 'warning', text: 'Stored · unverified' };
  if (provider.status === 'platform_available') return { tone: 'info', text: 'Platform available' };
  if (provider.status === 'healthy') return { tone: 'success', text: 'Healthy' };
  if (provider.status === 'degraded') return { tone: 'warning', text: 'Degraded' };
  return { tone: 'muted', text: provider.status || 'Unknown' };
}

function fmtDateTime(value?: string | null): string {
  return value ? new Date(value).toLocaleString() : 'Never';
}

function modelSummary(provider: ProviderInfo): string {
  if (!provider.top_models.length) return 'No seeded models';
  return provider.top_models.slice(0, 3).map((m) => m.model_id).join(', ');
}

type ProviderNavState = {
  brand_id?: string;
  brand_name?: string;
};

export function AdminProviders() {
  const location = useLocation();
  const navState = (location.state || {}) as ProviderNavState;
  const selectedBrandId = navState.brand_id;
  const selectedBrandName = navState.brand_name;
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [keys, setKeys] = useState<KeyListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [addProvider, setAddProvider] = useState('');
  const [addKey, setAddKey] = useState('');
  const [adding, setAdding] = useState(false);
  const [checking, setChecking] = useState<string | null>(null);
  const [checkResult, setCheckResult] = useState<Record<string, CheckState>>({});
  const [error, setError] = useState<string | null>(null);
  const [oauthBusy, setOauthBusy] = useState<string | null>(null);
  const [oauthMessage, setOauthMessage] = useState<string | null>(null);
  const [loginState, setLoginState] = useState<Record<string, LoginState>>({});
  const [callbackUrls, setCallbackUrls] = useState<Record<string, string>>({});
  const [expandedProvider, setExpandedProvider] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [provResult, keyResult] = await Promise.all([
        api.getProviders(selectedBrandId).catch(() => ({ providers: [] as ProviderInfo[] })),
        api.getProviderKeys(selectedBrandId).catch(() => [] as KeyListItem[]),
      ]);
      setProviders(provResult.providers ?? []);
      setKeys(keyResult ?? []);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [selectedBrandId]);

  const openai = useMemo(() => providers.find((provider) => provider.provider === 'openai') ?? null, [providers]);
  const apiKeyProviders = useMemo(
    () => providers.filter((provider) => provider.auth_supported.includes('api_key')),
    [providers],
  );
  const sortedProviders = useMemo(() => {
    const priority = (p: ProviderInfo) => {
      if (p.provider === 'openai') return 0;
      if (p.status === 'live') return 1;
      if (p.status === 'error') return 2;
      if (p.connected || p.has_platform_key) return 3;
      return 4;
    };
    return [...providers].sort((a, b) => priority(a) - priority(b) || a.provider.localeCompare(b.provider));
  }, [providers]);

  const counts = useMemo(() => ({
    live: providers.filter((p) => p.status === 'live').length,
    error: providers.filter((p) => p.status === 'error').length,
    credentials: providers.filter((p) => p.connected).length,
    models: providers.reduce((sum, p) => sum + p.model_count, 0),
  }), [providers]);

  async function handleAddKey(e: React.FormEvent) {
    e.preventDefault();
    if (!addProvider || !addKey.trim()) return;
    setAdding(true);
    setError(null);
    try {
      await api.registerKey(addProvider, addKey.trim(), selectedBrandId);
      setAddProvider('');
      setAddKey('');
      await load();
    } catch (e: unknown) {
      setError((e as Error).message ?? 'Failed to register key');
    } finally {
      setAdding(false);
    }
  }

  async function handleDeleteKey(provider: string) {
    if (!confirm(`Remove ${providerLabel(provider)} API key?`)) return;
    await api.deleteKey(provider, selectedBrandId).catch(() => {});
    await load();
  }

  async function handleDeleteAuth(provider: string) {
    if (!confirm(`Disconnect ${providerLabel(provider)} login?`)) return;
    await api.deleteProviderAuth(provider).catch(() => {});
    await load();
  }

  async function handleCheck(provider: string) {
    setChecking(provider);
    setCheckResult((prev) => {
      const next = { ...prev };
      delete next[provider];
      return next;
    });
    try {
      const result = await api.checkKey(provider, selectedBrandId);
      setCheckResult((prev) => ({ ...prev, [provider]: { status: result.status, message: result.message } }));
      await load();
    } catch (e: unknown) {
      setCheckResult((prev) => ({ ...prev, [provider]: { status: 'error', message: (e as Error).message ?? 'check failed' } }));
    } finally {
      setChecking(null);
    }
  }

  async function startLogin(provider: string) {
    setOauthBusy(provider);
    setOauthMessage(null);
    try {
      const result = await api.startProviderLogin(provider);
      setLoginState((prev) => ({
        ...prev,
        [provider]: {
          login_id: result.login_id,
          authorize_url: result.login.authorize_url,
        },
      }));
      setCallbackUrls((prev) => ({ ...prev, [provider]: '' }));
    } catch (e: unknown) {
      setOauthMessage((e as Error).message ?? 'Failed to start login');
    } finally {
      setOauthBusy(null);
    }
  }

  async function completeLogin(provider: string) {
    const pending = loginState[provider];
    const callbackUrl = callbackUrls[provider]?.trim();
    if (!pending || !callbackUrl) return;
    setOauthBusy(provider);
    setOauthMessage(null);
    try {
      await api.completeProviderLogin(provider, pending.login_id, callbackUrl);
      setLoginState((prev) => {
        const next = { ...prev };
        delete next[provider];
        return next;
      });
      setCallbackUrls((prev) => ({ ...prev, [provider]: '' }));
      await load();
      setOauthMessage(`${providerLabel(provider)} connected.`);
    } catch (e: unknown) {
      setOauthMessage((e as Error).message ?? 'Failed to complete login');
    } finally {
      setOauthBusy(null);
    }
  }

  if (loading) {
    return (
      <div className="admin-page">
        <div className="loading-full"><span className="spinner" /></div>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">{selectedBrandId ? `${selectedBrandName || 'Brand'} Provider Access` : 'AI Providers'}</div>
          <div className="admin-page-subtitle">
            {selectedBrandId
              ? 'BYOK credentials saved here are scoped to this brand only. They will not be shared with other brands.'
              : 'System/platform model access for CMO chat, specialist execution, and evaluation. Add brand-specific BYOK from a brand setup flow.'}
          </div>
        </div>
      </div>

      {oauthMessage && <div className="alert alert-success" style={{ marginBottom: 16 }}>{oauthMessage}</div>}
      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="admin-stats-grid" style={{ marginBottom: 16 }}>
        <div className="admin-stat"><span>Checked live</span><strong>{counts.live}</strong></div>
        <div className="admin-stat"><span>Failing</span><strong>{counts.error}</strong></div>
        <div className="admin-stat"><span>Saved credentials</span><strong>{counts.credentials}</strong></div>
        <div className="admin-stat"><span>Routable models</span><strong>{counts.models}</strong></div>
      </div>

      {openai && (
        <div className="admin-card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 20, alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 480px' }}>
              <div className="admin-card-title">Primary CMO Provider</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '8px 0 10px' }}>
                <span className={`badge badge-${providerStatus(openai).tone}`}>{providerStatus(openai).text}</span>
                <span className={`badge badge-${credentialLabel(openai).tone}`}>{credentialLabel(openai).text}</span>
                <span className="badge badge-info">{openai.top_models[0]?.model_id ?? 'model not selected'}</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10, fontSize: 12, color: 'var(--text2)' }}>
                <div><strong>Provider</strong><br />{providerLabel(openai.provider)}</div>
                <div><strong>Last used</strong><br />{fmtDateTime(openai.last_used_at)}</div>
                <div><strong>Last check</strong><br />{fmtDateTime(openai.last_check_at)}</div>
                <div><strong>Avg latency</strong><br />{openai.avg_latency_ms ? `${Math.round(openai.avg_latency_ms)}ms` : 'No runs yet'}</div>
              </div>
              {openai.last_check_message && (
                <div style={{ marginTop: 10, fontSize: 12, color: 'var(--text2)' }}>Last check result: {openai.last_check_message}</div>
              )}
              {openai.auth_mode === 'oauth' && openai.expires_at && (
                <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 8 }}>Access token expires {new Date(openai.expires_at).toLocaleString()}</div>
              )}
            </div>

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
              {openai.auth_mode === 'oauth' ? (
                <>
                  <button className="btn btn-ghost btn-sm" onClick={() => handleCheck('openai')} disabled={checking === 'openai'}>{checking === 'openai' ? 'Checking…' : 'Test connection'}</button>
                  <button className="btn btn-secondary btn-sm" onClick={() => startLogin('openai')} disabled={oauthBusy === 'openai'}>Reconnect</button>
                  <button className="btn btn-danger btn-sm" onClick={() => handleDeleteAuth('openai')}>Disconnect</button>
                </>
              ) : (
                <>
                  <button className="btn btn-dark btn-sm" onClick={() => startLogin('openai')} disabled={oauthBusy === 'openai'}>{oauthBusy === 'openai' ? 'Starting…' : 'Connect OpenAI'}</button>
                  {selectedBrandId && <button className="btn btn-secondary btn-sm" onClick={() => setAddProvider('openai')}>Use brand BYOK key instead</button>}
                </>
              )}
            </div>
          </div>

          {checkResult.openai && <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text2)' }}>Connection check: <strong>{checkResult.openai.status}</strong> — {checkResult.openai.message}</div>}

          {loginState.openai && (
            <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
              <div className="admin-card-title" style={{ fontSize: 16, marginBottom: 10 }}>Connect OpenAI in 3 steps</div>
              <div style={{ display: 'grid', gap: 14 }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13 }}>Step 1 — Open the login page</div>
                  <div style={{ fontSize: 12, color: 'var(--text2)', margin: '4px 0 8px' }}>Sign into your OpenAI / ChatGPT account in a new tab.</div>
                  {loginState.openai.authorize_url && <a className="btn btn-secondary btn-sm" href={loginState.openai.authorize_url} target="_blank" rel="noreferrer">Open OpenAI Login ↗</a>}
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13 }}>Step 2 — Copy the callback URL</div>
                  <div style={{ fontSize: 12, color: 'var(--text2)', margin: '4px 0 8px' }}>After sign-in, copy the full callback URL and paste it here.</div>
                  <textarea className="input" style={{ minHeight: 90, resize: 'vertical', fontFamily: 'var(--mono)', fontSize: 12 }} placeholder="Paste callback URL here…" value={callbackUrls.openai ?? ''} onChange={(e) => setCallbackUrls((prev) => ({ ...prev, openai: e.target.value }))} />
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13 }}>Step 3 — Finish connection</div>
                  <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                    <button className="btn btn-dark btn-sm" onClick={() => completeLogin('openai')} disabled={oauthBusy === 'openai' || !(callbackUrls.openai ?? '').trim()}>{oauthBusy === 'openai' ? 'Connecting…' : 'Finish connection'}</button>
                    <button className="btn btn-ghost btn-sm" onClick={() => setLoginState((prev) => { const next = { ...prev }; delete next.openai; return next; })}>Cancel</button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="admin-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
          <div>
            <div className="admin-card-title">Provider Health</div>
            <div style={{ fontSize: 13, color: 'var(--text2)' }}>Connection is based on the latest explicit check when available; older failed runs no longer override a successful check.</div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={() => void load()}>Refresh</button>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Provider</th>
                <th>Connection</th>
                <th>Credential</th>
                <th>Last used</th>
                <th>Last check</th>
                <th>Models</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sortedProviders.map((provider) => {
                const status = providerStatus(provider);
                const credential = credentialLabel(provider);
                const verified = checkResult[provider.provider];
                const expanded = expandedProvider === provider.provider;
                return (
                  <>
                    <tr key={provider.provider}>
                      <td>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{providerLabel(provider.provider)}</div>
                        <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 3 }}>{provider.provider}</div>
                      </td>
                      <td><span className={`badge badge-${status.tone}`}>{status.text}</span></td>
                      <td><span className={`badge badge-${credential.tone}`}>{credential.text}</span></td>
                      <td style={{ fontSize: 12, color: 'var(--text2)' }}>{fmtDateTime(provider.last_used_at)}</td>
                      <td style={{ fontSize: 12, color: 'var(--text2)' }}>
                        {fmtDateTime(provider.last_check_at)}
                        {(verified || provider.last_check_message) && <div style={{ marginTop: 3 }}>{verified ? `${verified.status} — ${verified.message}` : provider.last_check_message}</div>}
                      </td>
                      <td style={{ fontSize: 12, color: 'var(--text2)', maxWidth: 300 }}>{provider.model_count} · {modelSummary(provider)}</td>
                      <td>
                        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                          {provider.connected && <button className="btn btn-ghost btn-sm" onClick={() => handleCheck(provider.provider)} disabled={checking === provider.provider}>{checking === provider.provider ? '…' : 'Check'}</button>}
                          {provider.auth_mode === 'oauth' && <button className="btn btn-danger btn-sm" onClick={() => handleDeleteAuth(provider.provider)}>Disconnect</button>}
                          {provider.has_byok_key && <button className="btn btn-danger btn-sm" onClick={() => handleDeleteKey(provider.provider)}>Remove key</button>}
                          <button className="btn btn-secondary btn-sm" onClick={() => setExpandedProvider(expanded ? null : provider.provider)}>{expanded ? 'Hide' : 'Details'}</button>
                        </div>
                      </td>
                    </tr>
                    {expanded && (
                      <tr key={`${provider.provider}-details`}>
                        <td colSpan={7} style={{ background: '#fafafa' }}>
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
                            <div>
                              <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 6 }}>Model options</div>
                              {provider.top_models.length ? provider.top_models.map((model) => (
                                <div key={model.model_id} style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 4 }}>{model.model_id} · {model.quality_tier} · {model.capability} · {model.latency_ms}ms{model.supports_json ? ' · JSON' : ''}</div>
                              )) : <div style={{ fontSize: 12, color: 'var(--text2)' }}>No seeded models.</div>}
                            </div>
                            <div>
                              <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 6 }}>Routing facts</div>
                              <div style={{ fontSize: 12, color: 'var(--text2)' }}>Platform key: {provider.has_platform_key ? 'available' : 'none'}</div>
                              <div style={{ fontSize: 12, color: 'var(--text2)' }}>Auth mode: {provider.auth_mode || 'none'}</div>
                              <div style={{ fontSize: 12, color: 'var(--text2)' }}>Average latency: {provider.avg_latency_ms ? `${Math.round(provider.avg_latency_ms)}ms` : 'No successful runs yet'}</div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Add or Replace Direct API Key</div>
        <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 14 }}>
          Keys are encrypted and never shown again after saving. {selectedBrandId ? `This key will only be used for ${selectedBrandName || 'this brand'}.` : 'For client/customer BYOK, open Provider Access from that brand so the key is brand-scoped.'}
        </div>
        {keys.length > 0 && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
            {keys.map((key) => <span className="badge badge-info" key={key.provider}>{providerLabel(key.provider)} key · {new Date(key.created_at).toLocaleDateString()}</span>)}
          </div>
        )}
        <form onSubmit={handleAddKey} style={{ display: 'grid', gridTemplateColumns: 'minmax(180px, 240px) minmax(260px, 1fr) auto', gap: 12, alignItems: 'end' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="label">Provider</label>
            <select className="select" value={addProvider} onChange={(e) => setAddProvider(e.target.value)}>
              <option value="">Select provider…</option>
              {apiKeyProviders.map((provider) => <option key={provider.provider} value={provider.provider}>{providerLabel(provider.provider)}</option>)}
            </select>
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="label">API Key</label>
            <input className="input" type="password" value={addKey} onChange={(e) => setAddKey(e.target.value)} placeholder="sk-… or similar" />
          </div>
          <button type="submit" className="btn btn-dark" disabled={adding || !selectedBrandId || !addProvider || !addKey.trim()}>{adding ? 'Registering…' : 'Save brand key'}</button>
        </form>
        {!selectedBrandId && <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 10 }}>BYOK keys are saved per brand. Open this page from a brand setup or brand detail workflow to add a key.</div>}
      </div>
    </div>
  );
}
