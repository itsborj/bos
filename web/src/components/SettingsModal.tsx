import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { BillingSummary, KeyListItem, ProviderInfo, RunListItem } from '../api/types';
import type { SettingsTab } from '../context/UIContext';

interface Props {
  open: boolean;
  tab: SettingsTab;
  onTabChange: (tab: SettingsTab) => void;
  onClose: () => void;
}

/* ── BYOK Tab ── */
function ByokTab() {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [keys, setKeys] = useState<KeyListItem[]>([]);
  const [adding, setAdding] = useState<string | null>(null);
  const [newKey, setNewKey] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    Promise.all([api.getProviders(), api.getProviderKeys()])
      .then(([p, k]) => { setProviders(p.providers); setKeys(k); })
      .catch(() => {});
  }, []);

  const connectedProviders = new Set(keys.map(k => k.provider));

  async function handleAdd(provider: string) {
    if (!newKey.trim()) return;
    setSaving(true);
    try {
      await api.registerKey(provider, newKey.trim());
      setKeys(k => [...k, { provider, created_at: new Date().toISOString() }]);
      setAdding(null);
      setNewKey('');
      setMsg(`${provider} key registered.`);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : 'Failed to register key.');
    } finally {
      setSaving(false);
    }
  }

  async function handleRemove(provider: string) {
    try {
      await api.deleteKey(provider);
      setKeys(k => k.filter(x => x.provider !== provider));
      setMsg(`${provider} key removed.`);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : 'Failed to remove key.');
    }
  }

  return (
    <div>
      <div className="bos-settings-section-title">Execution Providers</div>
      <p className="bos-settings-desc">
        Connect your own API keys (BYOK) or use platform keys. Keys are encrypted at rest and never logged.
      </p>
      {msg && <div className="bos-settings-msg">{msg}</div>}
      {providers.map(p => {
        const hasKey = connectedProviders.has(p.provider);
        return (
          <div key={p.provider} className="bos-byok-row">
            <div className="bos-byok-provider">{p.provider}</div>
            <div className="bos-byok-status-col">
              {hasKey
                ? <><span className="bos-byok-key-display">••••••••••••</span><span className="bos-byok-badge connected">BYOK ✓</span></>
                : <><span className="bos-byok-key-display">Using platform key</span><span className="bos-byok-badge platform">Platform</span></>
              }
              {p.avg_latency_ms !== undefined && p.avg_latency_ms !== null && (
                <span style={{ marginLeft: 'auto', fontSize: '10px', color: '#888', fontFamily: 'monospace' }}>
                  {Math.round(p.avg_latency_ms)}ms
                </span>
              )}
            </div>
            {hasKey
              ? <button className="bos-byok-action" onClick={() => handleRemove(p.provider)}>Remove</button>
              : adding === p.provider
                ? (
                  <div className="bos-byok-add-form">
                    <input
                      className="bos-byok-input"
                      type="password"
                      placeholder="Paste API key..."
                      value={newKey}
                      onChange={e => setNewKey(e.target.value)}
                    />
                    <button className="bos-byok-action primary" disabled={saving} onClick={() => handleAdd(p.provider)}>
                      {saving ? '...' : 'Save'}
                    </button>
                    <button className="bos-byok-action" onClick={() => { setAdding(null); setNewKey(''); }}>Cancel</button>
                  </div>
                )
                : <button className="bos-byok-action" onClick={() => setAdding(p.provider)}>Add BYOK</button>
            }
          </div>
        );
      })}
    </div>
  );
}

/* ── Usage Tab ── */
function UsageTab() {
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getBillingSummary()
      .then(setBilling)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="bos-ws-loading">Loading...</div>;
  if (!billing) return <div className="bos-ws-empty">Could not load billing data.</div>;

  const providerCost = billing.total_provider_cost ?? 0;
  const sellPrice   = billing.total_sell_price ?? 0;
  const tokens      = billing.total_tokens ?? 0;

  return (
    <div>
      <div className="bos-settings-section-title">API Consumption — All Time</div>
      <div className="bos-usage-grid">
        <div className="bos-usage-box">
          <div className="bos-usage-label">Total Runs</div>
          <div className="bos-usage-value">{billing.total_runs}</div>
          <div className="bos-usage-sub">{billing.successful_runs} successful</div>
        </div>
        <div className="bos-usage-box">
          <div className="bos-usage-label">Total Tokens</div>
          <div className="bos-usage-value">{tokens > 0 ? (tokens / 1000).toFixed(1) + 'k' : '—'}</div>
          <div className="bos-usage-sub">All runs combined</div>
        </div>
        <div className="bos-usage-box">
          <div className="bos-usage-label">Provider Cost</div>
          <div className="bos-usage-value">${providerCost.toFixed(2)}</div>
          <div className="bos-usage-sub">Direct to provider</div>
        </div>
        <div className="bos-usage-box">
          <div className="bos-usage-label">Platform Revenue</div>
          <div className="bos-usage-value">${sellPrice.toFixed(2)}</div>
          <div className="bos-usage-sub">After markup</div>
        </div>
        <div className="bos-usage-box">
          <div className="bos-usage-label">Avg Cost / Run</div>
          <div className="bos-usage-value">
            {billing.total_runs > 0 ? '$' + (providerCost / billing.total_runs).toFixed(3) : '—'}
          </div>
          <div className="bos-usage-sub"></div>
        </div>
      </div>
    </div>
  );
}

/* ── Run History Tab ── */
function RunHistoryTab() {
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getRuns({ limit: 30 })
      .then(r => setRuns(r.runs))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="bos-ws-loading">Loading...</div>;

  return (
    <div>
      <div className="bos-settings-section-title">Recent Module Runs</div>
      {runs.length === 0 && <div className="bos-ws-empty">No runs yet.</div>}
      {runs.map(r => (
        <div key={r.run_id} className="bos-run-row">
          <span className="bos-run-module">{r.module_id}</span>
          <span className="bos-run-meta">{r.vertical} · {r.status}</span>
          <span className="bos-run-time">{new Date(r.created_at).toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

/* ── Modal ── */
const TAB_LABELS: Record<SettingsTab, string> = {
  byok: 'Providers & BYOK',
  usage: 'API Usage',
  history: 'Run History',
};

export function SettingsModal({ open, tab, onTabChange, onClose }: Props) {
  if (!open) return null;

  return (
    <div className="bos-settings-overlay" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bos-settings-panel">
        <div className="bos-settings-header">
          <span className="bos-settings-title">Settings</span>
          <button className="bos-settings-close" onClick={onClose}>✕ Close</button>
        </div>
        <div className="bos-settings-tabs">
          {(Object.keys(TAB_LABELS) as SettingsTab[]).map(t => (
            <button
              key={t}
              className={`bos-settings-tab ${tab === t ? 'active' : ''}`}
              onClick={() => onTabChange(t)}
            >
              {TAB_LABELS[t]}
            </button>
          ))}
        </div>
        <div className="bos-settings-body">
          {tab === 'byok'    && <ByokTab />}
          {tab === 'usage'   && <UsageTab />}
          {tab === 'history' && <RunHistoryTab />}
        </div>
      </div>
    </div>
  );
}
