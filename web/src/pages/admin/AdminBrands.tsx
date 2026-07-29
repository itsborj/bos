import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { BrandResponse, OnboardingStatus, WorkspaceResponse } from '../../api/types';

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const d = Math.floor(diff / 86400000);
  if (d < 1) return 'Today';
  if (d === 1) return 'Yesterday';
  if (d < 30) return `${d}d ago`;
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function profileBadge(status: OnboardingStatus | null | undefined, known: boolean): { tone: 'approved' | 'pending'; label: string } {
  if (!known) return { tone: 'pending', label: 'Checking…' };
  if (!status) return { tone: 'pending', label: 'Profile unknown' };
  return status.brand_profile_configured
    ? { tone: 'approved', label: 'Profile set' }
    : { tone: 'pending', label: 'No profile' };
}

const SOCIAL_CALLBACK_KEYS = ['facebook', 'instagram', 'gmail', 'google_calendar', 'google_drive', 'youtube', 'google_business', 'tiktok', 'gemini'] as const;
const DRIVE_RETURN_KEY = 'bos_drive_return_to';
const CONNECT_RETURN_KEY = 'bos_connect_return';

export function AdminBrands() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [brands, setBrands] = useState<BrandResponse[]>([]);
  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null);
  const [brandStatusById, setBrandStatusById] = useState<Record<string, OnboardingStatus | null>>({});
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState('');
  const [saving, setSaving] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    const callbackKey = SOCIAL_CALLBACK_KEYS.find(key => searchParams.has(key));
    if (!callbackKey) return;
    const returnTo = localStorage.getItem(DRIVE_RETURN_KEY) || sessionStorage.getItem(CONNECT_RETURN_KEY);
    localStorage.removeItem(DRIVE_RETURN_KEY);
    sessionStorage.removeItem(CONNECT_RETURN_KEY);
    if (!returnTo || returnTo === '/admin/brands' || returnTo.startsWith('/admin/brands?')) return;
    const [path, existingQuery = ''] = returnTo.split('?', 2);
    const merged = new URLSearchParams(existingQuery);
    searchParams.forEach((value, key) => merged.set(key, value));
    const qs = merged.toString();
    navigate(`${path}${qs ? `?${qs}` : ''}`, { replace: true });
  }, [navigate, searchParams]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      const [brandsRes, ws] = await Promise.all([
        api.getBrands().catch(() => ({ brands: [] as BrandResponse[], total: 0 })),
        api.getWorkspace().catch(() => null),
      ]);
      const brandList = brandsRes.brands ?? [];
      const statusEntries = await Promise.all(brandList.map(async brand => [
        brand.id,
        await api.getOnboardingStatus(brand.id).catch(() => null),
      ] as const));
      if (cancelled) return;
      setBrands(brandList);
      setWorkspace(ws);
      setBrandStatusById(Object.fromEntries(statusEntries));
      setLoading(false);
    }

    load().catch((err: unknown) => {
      if (cancelled) return;
      setError(err instanceof Error ? err.message : 'Could not load brands');
      setLoading(false);
    });

    return () => { cancelled = true; };
  }, []);

  async function handleCreate() {
    const name = newName.trim();
    if (!name) return;
    setSaving(true);
    setError(null);
    try {
      const brand = await api.createBrand({ name, voice: '', tone: '', values: [], domain: '', website_url: '', social_handles: {} });
      navigate('/admin/onboarding', { state: { brand_id: brand.id, brand_name: brand.name } });
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
      const wsBrand = (workspace.brand as any) || {};
      const brand = await api.createBrand({
        name: workspace.name,
        voice: wsBrand.voice || '',
        tone: wsBrand.tone || '',
        values: wsBrand.values || [],
        domain: wsBrand.domain || '',
        website_url: wsBrand.website_url || '',
        social_handles: wsBrand.social_handles || {},
      });
      const result = await api.claimWorkspaceBrand(brand.id);
      setBrands([result.brand]);
      setBrandStatusById(prev => ({ ...prev, [result.brand.id]: null }));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not seed from workspace');
    } finally {
      setSeeding(false);
    }
  }

  async function handleDelete(id: string) {
    const brand = brands.find(b => b.id === id);
    if (!brand) return;
    if (!window.confirm(`Delete brand "${brand.name}"? This cannot be undone.`)) return;
    setDeletingId(id);
    setError(null);
    try {
      await api.deleteBrand(id);
      setBrands(prev => prev.filter(b => b.id !== id));
      setBrandStatusById(prev => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not delete brand');
    } finally {
      setDeletingId(null);
    }
  }

  if (loading) {
    return <div className="admin-page"><div className="loading-full"><span className="spinner" /></div></div>;
  }

  return (
    <div className="admin-page">
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
            <button className="btn btn-ghost btn-sm" onClick={() => { setAdding(false); setNewName(''); }}>
              Cancel
            </button>
          </div>
          {error && <div style={{ fontSize: 12, color: 'var(--error)', marginTop: 8 }}>{error}</div>}
          <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 8 }}>
            Create the brand first, then import a Brand Brief and connect integrations inside the brand.
          </div>
        </div>
      )}

      {brands.length === 0 && !adding ? (
        <div className="admin-card" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>⊞</div>
          <div style={{ fontWeight: 800, fontSize: 16, marginBottom: 6 }}>No brands yet</div>
          <div style={{ color: 'var(--text2)', fontSize: 14, marginBottom: 20 }}>
            Add a brand to start managing profiles, integrations, campaigns, and creative assets for a specific client or business unit.
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
          {error && <div style={{ fontSize: 12, color: 'var(--error)', marginTop: 12 }}>{error}</div>}
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 14 }}>
          {brands.map(brand => {
            const statusKnown = Object.prototype.hasOwnProperty.call(brandStatusById, brand.id);
            const badge = profileBadge(brandStatusById[brand.id], statusKnown);
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
                  <span className={`status-badge ${badge.tone}`}>{badge.label}</span>
                </div>

                <div style={{ marginBottom: 14 }}>
                  {[
                    { key: 'Voice', val: brand.voice || '—' },
                    { key: 'Tone', val: brand.tone || '—' },
                  ].map(({ key, val }) => (
                    <div key={key} style={{ display: 'grid', gridTemplateColumns: '80px 1fr', gap: '3px 12px', margin: '5px 0', fontSize: 12 }}>
                      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text2)', paddingTop: 1 }}>{key}</div>
                      <div style={{ color: 'var(--text)' }}>{val}</div>
                    </div>
                  ))}
                  <div style={{ display: 'grid', gridTemplateColumns: '80px 1fr', gap: '3px 12px', margin: '5px 0', fontSize: 12, alignItems: 'flex-start' }}>
                    <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text2)', paddingTop: 3 }}>Values</div>
                    <div>
                      {brand.values?.length ? (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                          {brand.values.map(v => (
                            <span key={v} style={{ padding: '2px 8px', border: '1px solid var(--brand)', color: 'var(--brand)', borderRadius: 12, fontSize: 11, fontWeight: 500 }}>{v}</span>
                          ))}
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text2)', fontStyle: 'italic' }}>Not set</span>
                      )}
                    </div>
                  </div>
                </div>

                <div style={{ fontSize: 12, color: 'var(--text2)', padding: '10px 0', borderTop: '1px solid var(--border)' }}>
                  Manage integrations, products, audiences, guidelines, and creative assets inside this brand.
                </div>

                <div style={{ display: 'flex', gap: 8, paddingTop: 10, borderTop: '1px solid var(--border)', flexWrap: 'wrap' }}>
                  <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/admin/brands/${brand.id}`)}>Manage</button>
                  <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/admin/brands/${brand.id}?tab=integrations`)}>Integrations</button>
                  <button className="btn btn-ghost btn-sm" onClick={() => navigate('/admin/campaigns', { state: { brand_id: brand.id, brand_name: brand.name } })}>Campaigns</button>
                  <button
                    className="btn btn-danger btn-sm"
                    style={{ marginLeft: 'auto' }}
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

      {error && !adding && brands.length > 0 && (
        <div style={{ fontSize: 12, color: 'var(--error)', marginTop: 12 }}>{error}</div>
      )}
    </div>
  );
}
