import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import type { WorkspaceDocument, WorkspaceResponse } from '../../api/types';
import { ProductsTab, AudiencesTab } from './WorkspaceTabs';

type Tab = 'brand' | 'products' | 'audiences' | 'guidelines' | 'brand-kit';

function BrandReadOnly({ workspace }: { workspace: WorkspaceResponse }) {
  const navigate = useNavigate();
  const brand = workspace.brand;

  if (!brand?.voice && !brand?.tone && !brand?.values?.length) {
    return (
      <div style={{ textAlign: 'center', padding: '32px 0' }}>
        <div style={{ fontSize: 14, color: 'var(--text2)', marginBottom: 16 }}>
          Brand profile not set up yet.
        </div>
        <button className="btn btn-dark" onClick={() => navigate('/admin/onboarding')}>
          Set up via Brand Brief →
        </button>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 24, marginBottom: 20 }}>
        <div>
          <div className="label" style={{ marginBottom: 4 }}>Voice</div>
          <div style={{ fontSize: 14 }}>{brand.voice || '—'}</div>
        </div>
        <div>
          <div className="label" style={{ marginBottom: 4 }}>Tone</div>
          <div style={{ fontSize: 14 }}>{brand.tone || '—'}</div>
        </div>
        <div>
          <div className="label" style={{ marginBottom: 4 }}>Values</div>
          <div style={{ fontSize: 14 }}>{brand.values?.join(', ') || '—'}</div>
        </div>
      </div>
      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 12, color: 'var(--text2)' }}>
          Set by document ingestion — edit by submitting an updated brief
        </span>
        <button className="btn btn-ghost btn-sm" onClick={() => navigate('/admin/onboarding')}>
          Update via Brand Brief →
        </button>
      </div>
    </div>
  );
}

function BrandGuidelinesTab() {
  const [doc, setDoc] = useState<WorkspaceDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getDocuments({ doc_type: 'brand_guideline' })
      .then(docs => {
        const latest = docs[0] ?? null;
        setDoc(latest);
        setDraft(latest?.content_markdown ?? '');
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Could not load Brand Guidelines'))
      .finally(() => setLoading(false));
  }, []);

  async function handleCopy() {
    if (!doc) return;
    await navigator.clipboard.writeText(doc.content_markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  async function handleSave() {
    if (!doc || !draft.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateDocument(doc.id, { content_markdown: draft.trim(), status: doc.status === 'approved' ? 'draft' : doc.status });
      setDoc(updated);
      setDraft(updated.content_markdown);
      setEditing(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not save Brand Guidelines');
    } finally {
      setSaving(false);
    }
  }

  async function handleApprove() {
    if (!doc) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.approveDocument(doc.id);
      setDoc(updated);
      setDraft(updated.content_markdown);
      setEditing(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not approve Brand Guidelines');
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="loading-full"><span className="spinner" /></div>;

  if (!doc) {
    return (
      <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text2)' }}>
        No long-form Brand Guidelines document has been created yet.
        {error && <div style={{ fontSize: 12, color: 'var(--error)', marginTop: 12 }}>{error}</div>}
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, marginBottom: 14 }}>
        <div>
          <div style={{ fontWeight: 800, fontSize: 16 }}>{doc.title}</div>
          <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 3 }}>
            Long-form brand source of truth · {doc.status} · Updated {new Date(doc.updated_at).toLocaleString()} · stored as <code>brand_guideline</code>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <button className="btn btn-ghost btn-sm" onClick={handleCopy}>{copied ? 'Copied' : 'Copy Markdown'}</button>
          <button className="btn btn-ghost btn-sm" onClick={() => setEditing(!editing)}>{editing ? 'Cancel Edit' : 'Edit'}</button>
          {doc.status !== 'approved' && (
            <button className="btn btn-dark btn-sm" onClick={handleApprove} disabled={saving}>{saving ? 'Saving…' : 'Approve'}</button>
          )}
        </div>
      </div>

      {editing ? (
        <div>
          <textarea
            className="input"
            value={draft}
            onChange={e => setDraft(e.target.value)}
            style={{ minHeight: 620, resize: 'vertical', fontFamily: 'var(--mono)', fontSize: 12, lineHeight: 1.6 }}
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn btn-dark btn-sm" onClick={handleSave} disabled={saving || !draft.trim()}>{saving ? 'Saving…' : 'Save as Draft'}</button>
            <button className="btn btn-ghost btn-sm" onClick={() => { setDraft(doc.content_markdown); setEditing(false); }}>Discard</button>
          </div>
        </div>
      ) : (
        <div style={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.7, background: 'var(--ivory)', border: '.5px solid var(--border)', borderRadius: 0, padding: 16, maxHeight: '72vh', overflow: 'auto' }}>
          {doc.content_markdown}
        </div>
      )}
      {error && <div style={{ fontSize: 12, color: 'var(--error)', marginTop: 12 }}>{error}</div>}
    </div>
  );
}

function CampaignBrandKitTab() {
  const navigate = useNavigate();
  const [kit, setKit] = useState<WorkspaceDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getLatestBrandKit()
      .then(doc => { setKit(doc); setDraft(doc.content_markdown); })
      .catch((err: unknown) => {
        const status = typeof err === 'object' && err !== null && 'status' in err ? (err as { status?: number }).status : undefined;
        if (status !== 404) setError(err instanceof Error ? err.message : 'Could not load Campaign Brand Kit');
      })
      .finally(() => setLoading(false));
  }, []);

  async function handleCopy() {
    if (!kit) return;
    await navigator.clipboard.writeText(kit.content_markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  async function handleSave() {
    if (!kit || !draft.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateDocument(kit.id, { content_markdown: draft.trim(), status: kit.status === 'approved' ? 'draft' : kit.status });
      setKit(updated);
      setDraft(updated.content_markdown);
      setEditing(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not save Campaign Brand Kit');
    } finally {
      setSaving(false);
    }
  }

  async function handleApprove() {
    if (!kit) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.approveDocument(kit.id);
      setKit(updated);
      setDraft(updated.content_markdown);
      setEditing(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not approve Campaign Brand Kit');
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="loading-full"><span className="spinner" /></div>;

  if (!kit) {
    return (
      <div style={{ textAlign: 'center', padding: '32px 0' }}>
        <div style={{ fontSize: 14, color: 'var(--text2)', marginBottom: 16 }}>
          No Campaign Brand Kit has been generated yet.
        </div>
        <button className="btn btn-dark" onClick={() => navigate('/admin/onboarding')}>
          Generate in Onboarding →
        </button>
        {error && <div style={{ fontSize: 12, color: 'var(--error)', marginTop: 12 }}>{error}</div>}
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, marginBottom: 14 }}>
        <div>
          <div style={{ fontWeight: 800, fontSize: 16 }}>{kit.title}</div>
          <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 3 }}>
            {kit.status} · Updated {new Date(kit.updated_at).toLocaleString()} · stored as <code>campaign_brand_kit</code>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <button className="btn btn-ghost btn-sm" onClick={handleCopy}>{copied ? 'Copied' : 'Copy Markdown'}</button>
          <button className="btn btn-ghost btn-sm" onClick={() => setEditing(!editing)}>{editing ? 'Cancel Edit' : 'Edit'}</button>
          {kit.status !== 'approved' && (
            <button className="btn btn-dark btn-sm" onClick={handleApprove} disabled={saving}>{saving ? 'Saving…' : 'Approve'}</button>
          )}
        </div>
      </div>

      {editing ? (
        <div>
          <textarea
            className="input"
            value={draft}
            onChange={e => setDraft(e.target.value)}
            style={{ minHeight: 520, resize: 'vertical', fontFamily: 'var(--mono)', fontSize: 12, lineHeight: 1.6 }}
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn btn-dark btn-sm" onClick={handleSave} disabled={saving || !draft.trim()}>{saving ? 'Saving…' : 'Save as Draft'}</button>
            <button className="btn btn-ghost btn-sm" onClick={() => { setDraft(kit.content_markdown); setEditing(false); }}>Discard</button>
          </div>
        </div>
      ) : (
        <div style={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.7, background: 'var(--ivory)', border: '.5px solid var(--border)', borderRadius: 0, padding: 16, maxHeight: '70vh', overflow: 'auto' }}>
          {kit.content_markdown}
        </div>
      )}
      {error && <div style={{ fontSize: 12, color: 'var(--error)', marginTop: 12 }}>{error}</div>}
    </div>
  );
}

export function AdminWorkspace() {
  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>('brand');
  const [nameEditing, setNameEditing] = useState(false);
  const [nameValue, setNameValue] = useState('');
  const [nameSaving, setNameSaving] = useState(false);

  useEffect(() => {
    api.getWorkspace()
      .then(ws => { setWorkspace(ws); setNameValue(ws.name); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleRenameSave() {
    if (!nameValue.trim() || !workspace) return;
    setNameSaving(true);
    try {
      const updated = await api.putWorkspace(nameValue.trim());
      setWorkspace(updated);
      setNameEditing(false);
    } finally {
      setNameSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="admin-page">
        <div className="loading-full"><span className="spinner" /></div>
      </div>
    );
  }

  if (!workspace) {
    return (
      <div className="admin-page">
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          Workspace not set up yet.
        </div>
        <a href="/admin/onboarding" className="btn btn-dark">Go to Onboarding →</a>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          {nameEditing ? (
            <div className="inline-edit" style={{ marginBottom: 4 }}>
              <input
                className="input"
                value={nameValue}
                onChange={e => setNameValue(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleRenameSave(); if (e.key === 'Escape') setNameEditing(false); }}
                autoFocus
                style={{ fontSize: 20, fontWeight: 800 }}
              />
              <button className="btn btn-dark btn-sm" onClick={handleRenameSave} disabled={nameSaving}>
                {nameSaving ? '…' : 'Save'}
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => setNameEditing(false)}>Cancel</button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <div className="admin-page-title">{workspace.name}</div>
              <button className="btn btn-ghost btn-sm" onClick={() => setNameEditing(true)}>Rename</button>
            </div>
          )}
          <div className="admin-page-subtitle">Brand memory — profile, products, audiences, Brand Guidelines, and Campaign Brand Kit</div>
        </div>
      </div>

      <div className="admin-card" style={{ padding: 0 }}>
        <div className="tabs" style={{ padding: '0 24px', margin: 0, borderRadius: '14px 14px 0 0' }}>
          {(['brand', 'products', 'audiences', 'guidelines', 'brand-kit'] as Tab[]).map(tab => (
            <div
              key={tab}
              className={`tab${activeTab === tab ? ' active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab === 'brand-kit' ? 'Brand Kit' : tab === 'guidelines' ? 'Guidelines' : tab.charAt(0).toUpperCase() + tab.slice(1)}
            </div>
          ))}
        </div>
        <div style={{ padding: 24 }}>
          {activeTab === 'brand'     && <BrandReadOnly workspace={workspace} />}
          {activeTab === 'products'  && <ProductsTab  workspace={workspace} onUpdate={setWorkspace} />}
          {activeTab === 'audiences' && <AudiencesTab workspace={workspace} onUpdate={setWorkspace} />}
          {activeTab === 'guidelines' && <BrandGuidelinesTab />}
          {activeTab === 'brand-kit' && <CampaignBrandKitTab />}
        </div>
      </div>
    </div>
  );
}
