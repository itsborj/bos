import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, setApiKey } from '../api/client';

export function Auth() {
  const navigate = useNavigate();
  const [mode, setMode]           = useState<'choose' | 'enter'>('choose');
  const [keyInput, setKeyInput]   = useState('');
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState<string | null>(() => {
    const p = new URLSearchParams(window.location.search);
    return p.get('error') === '1' ? 'API key not recognized — check your key and try again.' : null;
  });
  const [bootstrapKey, setBootstrapKey] = useState<string | null>(null);

  async function handleBootstrap() {
    setLoading(true);
    setError(null);
    try {
      const result = await api.bootstrap();
      setBootstrapKey(result.key);
      setApiKey(result.key);
    } catch (e: unknown) {
      setError((e as Error).message ?? 'Bootstrap failed');
    } finally {
      setLoading(false);
    }
  }

  function handleEnterKey(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = keyInput.trim();
    if (!trimmed) return;
    setApiKey(trimmed);
    navigate('/cmo');
  }

  if (bootstrapKey) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <div className="auth-logo">
            <div className="logo-mark"><span className="logo-inner">K</span></div>
            <span className="auth-title">Key created</span>
          </div>
          <p className="auth-sub">Save this key — it will not be shown again.</p>
          <div style={{ background: '#fafafa', border: '1px solid #ddd', borderRadius: 6, padding: '10px 12px', fontFamily: 'monospace', fontSize: 12, wordBreak: 'break-all', marginBottom: 14 }}>
            {bootstrapKey}
          </div>
          <button className="btn btn-dark" style={{ width: '100%' }} onClick={() => navigate('/cmo')}>
            Continue to BOS →
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <div className="logo-mark"><span className="logo-inner">K</span></div>
          <div>
            <div className="auth-title">Klaroha</div>
          </div>
        </div>

        {error && <div className="auth-error">{error}</div>}

        {mode === 'choose' && (
          <>
            <button
              className="btn btn-dark"
              style={{ width: '100%', marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
              onClick={handleBootstrap}
              disabled={loading}
            >
              {loading ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Working…</> : 'Bootstrap — create first key'}
            </button>

            <div style={{ textAlign: 'center', fontSize: 12, color: '#999', margin: '8px 0' }}>or</div>

            <button
              className="btn btn-secondary"
              style={{ width: '100%' }}
              onClick={() => setMode('enter')}
            >
              I already have a key
            </button>
          </>
        )}

        {mode === 'enter' && (
          <form onSubmit={handleEnterKey}>
            <div className="form-group">
              <label className="label" htmlFor="api-key">API Key</label>
              <input
                id="api-key"
                className="input"
                type="password"
                placeholder="bos_…"
                value={keyInput}
                onChange={e => setKeyInput(e.target.value)}
                autoFocus
              />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="submit" className="btn btn-dark" disabled={!keyInput.trim()}>Connect</button>
              <button type="button" className="btn" onClick={() => { setMode('choose'); setError(null); }}>Back</button>
            </div>
          </form>
        )}

        <div style={{ marginTop: 20, fontSize: 11, color: '#bbb', textAlign: 'center' }}>
          One workspace · One command · Full control
        </div>
      </div>
    </div>
  );
}
