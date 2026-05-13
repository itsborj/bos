import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { AudienceOut, BrandResponse, ProductOut, WorkspaceDocument, WorkspaceResponse } from '../../api/types';

type Tab = 'profile' | 'products' | 'audiences' | 'guidelines' | 'brand-kit';

// ── Profile tab ───────────────────────────────────────────────────────────────

function ProfileTab({ brand, onUpdate }: { brand: BrandResponse; onUpdate: (b: BrandResponse) => void }) {
  const navigate = useNavigate();
  const [voice, setVoice]       = useState(brand.voice || '');
  const [tone, setTone]         = useState(brand.tone || '');
  const [valuesRaw, setValuesRaw] = useState((brand.values || []).join(', '));
  const [domain, setDomain]     = useState(brand.domain || '');
  const [websiteUrl, setWebsiteUrl] = useState(brand.website_url || '');
  const [saving, setSaving]     = useState(false);
  const [saved, setSaved]       = useState(false);
  const [error, setError]       = useState<string | null>(null);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateBrand(brand.id, {
        voice: voice || undefined,
        tone: tone || undefined,
        values: valuesRaw ? valuesRaw.split(',').map(v => v.trim()).filter(Boolean) : [],
        domain: domain || undefined,
        website_url: websiteUrl || undefined,
      });
      onUpdate(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not save profile');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ maxWidth: 560 }}>
      <form onSubmit={handleSave}>
        <div className="form-group">
          <label className="label" htmlFor="bd-voice">
            Brand Voice <span className="label-hint">how you sound</span>
          </label>
          <input id="bd-voice" className="input" value={voice} onChange={e => setVoice(e.target.value)} placeholder="e.g. authoritative and direct" />
        </div>
        <div className="form-group">
          <label className="label" htmlFor="bd-tone">
            Tone <span className="label-hint">emotional register</span>
          </label>
          <input id="bd-tone" className="input" value={tone} onChange={e => setTone(e.target.value)} placeholder="e.g. professional with warmth" />
        </div>
        <div className="form-group">
          <label className="label" htmlFor="bd-values">
            Brand Values <span className="label-hint">comma-separated</span>
          </label>
          <input id="bd-values" className="input" value={valuesRaw} onChange={e => setValuesRaw(e.target.value)} placeholder="transparency, innovation, reliability" />
        </div>
        <div className="form-group">
          <label className="label" htmlFor="bd-domain">
            Domain <span className="label-hint">e.g. klaroha.com</span>
          </label>
          <input id="bd-domain" className="input" value={domain} onChange={e => setDomain(e.target.value)} placeholder="brand.com" />
        </div>
        <div className="form-group">
          <label className="label" htmlFor="bd-website">
            Website URL
          </label>
          <input id="bd-website" className="input" value={websiteUrl} onChange={e => setWebsiteUrl(e.target.value)} placeholder="https://brand.com" />
        </div>
        {error && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 12 }}>{error}</div>}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <button type="submit" className="btn btn-dark" disabled={saving}>
            {saving ? 'Saving…' : saved ? '✓ Saved' : 'Save Profile'}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate('/admin/onboarding', { state: { brand_id: brand.id, brand_name: brand.name } })}
          >
            Update via Brand Brief →
          </button>
        </div>
      </form>
      <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 16 }}>
        For a full brief import (products, audiences, guidelines) use the Import Brief workflow.
      </div>
    </div>
  );
}

// ── Products tab ──────────────────────────────────────────────────────────────

function ProductsTab({ products, brandId, brandName }: { products: ProductOut[]; brandId: string; brandName: string }) {
  const navigate = useNavigate();
  const brandProducts = products.filter(p => p.brand_id === brandId);

  if (brandProducts.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '32px 0' }}>
        <div style={{ fontSize: 14, color: 'var(--text2)', marginBottom: 16 }}>
          No products linked to {brandName} yet.
        </div>
        <button
          className="btn btn-dark"
          onClick={() => navigate('/admin/onboarding', { state: { brand_id: brandId, brand_name: brandName } })}
        >
          Import via Brand Brief →
        </button>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 14 }}>
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => navigate('/admin/onboarding', { state: { brand_id: brandId, brand_name: brandName } })}
        >
          Update via Brand Brief →
        </button>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {brandProducts.map(p => (
          <div key={p.id} className="card">
            <div style={{ fontWeight: 700 }}>{p.name}</div>
            {p.tagline && <div style={{ fontSize: 13, color: 'var(--text2)', marginTop: 2 }}>{p.tagline}</div>}
            {p.benefits.length > 0 && (
              <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 4 }}>{p.benefits.join(' · ')}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Audiences tab ─────────────────────────────────────────────────────────────

function AudiencesTab({ audiences, brandId, brandName }: { audiences: AudienceOut[]; brandId: string; brandName: string }) {
  const navigate = useNavigate();
  const brandAudiences = audiences.filter(a => a.brand_id === brandId);

  if (brandAudiences.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '32px 0' }}>
        <div style={{ fontSize: 14, color: 'var(--text2)', marginBottom: 16 }}>
          No audiences linked to {brandName} yet.
        </div>
        <button
          className="btn btn-dark"
          onClick={() => navigate('/admin/onboarding', { state: { brand_id: brandId, brand_name: brandName } })}
        >
          Import via Brand Brief →
        </button>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 14 }}>
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => navigate('/admin/onboarding', { state: { brand_id: brandId, brand_name: brandName } })}
        >
          Update via Brand Brief →
        </button>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {brandAudiences.map(a => (
          <div key={a.id} className="card">
            <div style={{ fontWeight: 700 }}>{a.name}</div>
            {a.demographics && <div style={{ fontSize: 13, color: 'var(--text2)', marginTop: 2 }}>{a.demographics}</div>}
            {a.pain_points.length > 0 && (
              <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 4 }}>Pain: {a.pain_points.join(' · ')}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Guidelines tab ────────────────────────────────────────────────────────────

function GuidelinesTab({ brandId }: { brandId: string }) {
  const navigate = useNavigate();
  const [doc, setDoc]         = useState<WorkspaceDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft]     = useState('');
  const [saving, setSaving]   = useState(false);
  const [copied, setCopied]   = useState(false);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    api.getDocuments({ doc_type: 'brand_guideline', brand_id: brandId })
      .then(docs => {
        const latest = docs[0] ?? null;
        setDoc(latest);
        setDraft(latest?.content_markdown ?? '');
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Could not load guidelines'))
      .finally(() => setLoading(false));
  }, [brandId]);

  if (loading) return <div className="loading-full"><span className="spinner" /></div>;

  if (!doc) {
    return (
      <div style={{ textAlign: 'center', padding: '32px 0' }}>
        <div style={{ fontSize: 14, color: 'var(--text2)', marginBottom: 16 }}>
          No Brand Guidelines document yet.
        </div>
        <button className="btn btn-dark" onClick={() => navigate('/admin/onboarding', { state: { brand_id: brandId } })}>
          Generate via Brand Brief →
        </button>
        {error && <div style={{ fontSize: 12, color: '#dc2626', marginTop: 12 }}>{error}</div>}
      </div>
    );
  }

  async function handleCopy() {
    if (!doc) return;
    await navigator.clipboard.writeText(doc.content_markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  async function handleSave() {
    if (!doc || !draft.trim()) return;
    setSaving(true);
    try {
      const updated = await api.updateDocument(doc.id, {
        content_markdown: draft.trim(),
        status: doc.status === 'approved' ? 'draft' : doc.status,
      });
      setDoc(updated);
      setDraft(updated.content_markdown);
      setEditing(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not save');
    } finally {
      setSaving(false);
    }
  }

  async function handleApprove() {
    if (!doc) return;
    setSaving(true);
    try {
      const updated = await api.approveDocument(doc.id);
      setDoc(updated);
      setDraft(updated.content_markdown);
      setEditing(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not approve');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, marginBottom: 14 }}>
        <div>
          <div style={{ fontWeight: 800, fontSize: 16 }}>{doc.title}</div>
          <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 3 }}>
            {doc.status} · Updated {new Date(doc.updated_at).toLocaleString()}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary btn-sm" onClick={handleCopy}>{copied ? 'Copied' : 'Copy Markdown'}</button>
          <button className="btn btn-secondary btn-sm" onClick={() => setEditing(!editing)}>{editing ? 'Cancel' : 'Edit'}</button>
          {doc.status !== 'approved' && (
            <button className="btn btn-dark btn-sm" onClick={handleApprove} disabled={saving}>{saving ? '…' : 'Approve'}</button>
          )}
        </div>
      </div>
      {editing ? (
        <div>
          <textarea
            className="input"
            value={draft}
            onChange={e => setDraft(e.target.value)}
            style={{ minHeight: 580, resize: 'vertical', fontFamily: 'var(--mono)', fontSize: 12, lineHeight: 1.6 }}
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn btn-dark btn-sm" onClick={handleSave} disabled={saving || !draft.trim()}>{saving ? 'Saving…' : 'Save as Draft'}</button>
            <button className="btn btn-secondary btn-sm" onClick={() => { setDraft(doc.content_markdown); setEditing(false); }}>Discard</button>
          </div>
        </div>
      ) : (
        <div style={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.7, background: '#f9fafb', border: '1px solid var(--border)', borderRadius: 10, padding: 16, maxHeight: '72vh', overflow: 'auto' }}>
          {doc.content_markdown}
        </div>
      )}
      {error && <div style={{ fontSize: 12, color: '#dc2626', marginTop: 12 }}>{error}</div>}
    </div>
  );
}

// ── Brand Kit tab ─────────────────────────────────────────────────────────────

function BrandKitTab({ brandId }: { brandId: string }) {
  const navigate = useNavigate();
  const [kit, setKit]         = useState<WorkspaceDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft]     = useState('');
  const [saving, setSaving]   = useState(false);
  const [copied, setCopied]   = useState(false);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    api.getDocuments({ doc_type: 'campaign_brand_kit', brand_id: brandId })
      .then(docs => {
        const latest = docs[0] ?? null;
        setKit(latest);
        setDraft(latest?.content_markdown ?? '');
      })
      .catch((err: unknown) => {
        const status = typeof err === 'object' && err !== null && 'status' in err ? (err as { status?: number }).status : undefined;
        if (status !== 404) setError(err instanceof Error ? err.message : 'Could not load Brand Kit');
      })
      .finally(() => setLoading(false));
  }, [brandId]);

  if (loading) return <div className="loading-full"><span className="spinner" /></div>;

  if (!kit) {
    return (
      <div style={{ textAlign: 'center', padding: '32px 0' }}>
        <div style={{ fontSize: 14, color: 'var(--text2)', marginBottom: 16 }}>
          No Campaign Brand Kit generated yet.
        </div>
        <button className="btn btn-dark" onClick={() => navigate('/admin/onboarding', { state: { brand_id: brandId } })}>
          Generate in Onboarding →
        </button>
        {error && <div style={{ fontSize: 12, color: '#dc2626', marginTop: 12 }}>{error}</div>}
      </div>
    );
  }

  async function handleCopy() {
    if (!kit) return;
    await navigator.clipboard.writeText(kit.content_markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  async function handleSave() {
    if (!kit || !draft.trim()) return;
    setSaving(true);
    try {
      const updated = await api.updateDocument(kit.id, {
        content_markdown: draft.trim(),
        status: kit.status === 'approved' ? 'draft' : kit.status,
      });
      setKit(updated);
      setDraft(updated.content_markdown);
      setEditing(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not save');
    } finally {
      setSaving(false);
    }
  }

  async function handleApprove() {
    if (!kit) return;
    setSaving(true);
    try {
      const updated = await api.approveDocument(kit.id);
      setKit(updated);
      setDraft(updated.content_markdown);
      setEditing(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not approve');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, marginBottom: 14 }}>
        <div>
          <div style={{ fontWeight: 800, fontSize: 16 }}>{kit.title}</div>
          <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 3 }}>
            {kit.status} · Updated {new Date(kit.updated_at).toLocaleString()}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary btn-sm" onClick={handleCopy}>{copied ? 'Copied' : 'Copy Markdown'}</button>
          <button className="btn btn-secondary btn-sm" onClick={() => setEditing(!editing)}>{editing ? 'Cancel' : 'Edit'}</button>
          {kit.status !== 'approved' && (
            <button className="btn btn-dark btn-sm" onClick={handleApprove} disabled={saving}>{saving ? '…' : 'Approve'}</button>
          )}
        </div>
      </div>
      {editing ? (
        <div>
          <textarea
            className="input"
            value={draft}
            onChange={e => setDraft(e.target.value)}
            style={{ minHeight: 500, resize: 'vertical', fontFamily: 'var(--mono)', fontSize: 12, lineHeight: 1.6 }}
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn btn-dark btn-sm" onClick={handleSave} disabled={saving || !draft.trim()}>{saving ? 'Saving…' : 'Save as Draft'}</button>
            <button className="btn btn-secondary btn-sm" onClick={() => { setDraft(kit.content_markdown); setEditing(false); }}>Discard</button>
          </div>
        </div>
      ) : (
        <div style={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.7, background: '#f9fafb', border: '1px solid var(--border)', borderRadius: 10, padding: 16, maxHeight: '70vh', overflow: 'auto' }}>
          {kit.content_markdown}
        </div>
      )}
      {error && <div style={{ fontSize: 12, color: '#dc2626', marginTop: 12 }}>{error}</div>}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function AdminBrandDetail() {
  const { brandId } = useParams<{ brandId: string }>();
  const navigate    = useNavigate();

  const [brand, setBrand]       = useState<BrandResponse | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null);
  const [loading, setLoading]   = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>('profile');
  const [error, setError]       = useState<string | null>(null);

  useEffect(() => {
    if (!brandId) return;
    Promise.all([
      api.getBrand(brandId),
      api.getWorkspace().catch(() => null),
    ]).then(([b, ws]) => {
      setBrand(b);
      setWorkspace(ws);
    }).catch((err: unknown) => {
      setError(err instanceof Error ? err.message : 'Could not load brand');
    }).finally(() => setLoading(false));
  }, [brandId]);

  if (loading) {
    return <div className="admin-page"><div className="loading-full"><span className="spinner" /></div></div>;
  }

  if (error || !brand) {
    return (
      <div className="admin-page">
        <div style={{ fontSize: 14, color: '#dc2626', marginBottom: 16 }}>{error || 'Brand not found'}</div>
        <button className="btn btn-secondary btn-sm" onClick={() => navigate('/admin/brands')}>← Back to Brands</button>
      </div>
    );
  }

  const TABS: { id: Tab; label: string }[] = [
    { id: 'profile',   label: 'Profile' },
    { id: 'products',  label: 'Products' },
    { id: 'audiences', label: 'Audiences' },
    { id: 'guidelines', label: 'Guidelines' },
    { id: 'brand-kit', label: 'Brand Kit' },
  ];

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <button
              className="btn btn-ghost btn-sm"
              style={{ padding: '2px 6px', fontSize: 12 }}
              onClick={() => navigate('/admin/brands')}
            >
              ← Brands
            </button>
            <span style={{ color: 'var(--text2)', fontSize: 12 }}>/</span>
            <span style={{ fontWeight: 800, fontSize: 14 }}>{brand.name}</span>
          </div>
          <div className="admin-page-title">{brand.name}</div>
          <div className="admin-page-subtitle">
            Brand profile, products, audiences, and documents.
            {brand.domain && <> · {brand.domain}</>}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="btn btn-dark btn-sm"
            onClick={() => navigate('/admin/onboarding', { state: { brand_id: brand.id, brand_name: brand.name } })}
          >
            Import Brief
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => navigate('/admin/campaigns', { state: { brand_id: brand.id, brand_name: brand.name } })}
          >
            Campaigns
          </button>
        </div>
      </div>

      <div className="admin-card" style={{ padding: 0 }}>
        <div className="tabs" style={{ padding: '0 24px', margin: 0, borderRadius: '14px 14px 0 0' }}>
          {TABS.map(({ id, label }) => (
            <div
              key={id}
              className={`tab${activeTab === id ? ' active' : ''}`}
              onClick={() => setActiveTab(id)}
            >
              {label}
            </div>
          ))}
        </div>
        <div style={{ padding: 24 }}>
          {activeTab === 'profile' && (
            <ProfileTab brand={brand} onUpdate={setBrand} />
          )}
          {activeTab === 'products' && workspace && (
            <ProductsTab products={workspace.products} brandId={brand.id} brandName={brand.name} />
          )}
          {activeTab === 'audiences' && workspace && (
            <AudiencesTab audiences={workspace.audiences} brandId={brand.id} brandName={brand.name} />
          )}
          {activeTab === 'guidelines' && (
            <GuidelinesTab brandId={brand.id} />
          )}
          {activeTab === 'brand-kit' && (
            <BrandKitTab brandId={brand.id} />
          )}
        </div>
      </div>
    </div>
  );
}
