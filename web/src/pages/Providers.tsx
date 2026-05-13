import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { KeyListItem, ProviderInfo } from '../api/types';

export function Providers() {
  const navigate = useNavigate();
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [keys, setKeys] = useState<KeyListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [addProvider, setAddProvider] = useState('');
  const [addKey, setAddKey] = useState('');
  const [adding, setAdding] = useState(false);
  const [checking, setChecking] = useState<string | null>(null);
  const [checkResult, setCheckResult] = useState<Record<string, { status: string; message: string }>>({});
  const [error, setError] = useState<string | null>(null);

  async function load() {
    const [provResult, keyResult] = await Promise.all([
      api.getProviders().catch(() => ({ providers: [] as ProviderInfo[] })),
      api.getProviderKeys().catch(() => [] as KeyListItem[]),
    ]);
    setProviders(provResult.providers);
    setKeys(keyResult);
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function handleAddKey(e: React.FormEvent) {
    e.preventDefault();
    if (!addProvider || !addKey.trim()) return;
    setAdding(true);
    setError(null);
    try {
      await api.registerKey(addProvider, addKey.trim());
      setAddProvider('');
      setAddKey('');
      await load();
    } catch (e: unknown) {
      setError((e as Error).message ?? 'Failed to register key');
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(provider: string) {
    if (!confirm(`Remove ${provider} BYOK key?`)) return;
    await api.deleteKey(provider).catch(() => {});
    await load();
  }

  async function handleCheck(provider: string) {
    setChecking(provider);
    try {
      const result = await api.checkKey(provider);
      setCheckResult(prev => ({ ...prev, [provider]: { status: result.status, message: result.message } }));
    } catch (e: unknown) {
      setCheckResult(prev => ({ ...prev, [provider]: { status: 'error', message: (e as Error).message ?? 'check failed' } }));
    } finally {
      setChecking(null);
    }
  }

  return (
    <div>
      <div className="subpage-header">
        <button className="subpage-back" onClick={() => navigate('/settings')}>‹ Settings</button>
        <span className="subpage-title">Providers</span>
      </div>

      <div className="subpage-body ux-page">
        <div className="ux-hero">
          <div>
            <div className="ux-eyebrow">Provider access</div>
            <h1 className="ux-title">Model and credential health</h1>
            <p className="ux-subtitle">Connect BYOK credentials and confirm platform availability before routing CMO or module backends.</p>
          </div>
          <div className="ux-stat-row compact">
            <div className="ux-stat"><span>{providers.length}</span><small>providers</small></div>
            <div className="ux-stat"><span>{keys.length}</span><small>BYOK keys</small></div>
          </div>
        </div>

        {loading ? (
          <div className="loading-full" style={{ minHeight: 200 }}>
            <span className="spinner" />
          </div>
        ) : (
          <>
            <div className="card ux-lift-card">
              <div className="card-title">Provider Status</div>
              {providers.length === 0 ? (
                <div style={{ color: 'var(--text2)', fontSize: 13 }}>No providers found.</div>
              ) : (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Provider</th>
                        <th>Models</th>
                        <th>Status</th>
                        <th>Platform</th>
                        <th>BYOK</th>
                      </tr>
                    </thead>
                    <tbody>
                      {providers.map(p => (
                        <tr key={p.provider}>
                          <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{p.provider}</td>
                          <td style={{ color: 'var(--text2)' }}>{p.model_count}</td>
                          <td>
                            <span className={`status-dot status-dot-${p.status}`} />
                            {p.status}
                          </td>
                          <td>
                            {p.has_platform_key
                              ? <span className="badge badge-success">active</span>
                              : <span className="badge badge-muted">none</span>}
                          </td>
                          <td>
                            {p.has_byok_key
                              ? <span className="badge badge-info">registered</span>
                              : <span className="badge badge-muted">none</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="card ux-lift-card">
              <div className="card-title">BYOK Keys</div>

              {keys.length > 0 && (
                <div className="table-wrap" style={{ marginBottom: 20 }}>
                  <table className="table">
                    <thead>
                      <tr><th>Provider</th><th>Since</th><th>Check</th><th></th></tr>
                    </thead>
                    <tbody>
                      {keys.map(k => (
                        <tr key={k.provider}>
                          <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{k.provider}</td>
                          <td style={{ color: 'var(--text2)', fontSize: 12 }}>{new Date(k.created_at).toLocaleDateString()}</td>
                          <td>
                            {checkResult[k.provider] ? (
                              <span className={`badge badge-${checkResult[k.provider].status === 'ok' ? 'success' : 'error'}`}>
                                {checkResult[k.provider].status}
                              </span>
                            ) : (
                              <button
                                className="btn btn-ghost btn-sm"
                                onClick={() => handleCheck(k.provider)}
                                disabled={checking === k.provider}
                              >
                                {checking === k.provider
                                  ? <span className="spinner" style={{ width: 12, height: 12 }} />
                                  : 'Check'}
                              </button>
                            )}
                          </td>
                          <td>
                            <button className="btn btn-danger btn-sm" onClick={() => handleDelete(k.provider)}>
                              Remove
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="section-title">Register BYOK Key</div>
              {error && <div className="alert alert-error">{error}</div>}
              <form onSubmit={handleAddKey}>
                <div className="form-group">
                  <label className="label">Provider</label>
                  <select className="select" value={addProvider} onChange={e => setAddProvider(e.target.value)}>
                    <option value="">Select provider…</option>
                    <option value="openrouter">openrouter</option>
                    <option value="gemini">gemini</option>
                    <option value="nvidia">nvidia</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="label">API Key</label>
                  <input
                    className="input"
                    type="password"
                    value={addKey}
                    onChange={e => setAddKey(e.target.value)}
                    placeholder="sk-… or similar"
                  />
                </div>
                <button
                  type="submit"
                  className="btn btn-dark"
                  disabled={adding || !addProvider || !addKey.trim()}
                >
                  {adding ? 'Registering…' : 'Register Key'}
                </button>
              </form>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
