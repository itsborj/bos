import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { AudienceOut, ProductOut, WorkspaceResponse } from '../api/types';

/* ── Brand section ── */
export function BrandSection({ workspace, onUpdate }: { workspace: WorkspaceResponse; onUpdate: (ws: WorkspaceResponse) => void }) {
  const [editing, setEditing] = useState(false);
  const brand = workspace.brand ?? {};
  const [voice, setVoice]         = useState(brand.voice ?? '');
  const [tone, setTone]           = useState(brand.tone ?? '');
  const [valuesRaw, setValuesRaw] = useState((brand.values ?? []).join(', '));
  const [saving, setSaving]       = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const ws = await api.putBrand({
        voice: voice || undefined,
        tone: tone || undefined,
        values: valuesRaw ? valuesRaw.split(',').map(v => v.trim()).filter(Boolean) : [],
      });
      onUpdate(ws);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  if (editing) {
    return (
      <form onSubmit={save}>
        <div className="form-group">
          <label className="label">Brand Voice</label>
          <input className="input" value={voice} onChange={e => setVoice(e.target.value)} placeholder="e.g. authoritative and direct" autoFocus />
        </div>
        <div className="form-group">
          <label className="label">Tone</label>
          <input className="input" value={tone} onChange={e => setTone(e.target.value)} placeholder="e.g. professional with warmth" />
        </div>
        <div className="form-group">
          <label className="label">Core Values <span className="label-hint">comma-separated</span></label>
          <input className="input" value={valuesRaw} onChange={e => setValuesRaw(e.target.value)} placeholder="speed, clarity, results" />
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button type="submit" className="btn btn-dark btn-sm" disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
          <button type="button" className="btn btn-sm" onClick={() => setEditing(false)}>Cancel</button>
        </div>
      </form>
    );
  }

  return (
    <>
      <div className="ws-label">Brand Voice</div>
      <div className={`ws-field${!brand.voice ? ' empty' : ''}`}>{brand.voice || 'Not set'}</div>
      <div className="ws-label">Tone</div>
      <div className={`ws-field${!brand.tone ? ' empty' : ''}`}>{brand.tone || 'Not set'}</div>
      <div className="ws-label">Core Values</div>
      <div className={`ws-field${!brand.values?.length ? ' empty' : ''}`}>
        {brand.values?.join(' · ') || 'Not set'}
      </div>
      <button className="btn btn-sm" onClick={() => setEditing(true)}>Edit</button>
    </>
  );
}

/* ── Audiences section ── */
export function AudiencesSection({ workspace, onUpdate }: { workspace: WorkspaceResponse; onUpdate: (ws: WorkspaceResponse) => void }) {
  const [audiences, setAudiences] = useState<AudienceOut[]>(workspace.audiences);
  const [editIdx, setEditIdx]     = useState<number | null>(null);
  const [saving, setSaving]       = useState(false);

  const [name, setName] = useState('');
  const [demo, setDemo] = useState('');
  const [pain, setPain] = useState('');

  function startEdit(idx: number) {
    const a = audiences[idx];
    setName(a.name); setDemo(a.demographics ?? ''); setPain(a.pain_points.join(', '));
    setEditIdx(idx);
  }

  function startAdd() {
    setName(''); setDemo(''); setPain('');
    setEditIdx(audiences.length);
  }

  async function saveAll(updated: AudienceOut[]) {
    setSaving(true);
    try {
      const ws = await api.putAudiences(updated.map(a => ({
        id: a.id || undefined, name: a.name,
        demographics: a.demographics || undefined,
        pain_points: a.pain_points,
      })));
      setAudiences(ws.audiences);
      onUpdate(ws);
      setEditIdx(null);
    } finally {
      setSaving(false);
    }
  }

  function saveRow() {
    if (!name.trim()) return;
    const updated = [...audiences];
    const item: AudienceOut = {
      id: editIdx! < audiences.length ? audiences[editIdx!].id : '',
      name, demographics: demo,
      pain_points: pain.split(',').map(p => p.trim()).filter(Boolean),
    };
    updated[editIdx!] = item;
    saveAll(updated);
  }

  return (
    <>
      {audiences.map((a, i) => (
        <div key={a.id || i} style={{ marginBottom: 8 }}>
          {editIdx === i ? (
            <div className="card">
              <div className="form-group">
                <label className="label">Segment</label>
                <input className="input" value={name} onChange={e => setName(e.target.value)} autoFocus />
              </div>
              <div className="form-group">
                <label className="label">Demographics</label>
                <input className="input" value={demo} onChange={e => setDemo(e.target.value)} placeholder="e.g. 28–42, founders" />
              </div>
              <div className="form-group">
                <label className="label">Pain Points <span className="label-hint">comma-separated</span></label>
                <input className="input" value={pain} onChange={e => setPain(e.target.value)} />
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-dark btn-sm" onClick={saveRow} disabled={saving || !name.trim()}>{saving ? '…' : 'Save'}</button>
                <button className="btn btn-sm" onClick={() => setEditIdx(null)}>Cancel</button>
                <button className="btn btn-danger btn-sm" onClick={() => saveAll(audiences.filter((_, j) => j !== i))}>Remove</button>
              </div>
            </div>
          ) : (
            <div className="ws-field" style={{ marginBottom: 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontWeight: 600, marginBottom: 2 }}>{a.name}</div>
                  {a.demographics && <div style={{ fontSize: 12, color: '#666' }}>{a.demographics}</div>}
                  {a.pain_points.length > 0 && <div style={{ fontSize: 12, color: '#999' }}>{a.pain_points.join(' · ')}</div>}
                </div>
                <button className="btn btn-sm" style={{ flexShrink: 0, marginLeft: 8 }} onClick={() => startEdit(i)}>Edit</button>
              </div>
            </div>
          )}
        </div>
      ))}
      {editIdx === audiences.length ? (
        <div className="card" style={{ marginBottom: 8 }}>
          <div className="form-group">
            <label className="label">Segment</label>
            <input className="input" value={name} onChange={e => setName(e.target.value)} autoFocus placeholder="Segment name" />
          </div>
          <div className="form-group">
            <label className="label">Demographics</label>
            <input className="input" value={demo} onChange={e => setDemo(e.target.value)} placeholder="e.g. 28–42, founders" />
          </div>
          <div className="form-group">
            <label className="label">Pain Points <span className="label-hint">comma-separated</span></label>
            <input className="input" value={pain} onChange={e => setPain(e.target.value)} />
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-dark btn-sm" onClick={saveRow} disabled={saving || !name.trim()}>{saving ? '…' : 'Save'}</button>
            <button className="btn btn-sm" onClick={() => setEditIdx(null)}>Cancel</button>
          </div>
        </div>
      ) : (
        <button className="btn btn-sm" onClick={startAdd} disabled={editIdx !== null}>+ Add Audience</button>
      )}
    </>
  );
}

/* ── Products section ── */
export function ProductsSection({ workspace, onUpdate }: { workspace: WorkspaceResponse; onUpdate: (ws: WorkspaceResponse) => void }) {
  const [products, setProducts] = useState<ProductOut[]>(workspace.products);
  const [editIdx, setEditIdx]   = useState<number | null>(null);
  const [saving, setSaving]     = useState(false);

  const [name, setName]     = useState('');
  const [tag, setTag]       = useState('');
  const [bens, setBens]     = useState('');

  function startEdit(idx: number) {
    const p = products[idx];
    setName(p.name); setTag(p.tagline ?? ''); setBens(p.benefits.join(', '));
    setEditIdx(idx);
  }

  function startAdd() {
    setName(''); setTag(''); setBens('');
    setEditIdx(products.length);
  }

  async function saveAll(updated: ProductOut[]) {
    setSaving(true);
    try {
      const ws = await api.putProducts(updated.map(p => ({
        id: p.id || undefined, name: p.name,
        tagline: p.tagline || undefined,
        benefits: p.benefits,
      })));
      setProducts(ws.products);
      onUpdate(ws);
      setEditIdx(null);
    } finally {
      setSaving(false);
    }
  }

  function saveRow() {
    if (!name.trim()) return;
    const updated = [...products];
    const item: ProductOut = {
      id: editIdx! < products.length ? products[editIdx!].id : '',
      name, tagline: tag,
      benefits: bens.split(',').map(b => b.trim()).filter(Boolean),
    };
    updated[editIdx!] = item;
    saveAll(updated);
  }

  return (
    <>
      {products.map((p, i) => (
        editIdx === i ? (
          <div key={p.id || i} className="card" style={{ marginBottom: 8 }}>
            <div className="form-group">
              <label className="label">Name</label>
              <input className="input" value={name} onChange={e => setName(e.target.value)} autoFocus />
            </div>
            <div className="form-group">
              <label className="label">Tagline</label>
              <input className="input" value={tag} onChange={e => setTag(e.target.value)} placeholder="One-line description" />
            </div>
            <div className="form-group">
              <label className="label">Benefits <span className="label-hint">comma-separated</span></label>
              <input className="input" value={bens} onChange={e => setBens(e.target.value)} />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-dark btn-sm" onClick={saveRow} disabled={saving || !name.trim()}>{saving ? '…' : 'Save'}</button>
              <button className="btn btn-sm" onClick={() => setEditIdx(null)}>Cancel</button>
              <button className="btn btn-danger btn-sm" onClick={() => saveAll(products.filter((_, j) => j !== i))}>Remove</button>
            </div>
          </div>
        ) : (
          <div key={p.id || i} className="product-chip" onClick={() => startEdit(i)}>
            <div className="product-chip-icon">{p.name.charAt(0).toUpperCase()}</div>
            <div>
              <div className="product-chip-name">{p.name}</div>
              <div className="product-chip-meta">{p.tagline || (p.benefits.length > 0 ? p.benefits.join(' · ') : 'No tagline')}</div>
            </div>
            <span className="product-chip-arrow">›</span>
          </div>
        )
      ))}
      {editIdx === products.length ? (
        <div className="card" style={{ marginBottom: 8 }}>
          <div className="form-group">
            <label className="label">Name</label>
            <input className="input" value={name} onChange={e => setName(e.target.value)} autoFocus placeholder="Product name" />
          </div>
          <div className="form-group">
            <label className="label">Tagline</label>
            <input className="input" value={tag} onChange={e => setTag(e.target.value)} placeholder="One-line description" />
          </div>
          <div className="form-group">
            <label className="label">Benefits <span className="label-hint">comma-separated</span></label>
            <input className="input" value={bens} onChange={e => setBens(e.target.value)} />
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-dark btn-sm" onClick={saveRow} disabled={saving || !name.trim()}>{saving ? '…' : 'Save'}</button>
            <button className="btn btn-sm" onClick={() => setEditIdx(null)}>Cancel</button>
          </div>
        </div>
      ) : (
        <button className="btn btn-sm" onClick={startAdd} disabled={editIdx !== null}>+ Add Product</button>
      )}
    </>
  );
}

/* ── Main page ── */
function InitForm({ onCreated }: { onCreated: (ws: WorkspaceResponse) => void }) {
  const [voice, setVoice]   = useState('');
  const [tone, setTone]     = useState('');
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const ws = await api.putBrand({ voice: voice || undefined, tone: tone || undefined });
      onCreated(ws);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ maxWidth: 480 }}>
      <form onSubmit={submit} className="card">
        <div className="card-title">Initialize Workspace</div>
        <div className="form-group">
          <label className="label">Brand Voice</label>
          <input className="input" value={voice} onChange={e => setVoice(e.target.value)} placeholder="e.g. authoritative and direct" autoFocus />
        </div>
        <div className="form-group">
          <label className="label">Tone</label>
          <input className="input" value={tone} onChange={e => setTone(e.target.value)} placeholder="e.g. professional with warmth" />
        </div>
        <button type="submit" className="btn btn-dark" disabled={saving || (!voice && !tone)}>
          {saving ? 'Initializing…' : 'Initialize Workspace'}
        </button>
      </form>
    </div>
  );
}

export { BrandSection as BrandTab, ProductsSection as ProductsTab, AudiencesSection as AudiencesTab };

export function Workspace() {
  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null);
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    api.getWorkspace().then(setWorkspace).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="loading-full">
        <span className="spinner" />
        Loading…
      </div>
    );
  }

  if (!workspace) return <InitForm onCreated={ws => setWorkspace(ws)} />;

  const hasBrand    = !!(workspace.brand?.voice || workspace.brand?.tone);
  const hasProducts = workspace.products.length > 0;
  const hasAudiences = workspace.audiences.length > 0;

  return (
    <div className="ws-grid">
      {/* Left: Brand + Audiences */}
      <div>
        <div className="section-header">
          <span className="section-title">Brand</span>
        </div>
        <div className="card" style={{ marginBottom: 16 }}>
          <BrandSection workspace={workspace} onUpdate={setWorkspace} />
        </div>

        <div className="section-header">
          <span className="section-title">Audiences</span>
        </div>
        <AudiencesSection workspace={workspace} onUpdate={setWorkspace} />
      </div>

      {/* Right: Products + CMO draws from here */}
      <div>
        <div className="section-header">
          <span className="section-title">
            Products
            <span className="section-sub">{workspace.products.length} active</span>
          </span>
        </div>
        <ProductsSection workspace={workspace} onUpdate={setWorkspace} />

        <div className="section-header" style={{ marginTop: 18 }}>
          <span className="section-title">What CMO draws from here</span>
        </div>
        <div className="card" style={{ borderColor: hasBrand && hasProducts ? '#ddd' : '#f0f0f0' }}>
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.8px', textTransform: 'uppercase', color: '#999', marginBottom: 10 }}>
            Auto-resolved on every module run
          </div>
          <div className="ws-cmo-check">
            <span className={hasBrand ? 'ok' : 'dim'}>{hasBrand ? '✓' : '○'}</span>
            Brand voice & tone → injected into all copy modules
          </div>
          <div className="ws-cmo-check">
            <span className={hasProducts ? 'ok' : 'dim'}>{hasProducts ? '✓' : '○'}</span>
            Product benefits → resolved from catalog, no re-entry
          </div>
          <div className="ws-cmo-check">
            <span className={hasAudiences ? 'ok' : 'dim'}>{hasAudiences ? '✓' : '○'}</span>
            Audience pain points → seeded into all briefs
          </div>
        </div>
      </div>
    </div>
  );
}
