import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, clearApiKey, getApiKey } from '../api/client';
import type { BillingSummary, KeyListItem, ProviderInfo } from '../api/types';

export function Settings() {
  const navigate = useNavigate();
  const [providers, setProviders]   = useState<ProviderInfo[]>([]);
  const [keys, setKeys]             = useState<KeyListItem[]>([]);
  const [summary, setSummary]       = useState<BillingSummary | null>(null);
  const [loading, setLoading]       = useState(true);
  const [copied, setCopied]         = useState(false);
  const [addProvider, setAddProvider] = useState('');
  const [addKey, setAddKey]           = useState('');
  const [adding, setAdding]           = useState(false);
  const [addError, setAddError]       = useState('');

  const wsKey = getApiKey() ?? '';

  useEffect(() => {
    Promise.all([
      api.getProviders().catch(() => ({ providers: [] as ProviderInfo[] })),
      api.getProviderKeys().catch(() => [] as KeyListItem[]),
      api.getBillingSummary().catch(() => null),
    ]).then(([p, k, s]) => {
      setProviders(p.providers);
      setKeys(k);
      setSummary(s);
      setLoading(false);
    });
  }, []);

  function copyKey() {
    navigator.clipboard.writeText(wsKey).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  async function removeKey(provider: string) {
    await api.deleteKey(provider).catch(() => {});
    setKeys(k => k.filter(x => x.provider !== provider));
  }

  async function submitAddKey(e: React.FormEvent) {
    e.preventDefault();
    if (!addProvider.trim() || !addKey.trim()) return;
    setAdding(true); setAddError('');
    try {
      await api.registerKey(addProvider.trim(), addKey.trim());
      const updated = await api.getProviderKeys();
      setKeys(updated);
      setAddProvider(''); setAddKey('');
    } catch (err: unknown) {
      setAddError(err instanceof Error ? err.message : 'Failed to register key');
    } finally {
      setAdding(false);
    }
  }

  function provDot(status: string) {
    if (status === 'healthy') return <div className="prov-dot" style={{ background: '#28a745' }} />;
    if (status === 'degraded') return <div className="prov-dot" style={{ background: '#e6a817' }} />;
    return <div className="prov-dot" style={{ background: '#dc3545' }} />;
  }

  const providerCost = Number(summary?.total_provider_cost ?? 0) || 0;
  const sellPrice = Number(summary?.total_sell_price ?? 0) || 0;
  const totalRuns = Number(summary?.total_runs ?? 0) || 0;
  const totalTokens = Number(summary?.total_tokens ?? 0) || 0;

  function provPill(status: string) {
    if (status === 'healthy')  return <span className="status-pill sp-live"><span className="sp-dot" />Healthy</span>;
    if (status === 'degraded') return <span className="status-pill" style={{ background: '#fff3cd', color: '#856404' }}><span className="sp-dot" />Slow</span>;
    return <span className="status-pill sp-error"><span className="sp-dot" />Down</span>;
  }

  if (loading) {
    return (
      <div className="loading-full">
        <span className="spinner" />
        Loading…
      </div>
    );
  }

  return (
    <div className="ux-page">
      <div className="ux-hero">
        <div>
          <div className="ux-eyebrow">Operations settings</div>
          <h1 className="ux-title">Access, providers, and usage</h1>
          <p className="ux-subtitle">Keep infrastructure healthy without exposing provider plumbing to the CMO workspace.</p>
        </div>
        <div className="ux-stat-row compact">
          <div className="ux-stat"><span>{providers.length}</span><small>providers</small></div>
          <div className="ux-stat"><span>{keys.length}</span><small>keys</small></div>
          <div className="ux-stat"><span>{totalRuns}</span><small>runs</small></div>
        </div>
      </div>

      <div className="settings-grid">
      {/* Left column */}
      <div>
        {/* Provider Health */}
        <div className="section-header">
          <span className="section-title">Provider Health</span>
        </div>
        {providers.length === 0 ? (
          <div className="card" style={{ color: '#999', fontSize: 13 }}>No providers configured.</div>
        ) : (
          providers.map(p => (
            <div key={p.provider} className="provider-card">
              {provDot(p.status)}
              <div>
                <div className="provider-name">{p.provider}</div>
                <div className="provider-meta">
                  {p.has_platform_key ? 'Platform key' : p.has_byok_key ? 'BYOK key' : 'No key'} · {p.model_count} model{p.model_count !== 1 ? 's' : ''}
                </div>
              </div>
              {provPill(p.status)}
            </div>
          ))
        )}

        {/* BYOK Keys */}
        <div className="section-header" style={{ marginTop: 20 }}>
          <span className="section-title">BYOK Keys</span>
        </div>
        {keys.map(k => (
          <div key={k.provider} className="key-row">
            <span className="key-provider">{k.provider}</span>
            <span className="key-masked">••••••••••••••••</span>
            <span className="key-date">{new Date(k.created_at).toLocaleDateString()}</span>
            <span className="key-remove" onClick={() => removeKey(k.provider)}>Remove</span>
          </div>
        ))}

        <form onSubmit={submitAddKey} style={{ marginTop: 8 }}>
          <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
            <input
              className="input"
              style={{ width: '30%' }}
              placeholder="Provider"
              value={addProvider}
              onChange={e => setAddProvider(e.target.value)}
            />
            <input
              className="input"
              style={{ flex: 1 }}
              placeholder="API key"
              value={addKey}
              onChange={e => setAddKey(e.target.value)}
              type="password"
            />
          </div>
          {addError && <div style={{ fontSize: 12, color: '#721c24', marginBottom: 6 }}>{addError}</div>}
          <button type="submit" className="btn btn-sm btn-dark" disabled={adding || !addProvider.trim() || !addKey.trim()}>
            {adding ? 'Registering…' : '+ Register key'}
          </button>
        </form>
      </div>

      {/* Right column */}
      <div>
        {/* API Access */}
        <div className="section-header">
          <span className="section-title">API Access</span>
        </div>
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="ws-label" style={{ marginBottom: 6 }}>Workspace API Key</div>
          <div className="api-key-row">
            <div className="api-key-display">{wsKey.slice(0, 12)}••••••••••••••••{wsKey.slice(-4)}</div>
            <button className="copy-btn" onClick={copyKey}>{copied ? '✓ Copied' : 'Copy'}</button>
          </div>
          <div style={{ fontSize: 11, color: '#999', marginTop: 8 }}>
            Used by Claude agent · WhatsApp bridge · any REST client
          </div>
          <button
            className="btn btn-sm btn-danger"
            style={{ marginTop: 12 }}
            onClick={() => { clearApiKey(); navigate('/auth'); }}
          >
            Sign out
          </button>
        </div>

        {/* Billing */}
        <div className="section-header">
          <span className="section-title">Billing Summary</span>
        </div>
        <div className="card">
          <div className="billing-grid">
            <div>
              <div className="ws-label" style={{ marginBottom: 4 }}>Provider Cost</div>
              <div className="billing-num">${providerCost.toFixed(2)}</div>
              <div className="billing-lbl">all time · {totalRuns} runs</div>
            </div>
            <div>
              <div className="ws-label" style={{ marginBottom: 4 }}>Sell Price</div>
              <div className="billing-num">${sellPrice.toFixed(2)}</div>
              <div className="billing-lbl">
                ${(sellPrice - providerCost).toFixed(2)} margin
              </div>
            </div>
          </div>
          {summary && (
            <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid #f0f0f0', fontSize: 12, color: '#666' }}>
              {totalTokens.toLocaleString()} total tokens
            </div>
          )}
        </div>
      </div>
      </div>
    </div>
  );
}
