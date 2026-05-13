import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import type { BrandKitResponse, IngestResponse, ProviderInfo, WorkspaceDocument } from '../../api/types';

type OnboardingNavState = {
  brand_id?: string;
  brand_name?: string;
};

export function AdminOnboarding() {
  const navigate = useNavigate();
  const location = useLocation();
  const navState = (location.state || {}) as OnboardingNavState;
  const selectedBrandId = navState.brand_id;
  const selectedBrandName = navState.brand_name;
  const [providers, setProviders]       = useState<ProviderInfo[]>([]);
  const [docText, setDocText]           = useState('');
  const [workspaceName, setWorkspaceName] = useState('');
  const [ingesting, setIngesting]       = useState(false);
  const [result, setResult]             = useState<IngestResponse | null>(null);
  const [brandKit, setBrandKit]         = useState<WorkspaceDocument | null>(null);
  const [kitBusy, setKitBusy]           = useState(false);
  const [kitCopied, setKitCopied]       = useState(false);
  const [error, setError]               = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.getProviders().then(r => setProviders(r.providers)).catch(() => {}),
      api.getDocuments({ doc_type: 'campaign_brand_kit', brand_id: selectedBrandId })
        .then(docs => setBrandKit(docs[0] ?? null))
        .catch(() => {}),
    ]);
  }, [selectedBrandId]);

  const byokCount = providers.filter(p => p.has_byok_key).length;

  async function handleIngest(e: React.FormEvent) {
    e.preventDefault();
    if (!docText.trim()) return;
    setIngesting(true);
    setError(null);
    try {
      const res = await api.ingestBrandDoc(docText.trim(), workspaceName.trim() || undefined, selectedBrandId);
      setResult(res);
      setBrandKit(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Ingestion failed');
    } finally {
      setIngesting(false);
    }
  }

  async function handleGenerateBrandKit(additionalContext?: string) {
    setKitBusy(true);
    setError(null);
    try {
      const res: BrandKitResponse = await api.generateBrandKit(additionalContext, selectedBrandId);
      setBrandKit(res.document);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Brand Kit generation failed');
    } finally {
      setKitBusy(false);
    }
  }

  async function handleApproveBrandKit() {
    if (!brandKit) return;
    setKitBusy(true);
    setError(null);
    try {
      const updated = await api.approveDocument(brandKit.id);
      setBrandKit(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Brand Kit approval failed');
    } finally {
      setKitBusy(false);
    }
  }

  async function handleCopyBrandKit() {
    if (!brandKit) return;
    await navigator.clipboard.writeText(brandKit.content_markdown);
    setKitCopied(true);
    setTimeout(() => setKitCopied(false), 1800);
  }

  if (result) {
    const { workspace } = result;
    const profile = result.profile || workspace.brand || {};
    const visibleProducts = selectedBrandId
      ? workspace.products.filter(p => p.brand_id === selectedBrandId)
      : workspace.products.filter(p => !p.brand_id);
    const visibleAudiences = selectedBrandId
      ? workspace.audiences.filter(a => a.brand_id === selectedBrandId)
      : workspace.audiences.filter(a => !a.brand_id);
    return (
      <div className="admin-page">
        <div className="admin-page-header">
          <div>
            <div className="admin-page-title">Brand Brief Processed</div>
            <div className="admin-page-subtitle">{selectedBrandId ? 'Brand record updated from your document' : 'Workspace populated from your document'}</div>
          </div>
        </div>

        <div className="admin-card" style={{ marginBottom: 16 }}>
          <div className="admin-card-title" style={{ color: 'var(--success, #16a34a)' }}>
            ✓ {result.brand_name} is ready
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginTop: 16 }}>
            <div>
              <div className="admin-stat-label">Brand Voice</div>
              <div style={{ fontSize: 13, marginTop: 4 }}>{profile.voice || '—'}</div>
              <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 2 }}>
                Tone: {profile.tone || '—'}
              </div>
              {profile.values?.length ? (
                <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 2 }}>
                  Values: {profile.values.join(', ')}
                </div>
              ) : null}
            </div>
            <div>
              <div className="admin-stat-label">Products</div>
              {visibleProducts.map(p => (
                <div key={p.id} style={{ fontSize: 13, marginTop: 4 }}>
                  <strong>{p.name}</strong>
                  {p.tagline && <div style={{ fontSize: 12, color: 'var(--text2)' }}>{p.tagline}</div>}
                </div>
              ))}
              {visibleProducts.length === 0 && <div style={{ fontSize: 13, color: 'var(--text2)', marginTop: 4 }}>None extracted</div>}
            </div>
            <div>
              <div className="admin-stat-label">Audiences</div>
              {visibleAudiences.map(a => (
                <div key={a.id} style={{ fontSize: 13, marginTop: 4 }}>
                  <strong>{a.name}</strong>
                  {a.demographics && <div style={{ fontSize: 12, color: 'var(--text2)' }}>{a.demographics}</div>}
                </div>
              ))}
              {visibleAudiences.length === 0 && <div style={{ fontSize: 13, color: 'var(--text2)', marginTop: 4 }}>None extracted</div>}
            </div>
          </div>
        </div>

        <div className="admin-card" style={{ marginBottom: 16 }}>
          <div className="admin-card-title">Step 2 — Campaign Brand Kit</div>
          <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 12 }}>
            Required before the first campaign. This creates the minimum color, voice, typography, CTA, component, and platform rules needed for cohesive marketing.
          </div>
          {brandKit ? (
            <div>
              <div style={{ fontSize: 13, marginBottom: 8 }}>
                <strong>{brandKit.title}</strong> · {brandKit.status}
              </div>
              <div style={{ maxHeight: 180, overflow: 'auto', whiteSpace: 'pre-wrap', fontSize: 12, lineHeight: 1.6, border: '1px solid var(--border)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
                {brandKit.content_markdown}
              </div>
              {brandKit.status !== 'approved' && (
                <button className="btn btn-dark" onClick={handleApproveBrandKit} disabled={kitBusy}>
                  {kitBusy ? 'Approving…' : 'Approve Campaign Brand Kit'}
                </button>
              )}
            </div>
          ) : (
            <button className="btn btn-dark" onClick={() => handleGenerateBrandKit(docText)} disabled={kitBusy}>
              {kitBusy ? 'Generating…' : 'Generate Campaign Brand Kit'}
            </button>
          )}
          {error && <div style={{ fontSize: 12, color: '#dc2626', marginTop: 8 }}>{error}</div>}
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-dark" onClick={() => selectedBrandId ? navigate(`/admin/brands/${selectedBrandId}`) : navigate('/admin/workspace')}>
            {selectedBrandId ? 'Review Brand →' : 'Review Workspace →'}
          </button>
          <button className="btn btn-secondary" onClick={() => { setResult(null); setDocText(''); setWorkspaceName(''); }}>
            Submit Another Document
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">{selectedBrandId ? 'Update Brand Brief' : 'New Workspace Setup'}</div>
          <div className="admin-page-subtitle">
            {selectedBrandId
              ? `Import a fresh brief for ${selectedBrandName || 'this brand'} and update its profile, products, audiences, and Brand Kit.`
              : 'Guided setup: import the brand brief, generate the required Campaign Brand Kit, then optionally add BYOK provider access.'}
          </div>
        </div>
      </div>

      {/* Step 1 — Brand Brief */}
      <div className="admin-card" style={{ marginBottom: 16 }}>
        <div className="admin-card-title">Step 1 — Import Brand Brief</div>
        <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 16 }}>
          Paste any brand document — a brief, one-pager, deck notes, or description. BOS will extract brand voice,
          tone, values, products, and audiences automatically, then write them into {selectedBrandId ? 'the selected brand record' : 'the workspace profile'} for review.
        </div>
        <form onSubmit={handleIngest}>
          <div className="form-group">
            <label className="label">
              Brand / Project Name Override <span className="label-hint">optional — leave blank to extract from document</span>
            </label>
            <input
              className="input"
              value={workspaceName}
              onChange={e => setWorkspaceName(e.target.value)}
              placeholder={selectedBrandName ? `Current: ${selectedBrandName}; leave blank to let the brief rename it` : 'e.g. Nexus Labs'}
              disabled={ingesting}
            />
          </div>
          <div className="form-group">
            <label className="label">Brand Document</label>
            <textarea
              className="input"
              style={{ minHeight: 220, resize: 'vertical', fontFamily: 'var(--mono)', fontSize: 12 }}
              value={docText}
              onChange={e => setDocText(e.target.value)}
              placeholder="Paste your brand brief, company description, or any document containing brand, product, and audience information..."
              disabled={ingesting}
            />
          </div>
          {error && (
            <div style={{ padding: '8px 12px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 6, fontSize: 13, color: '#dc2626', marginBottom: 12 }}>
              {error}
            </div>
          )}
          <button
            type="submit"
            className="btn btn-dark"
            disabled={ingesting || !docText.trim()}
          >
            {ingesting ? 'Processing…' : selectedBrandId ? 'Update Brand Profile' : 'Create Workspace Profile'}
          </button>
        </form>
      </div>

      {/* Step 2 — Campaign Brand Kit */}
      <div className="admin-card" style={{ marginBottom: 16 }}>
        <div className="admin-card-title">
          Step 2 — Generate Campaign Brand Kit
          <span style={{ fontSize: 12, fontWeight: 400, color: brandKit?.status === 'approved' ? 'var(--success, #16a34a)' : 'var(--text2)' }}>
            {brandKit ? `  ${brandKit.status}` : '  Required after brand profile'}
          </span>
        </div>
        <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 12 }}>
          Required before launching the first campaign. It stores the basic color palette, tone of voice, typography, campaign components, and platform consistency rules as a tagged PostgreSQL document.
        </div>
        {brandKit ? (
          <div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }}>
              <span style={{ fontSize: 13 }}><strong>{brandKit.title}</strong></span>
              <span className={brandKit.status === 'approved' ? 'badge badge-success' : 'badge badge-warning'}>
                {brandKit.status}
              </span>
              <button className="btn btn-secondary btn-sm" onClick={handleCopyBrandKit}>
                {kitCopied ? 'Copied' : 'Copy Markdown'}
              </button>
              <button className="btn btn-secondary btn-sm" onClick={() => selectedBrandId ? navigate(`/admin/brands/${selectedBrandId}`) : navigate('/admin/workspace')}>
                {selectedBrandId ? 'Open Brand →' : 'Open in Workspace →'}
              </button>
              {brandKit.status !== 'approved' && (
                <button className="btn btn-dark btn-sm" onClick={handleApproveBrandKit} disabled={kitBusy}>
                  {kitBusy ? 'Approving…' : 'Approve'}
                </button>
              )}
            </div>
            <div style={{ maxHeight: 420, overflow: 'auto', whiteSpace: 'pre-wrap', fontSize: 12, lineHeight: 1.6, border: '1px solid var(--border)', borderRadius: 8, padding: 12, background: '#f9fafb' }}>
              {brandKit.content_markdown}
            </div>
          </div>
        ) : (
          <button className="btn btn-secondary btn-sm" onClick={() => handleGenerateBrandKit()} disabled={kitBusy}>
            {kitBusy ? 'Generating…' : 'Generate Campaign Brand Kit'}
          </button>
        )}
      </div>

      {/* Step 3 — Optional Provider Access */}
      <div className="admin-card">
        <div className="admin-card-title">
          Step 3 — Optional Provider Access / BYOK
          <span style={{ fontSize: 12, fontWeight: 400, color: byokCount > 0 ? 'var(--success, #16a34a)' : 'var(--text2)' }}>
            {byokCount > 0 ? `  ✓ ${byokCount} BYOK provider${byokCount > 1 ? 's' : ''} connected` : '  Optional'}
          </span>
        </div>
        <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 12 }}>
          Bring-your-own-key is optional. Add BYOK if you want runs billed directly to your provider account; otherwise the workspace can use connected login/platform access where available.
        </div>
        <div style={{ marginBottom: 12 }}>
          {providers.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--text2)' }}>Loading providers…</div>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Provider</th><th>Status</th><th>Mode</th></tr></thead>
                <tbody>
                  {providers.map(p => {
                    const connected = p.has_platform_key || p.connected;
                    const mode = p.auth_mode === 'oauth'
                      ? 'Login'
                      : p.has_byok_key
                        ? 'BYOK API key'
                        : p.has_platform_key
                          ? 'Platform'
                          : '—';
                    return (
                      <tr key={p.provider}>
                        <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{p.provider}</td>
                        <td>
                          {connected
                            ? <span className="badge badge-success">Available</span>
                            : <span className="badge badge-warning">Not connected</span>}
                        </td>
                        <td style={{ fontSize: 12, color: 'var(--text2)' }}>{mode}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <button className="btn btn-secondary btn-sm" onClick={() => navigate('/admin/providers', { state: selectedBrandId ? { brand_id: selectedBrandId, brand_name: selectedBrandName } : undefined })}>
          Manage BYOK / Provider Access →
        </button>
      </div>
    </div>
  );
}
