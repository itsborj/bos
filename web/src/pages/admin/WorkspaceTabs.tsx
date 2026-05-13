import { useState } from 'react';
import { api } from '../../api/client';
import type { AudienceOut, ProductOut, WorkspaceResponse } from '../../api/types';

export function BrandTab({ workspace, onUpdate }: { workspace: WorkspaceResponse; onUpdate: (ws: WorkspaceResponse) => void }) {
  const brand = workspace.brand ?? {};
  const [voice, setVoice]         = useState(brand.voice ?? '');
  const [tone, setTone]           = useState(brand.tone ?? '');
  const [valuesRaw, setValuesRaw] = useState((brand.values ?? []).join(', '));
  const [saving, setSaving]       = useState(false);
  const [saved, setSaved]         = useState(false);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await api.putBrand({
        voice: voice || undefined,
        tone: tone || undefined,
        values: valuesRaw ? valuesRaw.split(',').map(v => v.trim()).filter(Boolean) : [],
      });
      onUpdate(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSave}>
      <div className="form-group">
        <label className="label" htmlFor="voice">
          Brand Voice <span className="label-hint">how you sound</span>
        </label>
        <input id="voice" className="input" value={voice} onChange={e => setVoice(e.target.value)} placeholder="e.g. authoritative and direct" />
      </div>
      <div className="form-group">
        <label className="label" htmlFor="tone">
          Tone <span className="label-hint">emotional register</span>
        </label>
        <input id="tone" className="input" value={tone} onChange={e => setTone(e.target.value)} placeholder="e.g. professional with warmth" />
      </div>
      <div className="form-group">
        <label className="label" htmlFor="values">
          Brand Values <span className="label-hint">comma-separated</span>
        </label>
        <input id="values" className="input" value={valuesRaw} onChange={e => setValuesRaw(e.target.value)} placeholder="transparency, innovation, reliability" />
      </div>
      <button type="submit" className="btn btn-dark" disabled={saving}>
        {saving ? 'Saving…' : saved ? '✓ Saved' : 'Save Brand'}
      </button>
    </form>
  );
}

function ProductRow({
  product, onSave, onRemove,
}: {
  product: ProductOut;
  onSave: (p: ProductOut) => void;
  onRemove: () => void;
}) {
  const [editing, setEditing]         = useState(!product.id);
  const [name, setName]               = useState(product.name);
  const [tagline, setTagline]         = useState(product.tagline ?? '');
  const [benefitsRaw, setBenefitsRaw] = useState(product.benefits.join(', '));

  function handleSave() {
    onSave({ ...product, name, tagline, benefits: benefitsRaw.split(',').map(b => b.trim()).filter(Boolean) });
    setEditing(false);
  }

  if (!editing) {
    return (
      <div className="card">
        <div className="flex items-center justify-between">
          <div style={{ flex: 1, marginRight: 12 }}>
            <div style={{ fontWeight: 700 }}>{product.name}</div>
            {product.tagline && <div style={{ fontSize: 13, color: 'var(--text2)' }}>{product.tagline}</div>}
            {product.benefits.length > 0 && (
              <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 4 }}>{product.benefits.join(' · ')}</div>
            )}
          </div>
          <div className="flex gap-2">
            <button className="btn btn-secondary btn-sm" onClick={() => setEditing(true)}>Edit</button>
            <button className="btn btn-danger btn-sm" onClick={onRemove}>Remove</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="form-group">
        <label className="label">Name</label>
        <input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="Product name" autoFocus />
      </div>
      <div className="form-group">
        <label className="label">Tagline</label>
        <input className="input" value={tagline} onChange={e => setTagline(e.target.value)} placeholder="One-line description" />
      </div>
      <div className="form-group">
        <label className="label">Key Benefits <span className="label-hint">comma-separated</span></label>
        <input className="input" value={benefitsRaw} onChange={e => setBenefitsRaw(e.target.value)} placeholder="benefit 1, benefit 2" />
      </div>
      <div className="flex gap-2">
        <button className="btn btn-dark btn-sm" onClick={handleSave} disabled={!name.trim()}>Save</button>
        {product.id && <button className="btn btn-ghost btn-sm" onClick={() => setEditing(false)}>Cancel</button>}
      </div>
    </div>
  );
}

export function ProductsTab({ workspace, onUpdate }: { workspace: WorkspaceResponse; onUpdate: (ws: WorkspaceResponse) => void }) {
  const [products, setProducts] = useState<ProductOut[]>(workspace.products);
  const [saving, setSaving]     = useState(false);

  async function saveAll(updated: ProductOut[]) {
    setSaving(true);
    try {
      const ws = await api.putProducts(updated.map(p => ({
        id: p.id || undefined,
        name: p.name,
        tagline: p.tagline || undefined,
        benefits: p.benefits,
      })));
      setProducts(ws.products);
      onUpdate(ws);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {products.map((p, i) => (
        <ProductRow
          key={p.id || `new-${i}`}
          product={p}
          onSave={updated => { const next = [...products]; next[i] = updated; saveAll(next); }}
          onRemove={() => saveAll(products.filter((_, j) => j !== i))}
        />
      ))}
      {saving && <div style={{ color: 'var(--text2)', fontSize: 13 }}>Saving…</div>}
      <button
        className="btn btn-secondary"
        onClick={() => setProducts(prev => [...prev, { id: '', name: '', tagline: '', benefits: [] }])}
        disabled={saving}
      >
        + Add Product
      </button>
    </div>
  );
}

function AudienceRow({
  audience, onSave, onRemove,
}: {
  audience: AudienceOut;
  onSave: (a: AudienceOut) => void;
  onRemove: () => void;
}) {
  const [editing, setEditing] = useState(!audience.id);
  const [name, setName]       = useState(audience.name);
  const [demo, setDemo]       = useState(audience.demographics ?? '');
  const [painRaw, setPainRaw] = useState(audience.pain_points.join(', '));

  function handleSave() {
    onSave({ ...audience, name, demographics: demo, pain_points: painRaw.split(',').map(p => p.trim()).filter(Boolean) });
    setEditing(false);
  }

  if (!editing) {
    return (
      <div className="card">
        <div className="flex items-center justify-between">
          <div style={{ flex: 1, marginRight: 12 }}>
            <div style={{ fontWeight: 700 }}>{audience.name}</div>
            {audience.demographics && <div style={{ fontSize: 13, color: 'var(--text2)' }}>{audience.demographics}</div>}
            {audience.pain_points.length > 0 && (
              <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 4 }}>Pain: {audience.pain_points.join(' · ')}</div>
            )}
          </div>
          <div className="flex gap-2">
            <button className="btn btn-secondary btn-sm" onClick={() => setEditing(true)}>Edit</button>
            <button className="btn btn-danger btn-sm" onClick={onRemove}>Remove</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="form-group">
        <label className="label">Segment Name</label>
        <input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. SMB decision makers" autoFocus />
      </div>
      <div className="form-group">
        <label className="label">Demographics</label>
        <input className="input" value={demo} onChange={e => setDemo(e.target.value)} placeholder="e.g. 35-55, managers at 10-200 person companies" />
      </div>
      <div className="form-group">
        <label className="label">Pain Points <span className="label-hint">comma-separated</span></label>
        <input className="input" value={painRaw} onChange={e => setPainRaw(e.target.value)} placeholder="too much admin, slow approvals" />
      </div>
      <div className="flex gap-2">
        <button className="btn btn-dark btn-sm" onClick={handleSave} disabled={!name.trim()}>Save</button>
        {audience.id && <button className="btn btn-ghost btn-sm" onClick={() => setEditing(false)}>Cancel</button>}
      </div>
    </div>
  );
}

export function AudiencesTab({ workspace, onUpdate }: { workspace: WorkspaceResponse; onUpdate: (ws: WorkspaceResponse) => void }) {
  const [audiences, setAudiences] = useState<AudienceOut[]>(workspace.audiences);
  const [saving, setSaving]       = useState(false);

  async function saveAll(updated: AudienceOut[]) {
    setSaving(true);
    try {
      const ws = await api.putAudiences(updated.map(a => ({
        id: a.id || undefined,
        name: a.name,
        demographics: a.demographics || undefined,
        pain_points: a.pain_points,
      })));
      setAudiences(ws.audiences);
      onUpdate(ws);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {audiences.map((a, i) => (
        <AudienceRow
          key={a.id || `new-${i}`}
          audience={a}
          onSave={updated => { const next = [...audiences]; next[i] = updated; saveAll(next); }}
          onRemove={() => saveAll(audiences.filter((_, j) => j !== i))}
        />
      ))}
      {saving && <div style={{ color: 'var(--text2)', fontSize: 13 }}>Saving…</div>}
      <button
        className="btn btn-secondary"
        onClick={() => setAudiences(prev => [...prev, { id: '', name: '', demographics: '', pain_points: [] }])}
        disabled={saving}
      >
        + Add Audience
      </button>
    </div>
  );
}
