import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { AudienceOut, BillingSummary, BrandResponse, PmConfig, ProductOut, WorkspaceDocument, WorkspaceResponse } from '../../api/types';
import { DriveFolderPickerModal, useDriveFolderPicker } from '../../components/DriveFolderPicker';

type Tab = 'profile' | 'products' | 'audiences' | 'guidelines' | 'brand-kit' | 'project-management' | 'integrations';

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

function imageNameCount(files: { name: string }[], pattern: RegExp): number {
  return files.filter(f => pattern.test(f.name || '')).length;
}

type DriveImageLite = { id: string; name: string; mimeType: string; thumbnailLink?: string; webViewLink?: string };


function BrandKitTab({ brandId, brand }: { brandId: string; brand: BrandResponse }) {
  const navigate = useNavigate();
  const [kit, setKit]         = useState<WorkspaceDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft]     = useState('');
  const [saving, setSaving]   = useState(false);
  const [copied, setCopied]   = useState(false);
  const [error, setError]     = useState<string | null>(null);
  const drive = useDriveFolderPicker(brandId);
  const [foldersLoading, setFoldersLoading] = useState(true);
  const [driveImagesError, setDriveImagesError] = useState<string | null>(null);
  const [assetImages, setAssetImages] = useState<DriveImageLite[]>([]);
  const readinessGeneration = useRef(0);

  async function loadDriveImages(generation: number): Promise<DriveImageLite[] | null> {
    if (generation === readinessGeneration.current) {
      setFoldersLoading(true);
      setDriveImagesError(null);
    }
    try {
      const images = await api.listDriveImages(brandId, undefined, 'image');
      const files = images?.files || [];
      if (generation === readinessGeneration.current) setAssetImages(files);
      return files;
    } catch (err: unknown) {
      if (generation === readinessGeneration.current) setDriveImagesError(err instanceof Error ? err.message : 'Could not read images from the selected Drive folder.');
      return null;
    } finally {
      if (generation === readinessGeneration.current) setFoldersLoading(false);
    }
  }

  useEffect(() => {
    const generation = ++readinessGeneration.current;
    setLoading(true);
    setKit(null);
    setDraft('');
    setError(null);
    setAssetImages([]);
    setDriveImagesError(null);
    api.getDocuments({ doc_type: 'campaign_brand_kit', brand_id: brandId })
      .then(docs => {
        if (generation !== readinessGeneration.current) return;
        const latest = docs[0] ?? null;
        setKit(latest);
        setDraft(latest?.content_markdown ?? '');
      })
      .catch((err: unknown) => {
        if (generation !== readinessGeneration.current) return;
        const status = typeof err === 'object' && err !== null && 'status' in err ? (err as { status?: number }).status : undefined;
        if (status !== 404) setError(err instanceof Error ? err.message : 'Could not load Brand Creative Brief');
      })
      .finally(() => { if (generation === readinessGeneration.current) setLoading(false); });

    void loadDriveImages(generation);
    return () => { if (generation === readinessGeneration.current) readinessGeneration.current += 1; };
  }, [brandId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <div className="loading-full"><span className="spinner" /></div>;

  if (!kit) {
    return (
      <div style={{ textAlign: 'center', padding: '32px 0' }}>
        <div style={{ fontSize: 14, color: 'var(--text2)', marginBottom: 16 }}>
          No Brand Creative Brief generated yet.
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
    if (drive.driveLoading || !drive.driveRoot) {
      setError('Choose and validate a Brand Kit Drive folder containing the official logo before approving the Brand Creative Brief.');
      return;
    }
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
    <div id="campaign-brand-kit" style={{ scrollMarginTop: 90 }}>
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
            <button
              className="btn btn-dark btn-sm"
              onClick={handleApprove}
              disabled={saving || drive.driveLoading || !drive.driveRoot}
              title={!drive.driveRoot ? 'Validate the Brand Kit Drive folder and logo before approval.' : undefined}
            >{saving ? '…' : 'Approve'}</button>
          )}
        </div>
      </div>

      {(() => {
        const readinessLoading = drive.driveLoading || foldersLoading;
        const logoCount = imageNameCount(assetImages, /(^|[-_ .])(logo|wordmark|brandmark|mark)([-_ .]|$)/i);
        const supportingAssetCount = Math.max(0, assetImages.length - logoCount);
        const profileReady = Boolean(brand.voice || brand.tone || brand.values?.length);
        const rootReady = Boolean(drive.driveRoot && logoCount > 0);
        const checklist: Array<{ ok: boolean; label: string; required?: boolean; action?: { label: string; onClick: () => void; disabled?: boolean } }> = [
          { ok: profileReady, label: 'Brand profile imported', required: true },
          { ok: kit.status === 'approved', label: 'Brand Creative Brief approved', required: true },
          { ok: Boolean(drive.driveRoot), label: drive.driveRoot ? `Authorized Brand Kit folder: ${drive.driveRoot.name}` : 'Required: select one Brand Kit Drive folder in Integrations', required: true },
          { ok: logoCount > 0, label: logoCount > 0 ? `Official logo/wordmark available (${logoCount})` : 'Required: add an image named like *_logo.*', required: true },
          { ok: supportingAssetCount >= 3, label: supportingAssetCount >= 3 ? `Creative reference assets available (${supportingAssetCount})` : 'Optional: add 3–5 product, character, people, location, or aesthetic references' },
        ];
        return (
          <div id="brand-kit-assets" style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 14, marginBottom: 14, scrollMarginTop: 90 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', marginBottom: 8 }}>
              <div>
                <div style={{ fontWeight: 800, fontSize: 14 }}>Creative readiness</div>
                <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 3 }}>
                  The approved brief and official logo establish brand readiness. Additional assets guide creativity when relevant; fixed templates are optional.
                </div>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/admin/brands/${brandId}?tab=integrations`)} disabled={readinessLoading}>
                {readinessLoading ? 'Checking…' : rootReady ? 'Change folder' : 'Choose folder'}
              </button>
            </div>
            {error && (
              <div role="alert" style={{ fontSize: 12, color: '#b91c1c', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: 8, marginBottom: 8 }}>
                {error}
              </div>
            )}
            {(drive.driveError || driveImagesError) && (
              <div style={{ fontSize: 12, color: '#b45309', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: 8, marginBottom: 8 }}>
                {driveImagesError || drive.driveError}
              </div>
            )}
            {readinessLoading ? <div style={{ fontSize: 12, color: 'var(--text2)' }}>Checking the authorized Drive folder…</div> : (
              <div style={{ display: 'grid', gap: 7 }}>
                {/* Event callbacks read the request-generation ref only after user interaction. */}
                {/* eslint-disable-next-line react-hooks/refs */}
                {checklist.map(item => {
                  const missingRequired = item.required && !item.ok;
                  return (
                    <div key={item.label} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', justifyContent: 'space-between', fontSize: 12, color: item.ok || !item.required ? 'var(--text)' : 'var(--text2)' }}>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', minWidth: 0 }}>
                        <span className={`badge badge-${item.ok ? 'success' : missingRequired ? 'warning' : 'muted'}`} style={{ fontSize: 10, minWidth: 44, textAlign: 'center' }}>{item.ok ? 'OK' : missingRequired ? 'Todo' : 'Rec'}</span>
                        <span>{item.label}</span>
                      </div>
                      {item.action && (
                        <button className="btn btn-secondary btn-sm" style={{ flexShrink: 0, fontSize: 11, padding: '4px 8px' }} onClick={item.action.onClick} disabled={item.action.disabled}>
                          {item.action.label}
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })()}

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

// ── Project Management tab ────────────────────────────────────────────────────

const PM_PLUGINS: { id: string; label: string; list_id_hint: string; list_id_placeholder: string }[] = [
  { id: 'channel.clickup', label: 'ClickUp', list_id_hint: 'from the list URL: app.clickup.com/…/list/901106xxxxx', list_id_placeholder: '901106xxxxx' },
];

const DEFAULT_STATUS_MAP = { pending: 'review', approved: 'complete', rejected: 'revise' };
const DEFAULT_PM_CONFIG: PmConfig = { plugin: 'channel.clickup', sync_enabled: false, list_id: '', status_map: DEFAULT_STATUS_MAP };

function ProjectManagementTab({ brand, onUpdate }: { brand: BrandResponse; onUpdate: (b: BrandResponse) => void }) {
  const existing = brand.pm_config ?? DEFAULT_PM_CONFIG;

  const [plugin, setPlugin]                 = useState(existing.plugin || 'channel.clickup');
  const [syncEnabled, setSyncEnabled]       = useState(existing.sync_enabled);
  const [listId, setListId]                 = useState(existing.list_id || '');
  const [teamId, setTeamId]                 = useState(existing.team_id || '');
  const [pendingStatus, setPendingStatus]   = useState(existing.status_map?.pending || 'review');
  const [approvedStatus, setApprovedStatus] = useState(existing.status_map?.approved || 'complete');
  const [rejectedStatus, setRejectedStatus] = useState(existing.status_map?.rejected || 'revise');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved]   = useState(false);
  const [error, setError]   = useState<string | null>(null);

  const activePlugin = PM_PLUGINS.find(p => p.id === plugin) ?? PM_PLUGINS[0];

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateBrand(brand.id, {
        pm_config: {
          plugin,
          sync_enabled: syncEnabled,
          list_id: listId.trim(),
          ...(teamId.trim() ? { team_id: teamId.trim() } : {}),
          status_map: { pending: pendingStatus, approved: approvedStatus, rejected: rejectedStatus },
        },
      });
      onUpdate(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not save project management config');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ maxWidth: 520 }}>
      <form onSubmit={handleSave}>
        <div className="form-group">
          <label className="label" htmlFor="pm-plugin">
            Project Management System
          </label>
          <select
            id="pm-plugin"
            className="input"
            value={plugin}
            onChange={e => setPlugin(e.target.value)}
          >
            {PM_PLUGINS.map(p => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </select>
          <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 4 }}>
            Each PM system requires its capability to be configured in Admin → Capabilities.
          </div>
        </div>

        <div className="form-group">
          <label className="label" style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={syncEnabled}
              onChange={e => setSyncEnabled(e.target.checked)}
            />
            Auto-sync completed runs to {activePlugin.label}
          </label>
          <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 4 }}>
            Each completed run creates a review task in the configured list.
          </div>
        </div>

        <div className="form-group">
          <label className="label" htmlFor="pm-list-id">
            List ID <span className="label-hint">{activePlugin.list_id_hint}</span>
          </label>
          <input
            id="pm-list-id"
            className="input"
            value={listId}
            onChange={e => setListId(e.target.value)}
            placeholder={activePlugin.list_id_placeholder}
            disabled={!syncEnabled}
          />
        </div>

        <div className="form-group">
          <label className="label" htmlFor="pm-team-id">
            Workspace ID <span className="label-hint">optional — override if this brand uses a different ClickUp workspace</span>
          </label>
          <input
            id="pm-team-id"
            className="input"
            value={teamId}
            onChange={e => setTeamId(e.target.value)}
            placeholder="e.g. 90161625082 — from app.clickup.com/{ID}/..."
          />
        </div>

        <div className="form-group">
          <label className="label">
            Status mapping <span className="label-hint">BOS status → {activePlugin.label} status name</span>
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '130px 1fr', gap: '6px 12px', alignItems: 'center', marginTop: 6 }}>
            <span style={{ fontSize: 13, color: 'var(--text2)' }}>Pending review</span>
            <input className="input" value={pendingStatus} onChange={e => setPendingStatus(e.target.value)} placeholder="review" disabled={!syncEnabled} />
            <span style={{ fontSize: 13, color: 'var(--text2)' }}>Approved</span>
            <input className="input" value={approvedStatus} onChange={e => setApprovedStatus(e.target.value)} placeholder="complete" disabled={!syncEnabled} />
            <span style={{ fontSize: 13, color: 'var(--text2)' }}>Rejected</span>
            <input className="input" value={rejectedStatus} onChange={e => setRejectedStatus(e.target.value)} placeholder="revise" disabled={!syncEnabled} />
          </div>
        </div>

        {error && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 12 }}>{error}</div>}

        <button type="submit" className="btn btn-dark" disabled={saving}>
          {saving ? 'Saving…' : saved ? '✓ Saved' : 'Save Config'}
        </button>
      </form>
    </div>
  );
}

// ── Integrations tab ──────────────────────────────────────────────────────────

type SocialConn = {
  id: string;
  brand_id: string | null;
  platform: string;
  page_id: string;
  page_name: string | null;
  page_handle: string | null;
  status: string;
};

const INTEGRATION_PLATFORMS = [
  { id: 'facebook',        label: 'Facebook Page',   icon: '📘', twoStep: true },
  { id: 'instagram',       label: 'Instagram',        icon: '📸', twoStep: true },
  { id: 'youtube',         label: 'YouTube',          icon: '▶️' },
  { id: 'tiktok',          label: 'TikTok',           icon: '🎵' },
  { id: 'google_drive',    label: 'Google Drive',     icon: '🗂️', hasFolderPicker: true },
  { id: 'google_business', label: 'Google Business Profile', icon: '📍' },
  { id: 'gmail',           label: 'Gmail',            icon: '✉️' },
  { id: 'google_calendar', label: 'Google Calendar',  icon: '📅' },
] as const;

const CONNECT_RETURN_KEY = 'bos_connect_return';
const SOCIAL_CALLBACK_KEYS = INTEGRATION_PLATFORMS.map(p => p.id);
const SOCIAL_CALLBACK_LABELS: Record<string, string> = Object.fromEntries(
  INTEGRATION_PLATFORMS.map(p => [p.id, p.label])
);
const SOCIAL_CALLBACK_DEFAULT_ACCOUNTS: Record<string, string> = {
  facebook: 'Facebook page',
  instagram: 'Instagram account',
  youtube: 'YouTube channel',
  tiktok: 'TikTok account',
  google_drive: 'Google Drive',
  google_business: 'Google Business Profile',
  gmail: 'Gmail account',
  google_calendar: 'Google Calendar',
};

function hasSocialCallback(params: URLSearchParams): boolean {
  return SOCIAL_CALLBACK_KEYS.some(key => params.has(key));
}

function tabFromSearchParams(params: URLSearchParams): Tab {
  const requestedTab = params.get('tab');
  const validTabs: Tab[] = ['profile', 'products', 'audiences', 'guidelines', 'brand-kit', 'project-management', 'integrations'];
  if (requestedTab && validTabs.includes(requestedTab as Tab)) return requestedTab as Tab;
  if (hasSocialCallback(params)) return 'integrations';
  return 'profile';
}


function IntegrationsTab({ brandId }: { brandId: string }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [conns, setConns]           = useState<SocialConn[]>([]);
  const [loading, setLoading]       = useState(true);
  const [connectingId, setConnectingId] = useState<string | null>(null);
  const [metaModal, setMetaModal]   = useState<{ platform: 'facebook' | 'instagram'; sessionId: string; pages: { id: string; name: string }[] } | null>(null);
  const [toast, setToast]           = useState<string | null>(null);
  const [folderModalOpen, setFolderModalOpen] = useState(false);
  const drive = useDriveFolderPicker(brandId);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function showToast(msg: string) {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 4500);
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.listSocialConnections(brandId)
      .then(c => {
        if (cancelled) return;
        setConns(c as SocialConn[]);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [brandId]);

  useEffect(() => {
    const platform = SOCIAL_CALLBACK_KEYS.find(key => searchParams.has(key));
    if (!platform) return;

    const result = searchParams.get(platform) || '';
    const brandParam = searchParams.get('brand_id');
    const label = SOCIAL_CALLBACK_LABELS[platform] || platform;
    setSearchParams({ tab: 'integrations' }, { replace: true });

    if (brandParam && brandParam !== brandId) return;

    if ((platform === 'facebook' || platform === 'instagram') && result === 'select_page') {
      const sessionId = searchParams.get('session_id') || '';
      if (sessionId) {
        const loader = platform === 'instagram' ? api.instagramPendingPages : api.facebookPendingPages;
        loader(sessionId)
          .then(res => setMetaModal({ platform: platform as 'facebook' | 'instagram', sessionId, pages: res.pages }))
          .catch(() => showToast(`⚠️ Could not load ${label} choices — try connecting again`));
      }
      return;
    }

    if (result === 'connected') {
      const account = searchParams.get('account') || SOCIAL_CALLBACK_DEFAULT_ACCOUNTS[platform] || label;
      showToast(`✅ ${label} "${account}" connected`);
      api.listSocialConnections(brandId).then(c => setConns(c as SocialConn[])).catch(() => {});
    } else if (result === 'denied') {
      showToast(`${label} connection cancelled`);
    } else {
      const reason = searchParams.get('reason') || 'unknown';
      showToast(`⚠️ ${label} connection failed — ${reason.replace(/_/g, ' ')}`);
    }
  }, [brandId, searchParams, setSearchParams]);

  function conn(platform: string): SocialConn | null {
    return conns.find(c => c.platform === platform) ?? null;
  }

  async function handleConnect(platform: string) {
    setConnectingId(platform);
    sessionStorage.setItem(CONNECT_RETURN_KEY, `${window.location.pathname}?tab=integrations`);
    try {
      const res = await api.startSocialConnect(brandId, platform);
      window.location.href = res.authorize_url;
    } catch (e: unknown) {
      showToast(`⚠️ Could not start ${platform} — ${e instanceof Error ? e.message : 'unknown error'}`);
      setConnectingId(null);
    }
  }

  async function handleDisconnect(platform: string, label: string) {
    const c = conn(platform);
    if (!c) return;
    if (!window.confirm(`Disconnect ${label} "${c.page_name || c.page_id}"?`)) return;
    try {
      await api.disconnectSocial(c.id);
      setConns(prev => prev.filter(x => x.id !== c.id));
      if (platform === 'google_drive') drive.refresh();
      showToast(`${label} disconnected`);
    } catch {
      showToast('⚠️ Could not disconnect — try again');
    }
  }

  async function handleSelectMetaPage(pageId: string) {
    if (!metaModal) return;
    try {
      const picker = metaModal.platform === 'instagram' ? api.instagramSelectPage : api.facebookSelectPage;
      await picker(metaModal.sessionId, pageId);
      const page = metaModal.pages.find(p => p.id === pageId);
      const label = metaModal.platform === 'instagram' ? 'Instagram' : 'Facebook';
      setMetaModal(null);
      showToast(`✅ ${label} "${page?.name || pageId}" connected`);
      const updated = await api.listSocialConnections(brandId).catch(() => conns);
      setConns(updated as SocialConn[]);
    } catch {
      showToast('⚠️ Could not select page — try again');
    }
  }

  function handleDriveValidated() {
    setFolderModalOpen(false);
    drive.refresh();
  }

  if (loading) return <div className="loading-full"><span className="spinner" /></div>;

  return (
    <div style={{ maxWidth: 560 }}>
      {toast && (
        <div style={{ position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)', background: 'var(--fg)', color: 'var(--bg)', padding: '10px 20px', borderRadius: 8, fontSize: 13, fontWeight: 600, zIndex: 9999, boxShadow: '0 4px 20px rgba(0,0,0,.2)' }}>
          {toast}
        </div>
      )}

      {metaModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="admin-card" style={{ width: 360, margin: 0, padding: 24 }}>
            <div style={{ fontWeight: 800, fontSize: 15, marginBottom: 6 }}>
              {metaModal.platform === 'instagram' ? 'Select an Instagram-connected Meta Page' : 'Select a Facebook Page'}
            </div>
            <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 16 }}>
              {metaModal.platform === 'instagram'
                ? 'Choose the Meta Page that is linked to the Instagram Business Account you want to connect.'
                : 'Your account manages multiple pages. Choose which one to connect to this brand.'}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {metaModal.pages.map(p => (
                <button
                  key={p.id}
                  className="btn btn-secondary"
                  style={{ justifyContent: 'flex-start', textAlign: 'left' }}
                  onClick={() => handleSelectMetaPage(p.id)}
                >
                  {p.name}
                </button>
              ))}
            </div>
            <button className="btn btn-ghost btn-sm" style={{ marginTop: 12 }} onClick={() => setMetaModal(null)}>Cancel</button>
          </div>
        </div>
      )}

      <DriveFolderPickerModal brandId={brandId} open={folderModalOpen} onClose={() => setFolderModalOpen(false)} onValidated={handleDriveValidated} />

      <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 20 }}>
        Connect social and data platforms for this brand. After OAuth, you'll return here and stay on the Integrations tab.
      </div>

      <div id="publish-channels" style={{ display: 'flex', flexDirection: 'column', gap: 0, scrollMarginTop: 90 }}>
        {INTEGRATION_PLATFORMS.map(({ id, label, icon, ...flags }) => {
          const c = conn(id);
          const busy = connectingId === id;
          const hasFolderPicker = 'hasFolderPicker' in flags && flags.hasFolderPicker;
          const isConnected = c?.status === 'connected';
          const statusText = isConnected ? 'Connected' : (c?.status === 'needs_reauth' ? 'Reconnect required' : 'Setup blocked');
          return (
            <div
              key={id}
              id={`integration-${id}`}
              style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 0', borderBottom: '1px solid var(--border)', scrollMarginTop: 90 }}
            >
              <span style={{ fontSize: 18, width: 28, textAlign: 'center', flexShrink: 0 }}>{icon}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: c ? 700 : 400, color: c ? 'var(--fg)' : 'var(--text2)' }}>
                  {c ? (c.page_name || c.page_id) : label}
                </div>
                {c && (
                  <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 1 }}>{label}</div>
                )}
                {id === 'google_drive' && c && drive.driveRoot && (
                  <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 1 }}>Root: {drive.driveRoot.name}</div>
                )}
              </div>
              {c ? (
                <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
                  <span className={`status-badge ${isConnected ? 'approved' : 'pending'}`} style={{ fontSize: 10 }}>{statusText}</span>
                  {isConnected && hasFolderPicker && (
                    <button className="btn btn-secondary btn-sm" style={{ fontSize: 11 }} onClick={() => setFolderModalOpen(true)}>
                      {drive.driveRoot ? 'Change folder' : 'Choose folder'}
                    </button>
                  )}
                  {!isConnected && (
                    <button className="btn btn-secondary btn-sm" style={{ fontSize: 11 }} onClick={() => handleConnect(id)} disabled={busy}>
                      {busy ? 'Redirecting…' : 'Reconnect'}
                    </button>
                  )}
                  <button
                    className="btn btn-ghost btn-sm"
                    style={{ fontSize: 11, color: '#dc2626' }}
                    onClick={() => handleDisconnect(id, label)}
                  >
                    Disconnect
                  </button>
                </div>
              ) : (
                <button
                  className="btn btn-secondary btn-sm"
                  style={{ fontSize: 12, flexShrink: 0 }}
                  onClick={() => handleConnect(id)}
                  disabled={busy}
                >
                  {busy ? 'Redirecting…' : 'Connect'}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function AdminBrandDetail() {
  const { brandId } = useParams<{ brandId: string }>();
  const navigate    = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [brand, setBrand]         = useState<BrandResponse | null>(null);
  const [workspace, setWorkspace]  = useState<WorkspaceResponse | null>(null);
  const [billing, setBilling]      = useState<BillingSummary | null>(null);
  const [loading, setLoading]      = useState(true);
  const [activeTab, setActiveTab]  = useState<Tab>(() => tabFromSearchParams(searchParams));
  const [error, setError]          = useState<string | null>(null);

  useEffect(() => {
    const nextTab = tabFromSearchParams(searchParams);
    setActiveTab(current => current === nextTab ? current : nextTab);
  }, [searchParams]);

  useEffect(() => {
    const hash = window.location.hash;
    if (!hash) return;
    const targetId = decodeURIComponent(hash.slice(1));
    const timer = window.setTimeout(() => {
      document.getElementById(targetId)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 120);
    return () => window.clearTimeout(timer);
  }, [activeTab, brand?.id, searchParams]);

  useEffect(() => {
    if (!brandId) return;
    Promise.all([
      api.getBrand(brandId),
      api.getWorkspace().catch(() => null),
      api.getBillingSummary(brandId).catch(() => null),
    ]).then(([b, ws, bill]) => {
      setBrand(b);
      setWorkspace(ws);
      setBilling(bill);
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
    { id: 'profile',            label: 'Profile' },
    { id: 'integrations',       label: 'Integrations' },
    { id: 'products',           label: 'Products' },
    { id: 'audiences',          label: 'Audiences' },
    { id: 'guidelines',         label: 'Guidelines' },
    { id: 'brand-kit',          label: 'Creative Brief & Assets' },
    { id: 'project-management', label: 'Project Mgmt' },
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
            Brand profile, integrations, products, audiences, and documents.
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

      {billing && (
        <div className="admin-card" style={{ marginBottom: 16 }}>
          <div className="admin-card-title" style={{ marginBottom: 12 }}>AI Usage — this brand</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text2)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Tokens</div>
              <div style={{ fontSize: 22, fontWeight: 800 }}>{billing.total_tokens.toLocaleString()}</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text2)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Provider Cost</div>
              <div style={{ fontSize: 22, fontWeight: 800 }}>${billing.total_provider_cost.toFixed(4)}</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text2)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Billed (est.)</div>
              <div style={{ fontSize: 22, fontWeight: 800 }}>
                ${billing.total_sell_price.toFixed(4)}
              </div>
              {billing.total_provider_cost > 0 && (
                <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 2 }}>
                  {((billing.total_sell_price / billing.total_provider_cost - 1) * 100).toFixed(0)}% markup
                </div>
              )}
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text2)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Runs</div>
              <div style={{ fontSize: 22, fontWeight: 800 }}>
                {billing.successful_runs}
                <span style={{ fontSize: 13, fontWeight: 400, color: 'var(--text2)', marginLeft: 4 }}>/ {billing.total_runs}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="admin-card" style={{ padding: 0 }}>
        <div className="tabs" style={{ padding: '0 24px', margin: 0, borderRadius: '14px 14px 0 0' }}>
          {TABS.map(({ id, label }) => (
            <div
              key={id}
              className={`tab${activeTab === id ? ' active' : ''}`}
              onClick={() => {
                setActiveTab(id);
                const next = new URLSearchParams(searchParams);
                next.set('tab', id);
                setSearchParams(next);
              }}
            >
              {label}
            </div>
          ))}
        </div>
        <div style={{ padding: 24 }}>
          {activeTab === 'profile' && (
            <ProfileTab brand={brand} onUpdate={setBrand} />
          )}
          {activeTab === 'integrations' && brandId && (
            <IntegrationsTab brandId={brandId} />
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
            <BrandKitTab brandId={brand.id} brand={brand} />
          )}
          {activeTab === 'project-management' && (
            <ProjectManagementTab brand={brand} onUpdate={setBrand} />
          )}
        </div>
      </div>
    </div>
  );
}
