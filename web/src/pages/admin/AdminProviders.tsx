import { Fragment, useEffect, useMemo, useState } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { BackendOverride, KeyListItem, ProviderInfo, ProviderModelLive } from '../../api/types';

type CheckState = { status: string; message: string };
type LoginState = { login_id: string; authorize_url?: string };

const PROVIDER_LABELS: Record<string, string> = {
  openai:      'OpenAI',
  openrouter:  'OpenRouter',
  gemini:      'Google Gemini',
  nvidia:      'NVIDIA AI Cloud',
};

function providerLabel(provider: string): string {
  return PROVIDER_LABELS[provider] ?? provider;
}

function isProviderConnected(provider: ProviderInfo): boolean {
  return Boolean(provider.connected || provider.has_byok_key || provider.has_platform_key || provider.auth_mode === 'oauth');
}

function connectionTitle(provider: ProviderInfo): string {
  if (provider.auth_mode === 'oauth') return 'Connected with login';
  if (provider.has_byok_key) return 'Connected with API key';
  if (provider.has_platform_key) return 'Platform access available';
  return 'Not connected';
}

function fmtDateTime(value?: string | null): string {
  return value ? new Date(value).toLocaleString() : 'Never';
}

function modelSummary(provider: ProviderInfo): string {
  if (!provider.top_models.length) return 'No seeded models';
  return provider.top_models.slice(0, 3).map((m) => m.model_id).join(', ');
}

// ── Model helpers ─────────────────────────────────────────────────────────────

function friendlyModelName(modelId: string): string {
  const id = modelId.replace(':free', '').toLowerCase();
  // OpenRouter prefixed
  if (id === 'deepseek/deepseek-r1') return 'DeepSeek R1';
  if (id === 'meta-llama/llama-3.3-70b-instruct') return 'Llama 3.3 70B';
  if (id === 'meta-llama/llama-3.1-70b-instruct') return 'Llama 3.1 70B';
  if (id === 'meta-llama/llama-3.1-8b-instruct') return 'Llama 3.1 8B';
  if (id === 'qwen/qwen-2.5-72b-instruct') return 'Qwen 2.5 72B';
  if (id === 'google/gemma-2-27b-it') return 'Gemma 2 27B';
  if (id === 'google/gemma-2-9b-it') return 'Gemma 2 9B';
  if (id === 'mistralai/mistral-7b-instruct') return 'Mistral 7B';
  if (id === 'anthropic/claude-sonnet-4-5') return 'Claude Sonnet 4.5';
  if (id === 'openai/gpt-4o') return 'GPT-4o';
  if (id === 'google/gemini-2.5-pro') return 'Gemini 2.5 Pro';
  // Direct providers
  if (id === 'gemini-2.5-pro') return 'Gemini 2.5 Pro';
  if (id === 'gemini-2.5-flash') return 'Gemini 2.5 Flash';
  if (id === 'gemini-2.0-flash') return 'Gemini 2.0 Flash';
  if (id === 'gpt-4o') return 'GPT-4o';
  if (id === 'gpt-4o-mini') return 'GPT-4o Mini';
  if (id.includes('nemotron-70b')) return 'Llama Nemotron 70B';
  return modelId;
}

function formatCost(inputCost: number): string {
  const perMillion = inputCost * 1_000_000;
  return `$${perMillion % 1 === 0 ? perMillion.toFixed(0) : perMillion.toFixed(2)}/M in`;
}

// Version family — models in the same family are shown as version history
function modelVersionFamily(modelId: string): string {
  const id = modelId.replace(':free', '').toLowerCase();
  if (id.includes('llama-3') && id.includes('70b')) return 'llama-70b';
  if (id.includes('llama-3') && (id.includes('8b') || id.includes('3b'))) return 'llama-small';
  if (id.includes('deepseek-r1')) return 'deepseek-r1';
  if (id.includes('qwen-2.5')) return 'qwen-25';
  if (id.includes('gemma-2')) return 'gemma-2';
  if (id.includes('mistral-7b')) return 'mistral-7b';
  if (id.includes('claude-sonnet-4-5') || id.includes('claude-sonnet-4')) return 'claude-sonnet-4';
  if (id.includes('gpt-4o-mini')) return 'gpt-4o-mini';
  if (id.includes('gpt-4o')) return 'gpt-4o';
  if (id.includes('gemini-2.5')) return 'gemini-25';
  if (id.includes('gemini-2.0') || id.includes('gemini-2.')) return 'gemini-2x';
  if (id.includes('nemotron')) return 'nemotron';
  return modelId;
}

type ModelChoice = {
  value: string;
  provider: string;
  model_id: string;
  label: string;
  isLatestInFamily: boolean;
  isFree: boolean;
  inputCost: number;
};

export function AdminProviders() {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  // AI Providers is org-level infrastructure — never brand-scoped.
  // Brand-specific nav state is intentionally ignored here.
  void location.state;

  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [keys, setKeys] = useState<KeyListItem[]>([]);
  const [availableModels, setAvailableModels] = useState<ProviderModelLive[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [oauthMessage, setOauthMessage] = useState<string | null>(null);

  // BYOK form
  const [addProvider, setAddProvider] = useState('');
  const [addKey, setAddKey] = useState('');
  const [adding, setAdding] = useState(false);

  // CMO model override
  const [cmoOverride, setCmoOverride] = useState<BackendOverride | null>(null);
  const [cmoModel, setCmoModel] = useState('');
  const [savingCmo, setSavingCmo] = useState(false);

  // Diagnostics panel
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [checking, setChecking] = useState<string | null>(null);
  const [checkResult, setCheckResult] = useState<Record<string, CheckState>>({});
  const [expandedProvider, setExpandedProvider] = useState<string | null>(null);
  const [oauthBusy, setOauthBusy] = useState<string | null>(null);
  const [loginState, setLoginState] = useState<Record<string, LoginState>>({});
  const [callbackUrls, setCallbackUrls] = useState<Record<string, string>>({});

  useEffect(() => {
    const gemini = searchParams.get('gemini');
    const account = searchParams.get('account');
    if (gemini === 'connected') {
      setOauthMessage(`Google Gemini AI connected${account ? ` (${account})` : ''}.`);
      setSearchParams({}, { replace: true });
    } else if (gemini === 'error' || gemini === 'denied') {
      const reason = searchParams.get('reason') ?? '';
      setError(`Google Gemini connection failed${reason ? `: ${reason}` : ''}.`);
      setSearchParams({}, { replace: true });
    }
  }, []);

  async function load() {
    setLoading(true);
    try {
      const [provResult, keyResult, modelResult, overrideResult] = await Promise.all([
        api.getProviders().catch(() => ({ providers: [] as ProviderInfo[] })),
        api.getProviderKeys().catch(() => [] as KeyListItem[]),
        api.getAvailableModels().catch(() => ({ models: [] as ProviderModelLive[] })),
        api.getBackendOverrides().catch(() => ({ overrides: [] as BackendOverride[] })),
      ]);
      setProviders(provResult.providers ?? []);
      setKeys(keyResult ?? []);
      setAvailableModels(modelResult.models ?? []);
      const cmo = overrideResult.overrides.find(o => o.target === 'cmo.main') ?? null;
      setCmoOverride(cmo);
      setCmoModel(cmo?.model_id ? `${cmo.provider}::${cmo.model_id}` : '');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  // ── Computed ────────────────────────────────────────────────────────────────

  const providerReady = useMemo(
    () => new Set(providers.filter(isProviderConnected).map(p => p.provider)),
    [providers],
  );

  const cmoIsActive = useMemo(() => providers.some(isProviderConnected), [providers]);

  const primaryProvider = useMemo(() => {
    const priority = ['openai', 'openrouter', 'gemini', 'nvidia'];
    for (const p of priority) {
      const found = providers.find(prov => prov.provider === p && isProviderConnected(prov));
      if (found) return found;
    }
    return providers.find(isProviderConnected) ?? null;
  }, [providers]);

  // What the CMO is actually running right now (resolved, not "auto-routing")
  const cmoCurrentLabel = useMemo(() => {
    if (cmoOverride?.model_id) {
      return `${friendlyModelName(cmoOverride.model_id)} · ${providerLabel(cmoOverride.provider)}`;
    }
    if (primaryProvider?.top_models[0]) {
      return `${friendlyModelName(primaryProvider.top_models[0].model_id)} (auto-selected)`;
    }
    if (cmoIsActive) return 'Klaroha AI (auto-selected)';
    return null;
  }, [cmoOverride, primaryProvider, cmoIsActive]);

  // Whether the current CMO model uses the platform key (not BYOK)
  const cmoUsesPlatformKey = useMemo(() => {
    if (cmoOverride?.provider) return !providerReady.has(cmoOverride.provider) || primaryProvider?.has_platform_key;
    return primaryProvider?.has_platform_key && !primaryProvider?.has_byok_key;
  }, [cmoOverride, primaryProvider, providerReady]);

  const apiKeyProviders = useMemo(
    () => providers.filter(p => p.auth_supported.includes('api_key')),
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

  // Model choices grouped into families for the optgroup picker.
  // We collect all options first, sort by family + version (newest first),
  // then assign "Latest" to the first model in each family — so the label
  // Build picker choices from the live /providers/models response.
  // Backend already returns: OpenRouter free models (sorted by quality then name)
  // then direct-provider paid models. We just need to assign "Latest" labels
  // within version families and group by free/paid for the optgroups.
  const allModelChoices = useMemo(() => {
    const familySeen = new Set<string>();
    return availableModels.map(m => {
      const family = modelVersionFamily(m.model_id);
      const familyKey = `${m.provider}::${family}`;
      const isLatest = !familySeen.has(familyKey);
      familySeen.add(familyKey);

      const noKey = !providerReady.has(m.provider);
      const name = m.provider === 'openrouter' ? m.name : friendlyModelName(m.model_id);
      const costStr = m.is_free ? 'Free' : formatCost(m.input_cost_per_token);
      const latestTag = isLatest && family !== m.model_id ? ' · Latest' : '';
      const keyTag = noKey ? ' — no key' : '';

      return {
        value: `${m.provider}::${m.model_id}`,
        provider: m.provider,
        model_id: m.model_id,
        label: `${name}${latestTag} · ${costStr}${keyTag}`,
        isLatestInFamily: isLatest,
        isFree: m.is_free,
        inputCost: m.input_cost_per_token,
      } satisfies ModelChoice;
    });
  }, [availableModels, providerReady]);

  // Free OpenRouter models — always shown
  const freeChoices = useMemo(
    () => allModelChoices.filter(c => c.provider === 'openrouter' && c.isFree),
    [allModelChoices],
  );

  // Paid models — shown only when toggle is on
  const paidChoices = useMemo(
    () => allModelChoices.filter(c => !c.isFree),
    [allModelChoices],
  );

  // Group paid choices by provider for optgroups
  const paidByProvider = useMemo(() => {
    const groups: Record<string, ModelChoice[]> = {};
    paidChoices.forEach(c => {
      const group = c.provider === 'openrouter' ? 'openrouter-paid' : c.provider;
      (groups[group] ??= []).push(c);
    });
    return groups;
  }, [paidChoices]);

  // ── Handlers ─────────────────────────────────────────────────────────────────

  async function handleSaveCmoModel() {
    setSavingCmo(true);
    try {
      if (!cmoModel) {
        await api.deleteBackendOverride('cmo.main').catch(() => {});
        setCmoOverride(null);
      } else {
        const [provider, ...rest] = cmoModel.split('::');
        const model_id = rest.join('::');
        const saved = await api.putBackendOverride('cmo.main', {
          provider, model_id, tool_id: null, modality: 'text', strict: false,
        });
        setCmoOverride(saved);
      }
    } finally {
      setSavingCmo(false);
    }
  }

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

  async function handleDeleteKey(provider: string, brandId?: string | null) {
    if (!confirm(`Remove ${providerLabel(provider)} API key?`)) return;
    await api.deleteKey(provider, brandId ?? undefined).catch(() => {});
    await load();
  }

  async function handleDeleteAuth(provider: string) {
    if (!confirm(`Disconnect ${providerLabel(provider)} login?`)) return;
    await api.deleteProviderAuth(provider).catch(() => {});
    await load();
  }

  async function handleCheck(provider: string) {
    setChecking(provider);
    setCheckResult(prev => { const next = { ...prev }; delete next[provider]; return next; });
    try {
      const result = await api.checkKey(provider);
      setCheckResult(prev => ({ ...prev, [provider]: { status: result.status, message: result.message } }));
      await load();
    } catch (e: unknown) {
      setCheckResult(prev => ({ ...prev, [provider]: { status: 'error', message: (e as Error).message ?? 'check failed' } }));
    } finally {
      setChecking(null);
    }
  }

  async function startLogin(provider: string) {
    setOauthBusy(provider);
    setOauthMessage(null);
    setError(null);
    try {
      const result = await api.startProviderLogin(provider);
      setLoginState(prev => ({ ...prev, [provider]: { login_id: result.login_id, authorize_url: result.login.authorize_url } }));
      setCallbackUrls(prev => ({ ...prev, [provider]: '' }));
    } catch (e: unknown) {
      setError((e as Error).message ?? 'Failed to start login');
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
    setError(null);
    try {
      await api.completeProviderLogin(provider, pending.login_id, callbackUrl);
      setLoginState(prev => { const next = { ...prev }; delete next[provider]; return next; });
      setCallbackUrls(prev => ({ ...prev, [provider]: '' }));
      await load();
      setOauthMessage(`${providerLabel(provider)} connected.`);
    } catch (e: unknown) {
      setError((e as Error).message ?? 'Failed to complete login');
    } finally {
      setOauthBusy(null);
    }
  }

  if (loading) {
    return <div className="admin-page"><div className="loading-full"><span className="spinner" /></div></div>;
  }

  const paidGroupLabels: Record<string, string> = {
    'openrouter-paid': 'OpenRouter — Paid',
    openai: 'OpenAI Direct — Paid',
    gemini: 'Google Gemini — Paid',
    nvidia: 'NVIDIA — Paid',
  };

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">AI Providers</div>
          <div className="admin-page-subtitle">Configure the AI providers that power your CMO and all specialists.</div>
        </div>
      </div>

      {oauthMessage && <div className="alert alert-success" style={{ marginBottom: 16 }}>{oauthMessage}</div>}
      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      {/* ── CMO Brain ───────────────────────────────────────────────────────── */}
      <div className="admin-card" style={{ marginBottom: 16 }}>
        <div className="admin-card-title">CMO Brain</div>

        {/* Status line */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', margin: '10px 0 14px' }}>
          <span style={{ fontSize: 18, color: cmoIsActive ? 'var(--success)' : 'var(--text2)' }}>
            {cmoIsActive ? '●' : '○'}
          </span>
          {cmoIsActive ? (
            <span style={{ fontSize: 14, fontWeight: 600 }}>{cmoCurrentLabel}</span>
          ) : (
            <span style={{ fontSize: 14, color: 'var(--text2)' }}>
              Not running — add an API key below, or Klaroha AI covers it automatically.
            </span>
          )}
          {cmoUsesPlatformKey && cmoIsActive && (
            <span className="badge badge-muted">Klaroha platform</span>
          )}
          {cmoOverride && providerReady.has(cmoOverride.provider) && (
            <span className="badge badge-success">Your key</span>
          )}
        </div>

        {primaryProvider?.last_used_at && (
          <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 14 }}>
            Last run: {fmtDateTime(primaryProvider.last_used_at)}
            {primaryProvider.avg_latency_ms ? ` · Avg speed: ${Math.round(primaryProvider.avg_latency_ms)}ms` : ''}
          </div>
        )}

        {/* Model picker */}
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 14 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Set model</div>
          <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 12 }}>
            Free models via OpenRouter require no key. Paid models need a connected API key.
          </div>

          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 320px' }}>
              <select
                className="select"
                value={cmoModel}
                onChange={e => setCmoModel(e.target.value)}
              >
                <option value="">Auto-select best available</option>

                {freeChoices.length > 0 && (
                  <optgroup label="── Free · OpenRouter ──">
                    {freeChoices.map(c => (
                      <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                  </optgroup>
                )}

                {Object.entries(paidByProvider)
                  .filter(([group]) => group !== 'openrouter-paid')
                  .map(([group, choices]) => (
                    <optgroup key={group} label={`── ${paidGroupLabels[group] ?? group} ──`}>
                      {choices.map(c => (
                        <option key={c.value} value={c.value}>{c.label}</option>
                      ))}
                    </optgroup>
                  ))}
              </select>
            </div>
            <button
              className="btn btn-dark"
              onClick={handleSaveCmoModel}
              disabled={savingCmo || cmoModel === (cmoOverride?.model_id ? `${cmoOverride.provider}::${cmoOverride.model_id}` : '')}
            >
              {savingCmo ? 'Saving…' : cmoModel ? 'Save' : 'Reset to auto-select'}
            </button>
          </div>

          {cmoOverride?.model_id && !providerReady.has(cmoOverride.provider) && (
            <div style={{ marginTop: 8, fontSize: 12, color: 'var(--warning)' }}>
              ⚠ Pinned provider has no connected key — CMO will fall back to auto-select.
            </div>
          )}
        </div>
      </div>

      {/* ── Your API Keys ────────────────────────────────────────────────────── */}
      <div className="admin-card" style={{ marginBottom: 16 }}>
        <div className="admin-card-title">Your API Keys</div>
        <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 14 }}>
          Optional. Add your own API key to use your AI account directly and control costs.
          Without a key, Klaroha's platform AI handles everything automatically.
          Keys are encrypted and never shown after saving.
        </div>

        {/* Existing keys */}
        {keys.length > 0 && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
            {keys.map(key => (
              <div
                key={key.provider}
                style={{ display: 'flex', alignItems: 'center', gap: 8, border: '1px solid var(--border)', borderRadius: 8, padding: '6px 10px', fontSize: 13 }}
              >
                <span style={{ color: 'var(--success)' }}>●</span>
                <span>{providerLabel(key.provider)}</span>
                <span style={{ color: 'var(--text2)', fontSize: 11 }}>· {new Date(key.created_at).toLocaleDateString()}</span>
                <button
                  className="btn btn-ghost btn-sm"
                  style={{ fontSize: 11, padding: '2px 8px', color: 'var(--text2)' }}
                  onClick={() => handleDeleteKey(key.provider, key.brand_id)}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Add key form */}
        <form onSubmit={handleAddKey}>
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(180px, 220px) minmax(200px, 1fr) auto', gap: 10, alignItems: 'end', flexWrap: 'wrap' }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="label">Provider</label>
              <select className="select" value={addProvider} onChange={e => setAddProvider(e.target.value)}>
                <option value="">Select provider…</option>
                <option value="openrouter">OpenRouter (recommended)</option>
                {apiKeyProviders
                  .filter(p => p.provider !== 'openrouter')
                  .map(p => (
                    <option key={p.provider} value={p.provider}>{providerLabel(p.provider)}</option>
                  ))}
              </select>
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="label">API Key</label>
              <input
                className="input"
                type="password"
                value={addKey}
                onChange={e => setAddKey(e.target.value)}
                placeholder={addProvider === 'openrouter' ? 'sk-or-v1-…' : addProvider === 'gemini' ? 'AIza…' : 'sk-…'}
              />
            </div>
            <button
              type="submit"
              className="btn btn-dark"
              disabled={adding || !addProvider || !addKey.trim()}
            >
              {adding ? 'Saving…' : 'Save key'}
            </button>
          </div>

          {addProvider === 'openrouter' && (
            <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text2)' }}>
              OpenRouter covers all AI models (Claude, GPT-4, Gemini, Llama) with one key. Get one at{' '}
              <strong>openrouter.ai/keys</strong>.
            </div>
          )}
          {addProvider === 'gemini' && (
            <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text2)' }}>
              Get a free Gemini API key at <strong>aistudio.google.com/apikey</strong>.
            </div>
          )}
        </form>

        {error && <div className="alert alert-error" style={{ marginTop: 10 }}>{error}</div>}
      </div>

      {/* ── Provider Login Accounts (OAuth) ──────────────────────────────────── */}
      {providers.some(p => p.auth_supported.includes('oauth')) && (
        <div className="admin-card" style={{ marginBottom: 16 }}>
          <div className="admin-card-title">Sign in with an Account</div>
          <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 16 }}>
            Connect via browser login instead of an API key. Useful for ChatGPT accounts and other OAuth-based providers.
          </div>

          {providers.filter(p => p.auth_supported.includes('oauth')).map(prov => {
            const pid = prov.provider;
            const connected = isProviderConnected(prov);
            const pending = loginState[pid];
            const checkRes = checkResult[pid];
            return (
              <div key={pid} style={{ borderTop: '1px solid var(--border)', paddingTop: 14, marginTop: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 14 }}>{providerLabel(pid)}</div>
                    <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 3 }}>
                      {connected
                        ? `Connected${prov.expires_at ? ` · token expires ${new Date(prov.expires_at).toLocaleDateString()}` : ''}`
                        : 'Not connected'}
                    </div>
                    {prov.last_used_at && (
                      <div style={{ fontSize: 12, color: 'var(--text2)' }}>Last used: {fmtDateTime(prov.last_used_at)}</div>
                    )}
                    {checkRes && (
                      <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 4 }}>
                        Check: <strong>{checkRes.status}</strong> — {checkRes.message}
                      </div>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {connected ? (
                      <>
                        <button className="btn btn-ghost btn-sm" onClick={() => handleCheck(pid)} disabled={checking === pid}>
                          {checking === pid ? 'Checking…' : 'Test'}
                        </button>
                        <button className="btn btn-secondary btn-sm" onClick={() => startLogin(pid)} disabled={oauthBusy === pid}>
                          Reconnect
                        </button>
                        <button className="btn btn-danger btn-sm" onClick={() => handleDeleteAuth(pid)}>Disconnect</button>
                      </>
                    ) : (
                      <button className="btn btn-dark btn-sm" onClick={() => startLogin(pid)} disabled={oauthBusy === pid}>
                        {oauthBusy === pid ? 'Starting…' : `Connect ${providerLabel(pid)}`}
                      </button>
                    )}
                  </div>
                </div>

                {/* 3-step OAuth flow */}
                {pending && (
                  <div style={{ marginTop: 16, display: 'grid', gap: 14, background: 'var(--surface2)', padding: 16, borderRadius: 10, border: '1px solid var(--border)' }}>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 4 }}>Step 1 — Open the login page</div>
                      <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 8 }}>
                        Sign into your {providerLabel(pid)} account in a new tab.
                      </div>
                      {pending.authorize_url && (
                        <a className="btn btn-secondary btn-sm" href={pending.authorize_url} target="_blank" rel="noreferrer">
                          Open {providerLabel(pid)} login ↗
                        </a>
                      )}
                    </div>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 4 }}>Step 2 — Copy the callback URL</div>
                      <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 8 }}>
                        After sign-in, the browser redirects to localhost. If the page can't connect, that's expected —
                        copy the full URL from the address bar and paste it here.
                      </div>
                      <textarea
                        className="input"
                        style={{ minHeight: 80, fontFamily: 'var(--mono)', fontSize: 12, resize: 'vertical' }}
                        placeholder="Paste callback URL here…"
                        value={callbackUrls[pid] ?? ''}
                        onChange={e => setCallbackUrls(prev => ({ ...prev, [pid]: e.target.value }))}
                      />
                    </div>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 8 }}>Step 3 — Finish connection</div>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button
                          className="btn btn-dark btn-sm"
                          onClick={() => completeLogin(pid)}
                          disabled={oauthBusy === pid || !(callbackUrls[pid] ?? '').trim()}
                        >
                          {oauthBusy === pid ? 'Connecting…' : 'Finish connection'}
                        </button>
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => setLoginState(prev => { const next = { ...prev }; delete next[pid]; return next; })}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── System / Diagnostics ─────────────────────────────────────────────── */}
      <div style={{ marginBottom: 16 }}>
        <button
          className="btn btn-ghost"
          style={{ fontSize: 13, color: 'var(--text2)' }}
          onClick={() => setShowDiagnostics(v => !v)}
        >
          {showDiagnostics ? '▾' : '▸'} System / Diagnostics
        </button>

        {showDiagnostics && (
          <div className="admin-card" style={{ marginTop: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
              <div>
                <div className="admin-card-title">Provider Health</div>
                <div style={{ fontSize: 12, color: 'var(--text2)' }}>For debugging only — shows all provider connection states.</div>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={() => void load()}>Refresh</button>
            </div>

            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Provider</th>
                    <th style={{ width: 90 }}>Status</th>
                    <th>Last used</th>
                    <th>Last check</th>
                    <th>Models</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {sortedProviders.map(provider => {
                    const connected = isProviderConnected(provider);
                    const verified = checkResult[provider.provider];
                    const expanded = expandedProvider === provider.provider;
                    const isOAuth = provider.auth_mode === 'oauth';
                    const pendingLogin = loginState[provider.provider];
                    return (
                      <Fragment key={provider.provider}>
                        <tr key={provider.provider}>
                          <td>
                            <div style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{providerLabel(provider.provider)}</div>
                            <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 2 }}>{provider.provider}</div>
                          </td>
                          <td>
                            <span
                              title={connectionTitle(provider)}
                              style={{ color: connected ? 'var(--success)' : 'var(--text2)', fontSize: 18 }}
                            >
                              {connected ? '●' : '○'}
                            </span>
                          </td>
                          <td style={{ fontSize: 12, color: 'var(--text2)' }}>{fmtDateTime(provider.last_used_at)}</td>
                          <td style={{ fontSize: 12, color: 'var(--text2)' }}>
                            {fmtDateTime(provider.last_check_at)}
                            {(verified || provider.last_check_message) && (
                              <div style={{ marginTop: 3 }}>
                                {verified ? `${verified.status} — ${verified.message}` : provider.last_check_message}
                              </div>
                            )}
                          </td>
                          <td style={{ fontSize: 12, color: 'var(--text2)', maxWidth: 260 }}>
                            {provider.model_count} · {modelSummary(provider)}
                          </td>
                          <td>
                            <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                              {(connected || provider.has_platform_key) && (
                                <button className="btn btn-ghost btn-sm" onClick={() => handleCheck(provider.provider)} disabled={checking === provider.provider}>
                                  {checking === provider.provider ? '…' : 'Check'}
                                </button>
                              )}
                              {isOAuth && connected && (
                                <>
                                  <button className="btn btn-secondary btn-sm" onClick={() => startLogin(provider.provider)} disabled={oauthBusy === provider.provider}>
                                    Reconnect
                                  </button>
                                  <button className="btn btn-danger btn-sm" onClick={() => handleDeleteAuth(provider.provider)}>Disconnect</button>
                                </>
                              )}
                              {isOAuth && !connected && (
                                <button className="btn btn-dark btn-sm" onClick={() => startLogin(provider.provider)} disabled={oauthBusy === provider.provider}>
                                  {oauthBusy === provider.provider ? 'Starting…' : `Connect ${providerLabel(provider.provider)}`}
                                </button>
                              )}
                              {provider.has_byok_key && !isOAuth && (
                                <button className="btn btn-danger btn-sm" onClick={() => handleDeleteKey(provider.provider)}>Remove key</button>
                              )}
                              <button className="btn btn-secondary btn-sm" onClick={() => setExpandedProvider(expanded ? null : provider.provider)}>
                                {expanded ? 'Hide' : 'Details'}
                              </button>
                            </div>

                            {/* OAuth login flow inline */}
                            {isOAuth && pendingLogin && (
                              <div style={{ marginTop: 12, display: 'grid', gap: 10, textAlign: 'left' }}>
                                <div style={{ fontWeight: 700, fontSize: 12 }}>Step 1 — Open login page</div>
                                {pendingLogin.authorize_url && (
                                  <a className="btn btn-secondary btn-sm" href={pendingLogin.authorize_url} target="_blank" rel="noreferrer">
                                    Open {providerLabel(provider.provider)} Login ↗
                                  </a>
                                )}
                                <div style={{ fontWeight: 700, fontSize: 12 }}>Step 2 — Paste callback URL</div>
                                <textarea
                                  className="input"
                                  style={{ minHeight: 60, fontFamily: 'var(--mono)', fontSize: 11, resize: 'vertical' }}
                                  placeholder="Paste the full callback URL from the address bar…"
                                  value={callbackUrls[provider.provider] ?? ''}
                                  onChange={e => setCallbackUrls(prev => ({ ...prev, [provider.provider]: e.target.value }))}
                                />
                                <div style={{ display: 'flex', gap: 8 }}>
                                  <button
                                    className="btn btn-dark btn-sm"
                                    onClick={() => completeLogin(provider.provider)}
                                    disabled={oauthBusy === provider.provider || !(callbackUrls[provider.provider] ?? '').trim()}
                                  >
                                    {oauthBusy === provider.provider ? 'Connecting…' : 'Finish connection'}
                                  </button>
                                  <button
                                    className="btn btn-ghost btn-sm"
                                    onClick={() => setLoginState(prev => { const next = { ...prev }; delete next[provider.provider]; return next; })}
                                  >
                                    Cancel
                                  </button>
                                </div>
                              </div>
                            )}
                          </td>
                        </tr>

                        {expanded && (
                          <tr>
                            <td colSpan={6} style={{ background: '#fafafa' }}>
                              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
                                <div>
                                  <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 6 }}>Model options</div>
                                  {provider.top_models.length ? provider.top_models.map(model => (
                                    <div key={model.model_id} style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 4 }}>
                                      {model.model_id} · {model.quality_tier} · {model.latency_ms}ms{model.supports_json ? ' · JSON' : ''}
                                    </div>
                                  )) : <div style={{ fontSize: 12, color: 'var(--text2)' }}>No seeded models.</div>}
                                </div>
                                <div>
                                  <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 6 }}>Routing facts</div>
                                  <div style={{ fontSize: 12, color: 'var(--text2)' }}>Platform key: {provider.has_platform_key ? 'available' : 'none'}</div>
                                  <div style={{ fontSize: 12, color: 'var(--text2)' }}>Auth mode: {provider.auth_mode || 'none'}</div>
                                  <div style={{ fontSize: 12, color: 'var(--text2)' }}>
                                    Avg latency: {provider.avg_latency_ms ? `${Math.round(provider.avg_latency_ms)}ms` : 'No runs yet'}
                                  </div>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
