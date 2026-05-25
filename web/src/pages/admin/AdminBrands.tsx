import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { BrandResponse, WorkspaceResponse } from '../../api/types';

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const d = Math.floor(diff / 86400000);
  if (d < 1) return 'Today';
  if (d === 1) return 'Yesterday';
  if (d < 30) return `${d}d ago`;
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function profileComplete(brand: BrandResponse): boolean {
  return !!(brand.voice || brand.tone || brand.values?.length);
}

type SocialConn = { id: string; brand_id: string | null; platform: string; page_id: string; page_name: string | null; page_handle: string | null; status: string };

function loadGapiPicker(): Promise<void> {
  return new Promise((resolve, reject) => {
    const w = window as unknown as { gapi?: { load: (n: string, o: { callback: () => void }) => void }; google?: { picker?: unknown } };
    if (w.google?.picker) return resolve();
    const ready = () => w.gapi!.load('picker', { callback: () => resolve() });
    const existing = document.getElementById('gapi-script') as HTMLScriptElement | null;
    if (existing) {
      if (w.gapi) ready(); else existing.addEventListener('load', ready);
      return;
    }
    const s = document.createElement('script');
    s.id = 'gapi-script';
    s.src = 'https://apis.google.com/js/api.js';
    s.onload = ready;
    s.onerror = () => reject(new Error('Failed to load Google API script'));
    document.body.appendChild(s);
  });
}


export function AdminBrands() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [brands, setBrands]             = useState<BrandResponse[]>([]);
  const [workspace, setWorkspace]       = useState<WorkspaceResponse | null>(null);
  const [connections, setConnections]   = useState<SocialConn[]>([]);
  const [loading, setLoading]           = useState(true);
  const [adding, setAdding]             = useState(false);
  const [newName, setNewName]           = useState('');
  const [saving, setSaving]             = useState(false);
  const [seeding, setSeeding]           = useState(false);
  const [error, setError]               = useState<string | null>(null);
  const [deletingId, setDeletingId]     = useState<string | null>(null);
  const [connectingId, setConnectingId] = useState<string | null>(null);
  const [driveRoots, setDriveRoots]     = useState<Record<string, { id: string; name: string }>>({});
  const [toast, setToast]               = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function showToast(msg: string) {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 4000);
  }

  useEffect(() => {
    Promise.all([
      api.getBrands().catch(() => ({ brands: [] as BrandResponse[], total: 0 })),
      api.getWorkspace().catch(() => null),
      api.listSocialConnections().catch(() => [] as SocialConn[]),
    ]).then(([brandsRes, ws, conns]) => {
      setBrands(brandsRes.brands);
      setWorkspace(ws);
      setConnections(conns as SocialConn[]);
    }).finally(() => setLoading(false));
  }, []);

  const [fbPendingSession, setFbPendingSession] = useState<{ sessionId: string; pages: { id: string; name: string }[] } | null>(null);

  // Handle OAuth callback params from installed connector redirects.
  useEffect(() => {
    const gc = searchParams.get('google_calendar');
    if (gc) {
      const reason = searchParams.get('reason') || '';
      const account = searchParams.get('account') || '';
      setSearchParams({});
      if (gc === 'connected') {
        showToast(`✅ Google Calendar "${account}" connected`);
        api.listSocialConnections().then(conns => setConnections(conns)).catch(() => {});
      } else if (gc === 'denied') {
        showToast('Google Calendar connection cancelled');
      } else {
        showToast(`⚠️ Google Calendar connection failed — ${reason.replace(/_/g, ' ')}`);
      }
    }
    const gm = searchParams.get('gmail');
    const brandId = searchParams.get('brand_id');

    if (gm) {
      setSearchParams({}, { replace: true });
      if (gm === 'connected') {
        const account = searchParams.get('account') || 'Gmail account';
        showToast(`✅ Gmail "${account}" connected`);
        if (brandId) api.listSocialConnections(brandId).then(c => setConnections(prev => [...prev.filter(x => x.brand_id !== brandId), ...(c as SocialConn[])])).catch(() => {});
      } else if (gm === 'denied') {
        showToast('Gmail connection cancelled');
      } else {
        const reason = searchParams.get('reason') || 'unknown';
        showToast(`⚠️ Gmail connection failed — ${reason.replace(/_/g, ' ')}`);
      }
    }
    const fb = searchParams.get('facebook');
    if (fb) {
      setSearchParams({}, { replace: true });
      if (fb === 'connected') {
        const account = searchParams.get('account') || 'Facebook page';
        showToast(`✅ Facebook "${account}" connected`);
        api.listSocialConnections().then(conns => setConnections(conns as SocialConn[])).catch(() => {});
      } else if (fb === 'select_page') {
        const sessionId = searchParams.get('session_id') || '';
        if (sessionId) {
          api.facebookPendingPages(sessionId)
            .then(res => setFbPendingSession({ sessionId, pages: res.pages }))
            .catch(() => showToast('⚠️ Could not load Facebook pages — try connecting again'));
        }
      } else if (fb === 'denied') {
        showToast('Facebook connection cancelled');
      } else {
        const reason = searchParams.get('reason') || 'unknown';
        showToast(`⚠️ Facebook connection failed — ${reason.replace(/_/g, ' ')}`);
      }
    }
    const yt = searchParams.get('youtube');
    if (yt) {
      setSearchParams({}, { replace: true });
      if (yt === 'connected') {
        const account = searchParams.get('account') || 'YouTube channel';
        showToast(`✅ YouTube "${account}" connected`);
        api.listSocialConnections().then(conns => setConnections(conns as SocialConn[])).catch(() => {});
      } else if (yt === 'denied') {
        showToast('YouTube connection cancelled');
      } else {
        const reason = searchParams.get('reason') || 'unknown';
        showToast(`⚠️ YouTube connection failed — ${reason.replace(/_/g, ' ')}`);
      }
    }
    const tt = searchParams.get('tiktok');
    if (tt) {
      setSearchParams({}, { replace: true });
      if (tt === 'connected') {
        const account = searchParams.get('account') || 'TikTok account';
        showToast(`✅ TikTok "${account}" connected`);
        api.listSocialConnections().then(conns => setConnections(conns as SocialConn[])).catch(() => {});
      } else if (tt === 'denied') {
        showToast('TikTok connection cancelled');
      } else {
        const reason = searchParams.get('reason') || 'unknown';
        showToast(`⚠️ TikTok connection failed — ${reason.replace(/_/g, ' ')}`);
      }
    }
    const gd = searchParams.get('google_drive');
    if (gd) {
      setSearchParams({}, { replace: true });
      if (gd === 'connected') {
        const account = searchParams.get('account') || 'Google Drive';
        showToast(`✅ Google Drive "${account}" connected`);
        api.listSocialConnections().then(conns => setConnections(conns as SocialConn[])).catch(() => {});
      } else if (gd === 'denied') {
        showToast('Google Drive connection cancelled');
      } else {
        const reason = searchParams.get('reason') || 'unknown';
        showToast(`⚠️ Google Drive connection failed — ${reason.replace(/_/g, ' ')}`);
      }
    }
  }, []);

  async function handleCreate() {
    const name = newName.trim();
    if (!name) return;
    setSaving(true);
    setError(null);
    try {
      const brand = await api.createBrand({ name, voice: '', tone: '', values: [], domain: '', website_url: '', social_handles: {} });
      setBrands(prev => [brand, ...prev]);
      setNewName('');
      setAdding(false);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not create brand');
    } finally {
      setSaving(false);
    }
  }

  async function handleSeedFromWorkspace() {
    if (!workspace) return;
    setSeeding(true);
    setError(null);
    try {
      const ws_brand = (workspace.brand as any) || {};
      const brand = await api.createBrand({
        name: workspace.name,
        voice: ws_brand.voice || '',
        tone: ws_brand.tone || '',
        values: ws_brand.values || [],
        domain: ws_brand.domain || '',
        website_url: ws_brand.website_url || '',
        social_handles: ws_brand.social_handles || {},
      });
      const result = await api.claimWorkspaceBrand(brand.id);
      setBrands([result.brand]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not seed from workspace');
    } finally {
      setSeeding(false);
    }
  }

  async function handleConnectFacebook(brandId: string) {
    setConnectingId(brandId + '_facebook');
    try {
      const res = await api.startSocialConnect(brandId, 'facebook');
      window.location.href = res.authorize_url;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'check META_APP_ID in settings';
      showToast(`⚠️ Could not start Facebook connect — ${msg}`);
    } finally {
      setConnectingId(null);
    }
  }

  async function handleDisconnectFacebook(brandId: string) {
    const conn = connections.find(c => c.brand_id === brandId && c.platform === 'facebook');
    if (!conn) return;
    if (!window.confirm(`Disconnect Facebook page "${conn.page_name}"?`)) return;
    try {
      await api.disconnectSocial(conn.id);
      setConnections(prev => prev.filter(c => c.id !== conn.id));
      showToast('Facebook page disconnected');
    } catch {
      showToast('⚠️ Could not disconnect — try again');
    }
  }

  async function handleSelectFacebookPage(pageId: string) {
    if (!fbPendingSession) return;
    try {
      await api.facebookSelectPage(fbPendingSession.sessionId, pageId);
      const page = fbPendingSession.pages.find(p => p.id === pageId);
      setFbPendingSession(null);
      showToast(`✅ Facebook "${page?.name || pageId}" connected`);
      api.listSocialConnections().then(conns => setConnections(conns as SocialConn[])).catch(() => {});
    } catch {
      showToast('⚠️ Could not connect page — try again');
    }
  }

  async function handleConnectGmail(brandId: string) {
    setConnectingId(brandId + '_gmail');
    try {
      const res = await api.startSocialConnect(brandId, 'gmail');
      window.location.href = res.authorize_url;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'check GOOGLE_CLIENT_ID in settings';
      showToast(`⚠️ Could not start Gmail connect — ${msg}`);
    } finally {
      setConnectingId(null);
    }
  }

  async function handleConnectYouTube(brandId: string) {
    setConnectingId(brandId + '_youtube');
    try {
      const res = await api.startSocialConnect(brandId, 'youtube');
      window.location.href = res.authorize_url;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'check Google OAuth settings';
      showToast(`⚠️ Could not start YouTube connect — ${msg}`);
    } finally {
      setConnectingId(null);
    }
  }

  async function handleDisconnectYouTube(brandId: string) {
    const conn = connections.find(c => c.brand_id === brandId && c.platform === 'youtube');
    if (!conn) return;
    if (!window.confirm(`Disconnect YouTube channel "${conn.page_name}"?`)) return;
    try {
      await api.disconnectSocial(conn.id);
      setConnections(prev => prev.filter(c => c.id !== conn.id));
      showToast('YouTube channel disconnected');
    } catch {
      showToast('⚠️ Could not disconnect — try again');
    }
  }

  async function handleConnectTikTok(brandId: string) {
    setConnectingId(brandId + '_tiktok');
    try {
      const res = await api.startSocialConnect(brandId, 'tiktok');
      window.location.href = res.authorize_url;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'check TikTok OAuth settings';
      showToast(`⚠️ Could not start TikTok connect — ${msg}`);
    } finally {
      setConnectingId(null);
    }
  }

  async function handleConnectDrive(brandId: string) {
    setConnectingId(brandId + '_google_drive');
    try {
      const res = await api.startSocialConnect(brandId, 'google_drive');
      window.location.href = res.authorize_url;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'check Google OAuth settings';
      showToast(`⚠️ Could not start Google Drive connect — ${msg}`);
    } finally {
      setConnectingId(null);
    }
  }

  async function handleDisconnectTikTok(brandId: string) {
    const conn = connections.find(c => c.brand_id === brandId && c.platform === 'tiktok');
    if (!conn) return;
    if (!window.confirm(`Disconnect TikTok account "${conn.page_name}"?`)) return;
    try {
      await api.disconnectSocial(conn.id);
      setConnections(prev => prev.filter(c => c.id !== conn.id));
      showToast('TikTok account disconnected');
    } catch {
      showToast('⚠️ Could not disconnect — try again');
    }
  }

  async function handleDisconnectDrive(brandId: string) {
    const conn = connections.find(c => c.brand_id === brandId && c.platform === 'google_drive');
    if (!conn) return;
    if (!window.confirm(`Disconnect Google Drive "${conn.page_name}"?`)) return;
    try {
      await api.disconnectSocial(conn.id);
      setConnections(prev => prev.filter(c => c.id !== conn.id));
      setDriveRoots(prev => { const next = { ...prev }; delete next[brandId]; return next; });
      showToast('Google Drive disconnected');
    } catch {
      showToast('⚠️ Could not disconnect — try again');
    }
  }

  async function handleChooseDriveFolder(brandId: string) {
    try {
      const cfg = await api.getDrivePickerConfig(brandId);
      await loadGapiPicker();
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const g = (window as any).google;
      const view = new g.picker.DocsView(g.picker.ViewId.FOLDERS)
        .setSelectFolderEnabled(true)
        .setMimeTypes('application/vnd.google-apps.folder');
      const picker = new g.picker.PickerBuilder()
        .setOAuthToken(cfg.access_token)
        .setDeveloperKey(cfg.api_key)
        .setAppId(cfg.app_id)
        .addView(view)
        .enableFeature(g.picker.Feature.SUPPORT_DRIVES)
        .setTitle("Choose the root folder for this brand's assets")
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        .setCallback(async (data: any) => {
          if (data.action !== g.picker.Action.PICKED) return;
          const doc = data.docs?.[0];
          if (!doc) return;
          try {
            await api.setDriveRoot(brandId, doc.id, doc.name, doc.url || undefined);
            setDriveRoots(prev => ({ ...prev, [brandId]: { id: doc.id, name: doc.name } }));
            showToast(`✅ Asset root set to "${doc.name}"`);
          } catch {
            showToast('⚠️ Could not save folder selection — try again');
          }
        })
        .build();
      picker.setVisible(true);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'check GOOGLE_PICKER_API_KEY + Picker API enabled';
      showToast(`⚠️ Could not open folder picker — ${msg}`);
    }
  }

  async function handleDisconnectGmail(brandId: string) {
    const conn = connections.find(c => c.brand_id === brandId && c.platform === 'gmail');
    if (!conn) return;
    if (!window.confirm(`Disconnect Gmail account "${conn.page_name}"?`)) return;
    try {
      await api.disconnectSocial(conn.id);
      setConnections(prev => prev.filter(c => c.id !== conn.id));
      showToast('Gmail account disconnected');
    } catch {
      showToast('⚠️ Could not disconnect — try again');
    }
  }

  async function handleConnectCalendar(brandId: string) {
    setConnectingId(brandId + '_calendar');
    try {
      const res = await api.startSocialConnect(brandId, 'google_calendar');
      window.location.href = res.authorize_url;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'check GOOGLE_CLIENT_ID in settings';
      showToast(`⚠️ Could not start Calendar connect — ${msg}`);
    } finally {
      setConnectingId(null);
    }
  }

  async function handleDisconnectCalendar(brandId: string) {
    const conn = connections.find(c => c.brand_id === brandId && c.platform === 'google_calendar');
    if (!conn) return;
    if (!window.confirm(`Disconnect Google Calendar account "${conn.page_name}"?`)) return;
    try {
      await api.disconnectSocial(conn.id);
      setConnections(prev => prev.filter(c => c.id !== conn.id));
      showToast('Google Calendar disconnected');
    } catch {
      showToast('⚠️ Could not disconnect — try again');
    }
  }

  async function handleDelete(id: string) {
    if (!window.confirm('Delete this brand? All associated data will be unlinked.')) return;
    setDeletingId(id);
    try {
      await api.deleteBrand(id);
      setBrands(prev => prev.filter(b => b.id !== id));
    } catch {
      // deletion failed silently; brand stays in list
    } finally {
      setDeletingId(null);
    }
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
          <div className="admin-page-title">Brands</div>
          <div className="admin-page-subtitle">Each brand is a distinct business or client with its own profile, products, audiences, and campaigns.</div>
        </div>
        <button className="btn btn-dark btn-sm" onClick={() => { setAdding(true); setError(null); }}>
          + New Brand
        </button>
      </div>

      {adding && (
        <div className="admin-card" style={{ marginBottom: 20, padding: '18px 20px' }}>
          <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 12 }}>New Brand</div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <input
              className="input"
              placeholder="Brand name (e.g. Klaroha, Client A)"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleCreate(); if (e.key === 'Escape') setAdding(false); }}
              autoFocus
              style={{ flex: 1 }}
            />
            <button className="btn btn-dark btn-sm" onClick={handleCreate} disabled={saving || !newName.trim()}>
              {saving ? '…' : 'Create'}
            </button>
            <button className="btn btn-secondary btn-sm" onClick={() => { setAdding(false); setNewName(''); }}>
              Cancel
            </button>
          </div>
          {error && <div style={{ fontSize: 12, color: '#dc2626', marginTop: 8 }}>{error}</div>}
          <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 8 }}>
            Create the brand first, then import a Brand Brief to set voice, tone, products, and audiences.
          </div>
        </div>
      )}

      {fbPendingSession && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="admin-card" style={{ width: 360, margin: 0, padding: 24 }}>
            <div style={{ fontWeight: 800, fontSize: 15, marginBottom: 6 }}>Select a Facebook Page</div>
            <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 16 }}>
              Your account manages multiple pages. Choose which one to connect to this brand.
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {fbPendingSession.pages.map(p => (
                <button
                  key={p.id}
                  className="btn btn-secondary"
                  style={{ justifyContent: 'flex-start', textAlign: 'left' }}
                  onClick={() => handleSelectFacebookPage(p.id)}
                >
                  {p.name}
                </button>
              ))}
            </div>
            <button className="btn btn-ghost btn-sm" style={{ marginTop: 12 }} onClick={() => setFbPendingSession(null)}>Cancel</button>
          </div>
        </div>
      )}

      {brands.length === 0 && !adding ? (
        <div className="admin-card" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>⊞</div>
          <div style={{ fontWeight: 800, fontSize: 16, marginBottom: 6 }}>No brands yet</div>
          <div style={{ color: 'var(--text2)', fontSize: 14, marginBottom: 20 }}>
            Add a brand to start managing campaigns, audiences, and content for a specific client or business unit.
          </div>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
            <button className="btn btn-dark" onClick={() => setAdding(true)}>+ New Brand</button>
            {workspace && (
              <button
                className="btn btn-secondary"
                onClick={handleSeedFromWorkspace}
                disabled={seeding}
                title={`Create "${workspace.name}" brand from existing workspace profile and link all current data`}
              >
                {seeding ? 'Setting up…' : `Import "${workspace.name}" from workspace`}
              </button>
            )}
          </div>
          {error && <div style={{ fontSize: 12, color: '#dc2626', marginTop: 12 }}>{error}</div>}
          <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 16 }}>
            "Import from workspace" promotes your existing brand profile, products, audiences, and documents into a named brand.
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 14 }}>
          {brands.map(brand => {
            const complete = profileComplete(brand);
            return (
              <div key={brand.id} className="admin-card" style={{ margin: 0, display: 'flex', flexDirection: 'column', gap: 0 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 10 }}>
                  <div>
                    <div
                      role="button"
                      tabIndex={0}
                      style={{ fontWeight: 800, fontSize: 16, cursor: 'pointer' }}
                      onClick={() => navigate(`/admin/brands/${brand.id}`)}
                      onKeyDown={e => e.key === 'Enter' && navigate(`/admin/brands/${brand.id}`)}
                    >{brand.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 2 }}>
                      Added {timeAgo(brand.created_at)}
                      {brand.domain && <> · {brand.domain}</>}
                    </div>
                  </div>
                  <span className={`status-badge ${complete ? 'approved' : 'pending'}`}>
                    {complete ? 'Profile set' : 'No profile'}
                  </span>
                </div>

                {complete ? (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14, fontSize: 13 }}>
                    {brand.voice && (
                      <div>
                        <div className="label" style={{ marginBottom: 2 }}>Voice</div>
                        <div style={{ color: 'var(--text2)' }}>{brand.voice}</div>
                      </div>
                    )}
                    {brand.tone && (
                      <div>
                        <div className="label" style={{ marginBottom: 2 }}>Tone</div>
                        <div style={{ color: 'var(--text2)' }}>{brand.tone}</div>
                      </div>
                    )}
                    {brand.values?.length > 0 && (
                      <div style={{ gridColumn: '1 / -1' }}>
                        <div className="label" style={{ marginBottom: 4 }}>Values</div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                          {brand.values.map(v => (
                            <span key={v} className="bos-module-chip">{v}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 14, fontStyle: 'italic' }}>
                    Import a Brand Brief to set voice, tone, products, and audiences.
                  </div>
                )}

                {(() => {
                  const gmConn = connections.find(c => c.brand_id === brand.id && c.platform === 'gmail');
                  const gcConn = connections.find(c => c.brand_id === brand.id && c.platform === 'google_calendar');
                  const fbConn = connections.find(c => c.brand_id === brand.id && c.platform === 'facebook');
                  const ytConn = connections.find(c => c.brand_id === brand.id && c.platform === 'youtube');
                  const ttConn = connections.find(c => c.brand_id === brand.id && c.platform === 'tiktok');
                  const gdConn = connections.find(c => c.brand_id === brand.id && c.platform === 'google_drive');
                  return (
                    <>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderTop: '1px solid var(--border)', marginTop: 8 }}>
                        <span style={{ fontSize: 13 }}>📘</span>
                        {fbConn ? (
                          <>
                            <span style={{ fontSize: 12, fontWeight: 600, flex: 1 }}>{fbConn.page_name || fbConn.page_id}</span>
                            <span className="status-badge approved" style={{ fontSize: 10 }}>Connected</span>
                            <button className="btn btn-ghost btn-sm" style={{ fontSize: 11, padding: '2px 8px' }} onClick={() => handleDisconnectFacebook(brand.id)}>Disconnect</button>
                          </>
                        ) : (
                          <>
                            <span style={{ fontSize: 12, color: 'var(--text2)', flex: 1 }}>Facebook Page</span>
                            <button
                              className="btn btn-secondary btn-sm"
                              style={{ fontSize: 11, padding: '3px 10px' }}
                              onClick={() => handleConnectFacebook(brand.id)}
                              disabled={connectingId === brand.id + '_facebook'}
                            >
                              {connectingId === brand.id + '_facebook' ? 'Redirecting…' : 'Connect'}
                            </button>
                          </>
                        )}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderTop: '1px solid var(--border)', marginTop: 8 }}>
                        <span style={{ fontSize: 13 }}>▶️</span>
                        {ytConn ? (
                          <>
                            <span style={{ fontSize: 12, fontWeight: 600, flex: 1 }}>{ytConn.page_name || ytConn.page_id}</span>
                            <span className="status-badge approved" style={{ fontSize: 10 }}>Connected</span>
                            <button className="btn btn-ghost btn-sm" style={{ fontSize: 11, padding: '2px 8px' }} onClick={() => handleDisconnectYouTube(brand.id)}>Disconnect</button>
                          </>
                        ) : (
                          <>
                            <span style={{ fontSize: 12, color: 'var(--text2)', flex: 1 }}>YouTube</span>
                            <button
                              className="btn btn-secondary btn-sm"
                              style={{ fontSize: 11, padding: '3px 10px' }}
                              onClick={() => handleConnectYouTube(brand.id)}
                              disabled={connectingId === brand.id + '_youtube'}
                            >
                              {connectingId === brand.id + '_youtube' ? 'Redirecting…' : 'Connect'}
                            </button>
                          </>
                        )}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderTop: '1px solid var(--border)', marginTop: 8 }}>
                        <span style={{ fontSize: 13 }}>🎵</span>
                        {ttConn ? (
                          <>
                            <span style={{ fontSize: 12, fontWeight: 600, flex: 1 }}>{ttConn.page_name || ttConn.page_id}</span>
                            <span className="status-badge approved" style={{ fontSize: 10 }}>Connected</span>
                            <button className="btn btn-ghost btn-sm" style={{ fontSize: 11, padding: '2px 8px' }} onClick={() => handleDisconnectTikTok(brand.id)}>Disconnect</button>
                          </>
                        ) : (
                          <>
                            <span style={{ fontSize: 12, color: 'var(--text2)', flex: 1 }}>TikTok</span>
                            <button
                              className="btn btn-secondary btn-sm"
                              style={{ fontSize: 11, padding: '3px 10px' }}
                              onClick={() => handleConnectTikTok(brand.id)}
                              disabled={connectingId === brand.id + '_tiktok'}
                            >
                              {connectingId === brand.id + '_tiktok' ? 'Redirecting…' : 'Connect'}
                            </button>
                          </>
                        )}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderTop: '1px solid var(--border)', marginTop: 8 }}>
                        <span style={{ fontSize: 13 }}>🗂️</span>
                        {gdConn ? (
                          <>
                            <span style={{ fontSize: 12, fontWeight: 600, flex: 1 }}>
                              {driveRoots[brand.id]?.name ? `Root: ${driveRoots[brand.id].name}` : (gdConn.page_name || gdConn.page_id)}
                            </span>
                            <span className="status-badge approved" style={{ fontSize: 10 }}>Connected</span>
                            <button className="btn btn-secondary btn-sm" style={{ fontSize: 11, padding: '2px 8px' }} onClick={() => handleChooseDriveFolder(brand.id)}>
                              {driveRoots[brand.id] ? 'Change folder' : 'Choose folder'}
                            </button>
                            <button className="btn btn-ghost btn-sm" style={{ fontSize: 11, padding: '2px 8px' }} onClick={() => handleDisconnectDrive(brand.id)}>Disconnect</button>
                          </>
                        ) : (
                          <>
                            <span style={{ fontSize: 12, color: 'var(--text2)', flex: 1 }}>Google Drive</span>
                            <button
                              className="btn btn-secondary btn-sm"
                              style={{ fontSize: 11, padding: '3px 10px' }}
                              onClick={() => handleConnectDrive(brand.id)}
                              disabled={connectingId === brand.id + '_google_drive'}
                            >
                              {connectingId === brand.id + '_google_drive' ? 'Redirecting…' : 'Connect'}
                            </button>
                          </>
                        )}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderTop: '1px solid var(--border)', marginTop: 8 }}>
                        <span style={{ fontSize: 13 }}>✉️</span>
                        {gmConn ? (
                          <>
                            <span style={{ fontSize: 12, fontWeight: 600, flex: 1 }}>
                              {gmConn.page_name || gmConn.page_id}
                            </span>
                            <span className="status-badge approved" style={{ fontSize: 10 }}>Connected</span>
                            <button className="btn btn-ghost btn-sm" style={{ fontSize: 11, padding: '2px 8px' }} onClick={() => handleDisconnectGmail(brand.id)}>
                              Disconnect
                            </button>
                          </>
                        ) : (
                          <>
                            <span style={{ fontSize: 12, color: 'var(--text2)', flex: 1 }}>Gmail</span>
                            <button
                              className="btn btn-secondary btn-sm"
                              style={{ fontSize: 11, padding: '3px 10px' }}
                              onClick={() => handleConnectGmail(brand.id)}
                              disabled={connectingId === brand.id + '_gmail'}
                            >
                              {connectingId === brand.id + '_gmail' ? 'Redirecting…' : 'Connect'}
                            </button>
                          </>
                        )}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderTop: '1px solid var(--border)' }}>
                        <span style={{ fontSize: 13 }}>📅</span>
                        {gcConn ? (
                          <>
                            <span style={{ fontSize: 12, fontWeight: 600, flex: 1 }}>
                              {gcConn.page_name || gcConn.page_id}
                            </span>
                            <span className="status-badge approved" style={{ fontSize: 10 }}>Connected</span>
                            <button className="btn btn-ghost btn-sm" style={{ fontSize: 11, padding: '2px 8px' }} onClick={() => handleDisconnectCalendar(brand.id)}>
                              Disconnect
                            </button>
                          </>
                        ) : (
                          <>
                            <span style={{ fontSize: 12, color: 'var(--text2)', flex: 1 }}>Google Calendar</span>
                            <button
                              className="btn btn-secondary btn-sm"
                              style={{ fontSize: 11, padding: '3px 10px' }}
                              onClick={() => handleConnectCalendar(brand.id)}
                              disabled={connectingId === brand.id + '_calendar'}
                            >
                              {connectingId === brand.id + '_calendar' ? 'Redirecting…' : 'Connect'}
                            </button>
                          </>
                        )}
                      </div>
                    </>
                  );
                })()}

                <div style={{ display: 'flex', gap: 8, paddingTop: 10, borderTop: '1px solid var(--border)' }}>
                  <button
                    className="btn btn-dark btn-sm"
                    onClick={() => navigate(`/admin/brands/${brand.id}`)}
                  >
                    Manage
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => navigate('/admin/campaigns', { state: { brand_id: brand.id, brand_name: brand.name } })}
                  >
                    Campaigns
                  </button>
                  <button
                    className="btn btn-ghost btn-sm"
                    style={{ marginLeft: 'auto', color: '#dc2626' }}
                    onClick={() => handleDelete(brand.id)}
                    disabled={deletingId === brand.id}
                  >
                    {deletingId === brand.id ? '…' : 'Delete'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
