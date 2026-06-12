import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, setApiKey, validateKey } from '../api/client';

export function Auth() {
  const navigate = useNavigate();
  const [mode, setMode]           = useState<'choose' | 'enter'>('choose');
  const [keyInput, setKeyInput]   = useState('');
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState<string | null>(() => {
    const p = new URLSearchParams(window.location.search);
    const err = p.get('error');
    if (err === '1') return 'API key not recognized — check your key and try again.';
    if (err === 'google_denied') return 'Google login was cancelled or denied.';
    if (err === 'unauthorized_email') return 'This Google account is not on the admin whitelist.';
    if (err) return `Login failed: ${err.replace(/_/g, ' ')}`;
    return null;
  });
  const [bootstrapKey, setBootstrapKey] = useState<string | null>(null);

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const key = p.get('key');
    if (!key) return;

    let cancelled = false;
    async function validateUrlKey() {
      setLoading(true);
      setError(null);
      const result = await validateKey(key as string);
      if (cancelled) return;
      setLoading(false);
      // Clean up URL whether valid or invalid so keys are not left in browser history.
      window.history.replaceState({}, '', window.location.pathname);
      if (!result.valid) {
        setError(result.message);
        return;
      }
      setApiKey(key as string);
      navigate('/cmo');
    }
    void validateUrlKey();
    return () => { cancelled = true; };
  }, [navigate]);

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

  function handleGoogleLogin() {
    // Redirect to backend Google login endpoint
    // We use /api prefix because Nginx forwards it to the backend
    window.location.href = '/api/auth/google/login';
  }

  async function handleEnterKey(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = keyInput.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    const result = await validateKey(trimmed);
    setLoading(false);
    if (!result.valid) {
      setError(result.message);
      return;
    }
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
          <div className="auth-choose-mode">
            <button
              className="btn btn-dark"
              style={{ width: '100%', marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
              onClick={handleGoogleLogin}
              disabled={loading}
              id="google-login-button"
            >
              <svg width="18" height="18" viewBox="0 0 18 18">
                <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z" fill="#4285f4"/>
                <path d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34a853"/>
                <path d="M3.964 10.707c-.18-.54-.282-1.117-.282-1.707s.102-1.167.282-1.707V4.961H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.039l3.007-2.332z" fill="#fbbc05"/>
                <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.582C13.463.891 11.426 0 9 0 5.482 0 2.443 2.043.957 4.961L3.964 7.29c.708-2.127 2.692-3.71 5.036-3.71z" fill="#ea4335"/>
              </svg>
              Sign in with Google
            </button>

            <button
              className="btn btn-secondary"
              style={{ width: '100%', marginBottom: 12 }}
              onClick={handleBootstrap}
              disabled={loading}
            >
              {loading ? 'Working…' : 'Bootstrap — create first key'}
            </button>

            <div style={{ textAlign: 'center', fontSize: 12, color: '#999', margin: '8px 0' }}>or</div>

            <button
              className="btn"
              style={{ width: '100%', border: '1px solid #ddd' }}
              onClick={() => setMode('enter')}
            >
              I already have a key
            </button>
          </div>
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
              <button type="submit" className="btn btn-dark" disabled={!keyInput.trim() || loading}>{loading ? 'Checking…' : 'Connect'}</button>
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
