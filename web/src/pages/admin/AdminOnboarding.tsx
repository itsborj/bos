import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import type { BrandKitResponse, BrandResponse, IngestResponse, ProviderInfo, WorkspaceDocument } from '../../api/types';

type OnboardingNavState = {
  brand_id?: string;
  brand_name?: string;
};

// 'org'          — writing to workspace-level (brand_id=NULL)
// 'new_brand'    — creating a brand row first, then importing to it
// 'update_brand' — locked to an existing brand (always tied to its brand_id)
type ImportScope = 'org' | 'new_brand' | 'update_brand';

// UI step before the form is ready
type ScopeStep = 'loading' | 'org_or_brand' | 'select_target' | 'form';

export function AdminOnboarding() {
  const navigate = useNavigate();
  const location = useLocation();
  const navState = (location.state || {}) as OnboardingNavState;
  const navBrandId   = navState.brand_id;
  const navBrandName = navState.brand_name;

  // scope resolution
  const [scopeStep, setScopeStep]         = useState<ScopeStep>('loading');
  const [scope, setScope]                 = useState<ImportScope | null>(null);
  const [existingBrands, setExistingBrands] = useState<BrandResponse[]>([]);
  const [targetBrandId, setTargetBrandId] = useState<string | null>(navBrandId || null);
  const [targetBrandName, setTargetBrandName] = useState<string>(navBrandName || '');

  // "this is a brand, not org" sub-fields
  const [orgName, setOrgName]             = useState('');
  const [newBrandName, setNewBrandName]   = useState('');
  const [showBrandFields, setShowBrandFields] = useState(false);

  // "select existing brand" sub-state for select_target step
  const [selectedExisting, setSelectedExisting] = useState<string | null>(null);
  const [showNewBrandField, setShowNewBrandField] = useState(false);

  // form
  const [providers, setProviders]   = useState<ProviderInfo[]>([]);
  const [docText, setDocText]       = useState('');
  const [workspaceName, setWorkspaceName] = useState('');
  const [ingesting, setIngesting]   = useState(false);
  const [result, setResult]         = useState<IngestResponse | null>(null);
  const [brandKit, setBrandKit]     = useState<WorkspaceDocument | null>(null);
  const [kitBusy, setKitBusy]       = useState(false);
  const [kitCopied, setKitCopied]   = useState(false);
  const [error, setError]           = useState<string | null>(null);
  const [kitWarning, setKitWarning] = useState(false);

  useEffect(() => {
    api.getProviders().then(r => setProviders(r.providers)).catch(() => {});

    if (navBrandId) {
      // Update mode — locked to this brand, no scope negotiation
      setScope('update_brand');
      setScopeStep('form');
      // Check for existing brand kit so we can warn before overwrite
      api.getDocuments({ doc_type: 'campaign_brand_kit', brand_id: navBrandId })
        .then(docs => { if (docs.length > 0) setKitWarning(true); })
        .catch(() => {});
      api.getDocuments({ doc_type: 'campaign_brand_kit', brand_id: navBrandId })
        .then(docs => setBrandKit(docs[0] ?? null))
        .catch(() => {});
    } else {
      api.getBrands()
        .then(r => {
          if (r.brands.length > 0) {
            setExistingBrands(r.brands);
            setScopeStep('select_target');
          } else {
            setScopeStep('org_or_brand');
          }
        })
        .catch(() => setScopeStep('org_or_brand'));
    }
  }, [navBrandId]);

  // ── Scope step: org vs brand (first-time, no brands exist) ──────────────────

  function handleChooseOrg() {
    setScope('org');
    setScopeStep('form');
    // Check if workspace-level slot already has a kit
    api.getDocuments({ doc_type: 'campaign_brand_kit' })
      .then(docs => { if (docs.length > 0) setKitWarning(true); })
      .catch(() => {});
    api.getDocuments({ doc_type: 'campaign_brand_kit' })
      .then(docs => setBrandKit(docs[0] ?? null))
      .catch(() => {});
  }

  function handleChooseBrand() {
    setShowBrandFields(true);
  }

  function handleConfirmBrandScope() {
    if (!newBrandName.trim()) return;
    setScope('new_brand');
    setScopeStep('form');
  }

  // ── Scope step: select target (brands exist) ─────────────────────────────────

  function handleSelectExistingBrand(brand: BrandResponse) {
    setSelectedExisting(brand.id);
    setTargetBrandId(brand.id);
    setTargetBrandName(brand.name);
    setScope('update_brand');
    setScopeStep('form');
    api.getDocuments({ doc_type: 'campaign_brand_kit', brand_id: brand.id })
      .then(docs => { if (docs.length > 0) setKitWarning(true); })
      .catch(() => {});
    api.getDocuments({ doc_type: 'campaign_brand_kit', brand_id: brand.id })
      .then(docs => setBrandKit(docs[0] ?? null))
      .catch(() => {});
  }

  function handleSelectNewBrand() {
    setSelectedExisting(null);
    setShowNewBrandField(true);
  }

  function handleConfirmNewBrand() {
    if (!newBrandName.trim()) return;
    setScope('new_brand');
    setScopeStep('form');
  }

  // ── Form submission ──────────────────────────────────────────────────────────

  async function handleIngest(e: React.FormEvent) {
    e.preventDefault();
    if (!docText.trim()) return;
    setIngesting(true);
    setError(null);
    try {
      let effectiveBrandId: string | undefined = undefined;

      if (scope === 'update_brand' && targetBrandId) {
        effectiveBrandId = targetBrandId;
      } else if (scope === 'new_brand') {
        if (orgName.trim()) {
          await api.putWorkspace(orgName.trim());
        }
        const newBrand = await api.createBrand({ name: newBrandName.trim() });
        effectiveBrandId = newBrand.id;
        setTargetBrandId(newBrand.id);
        setTargetBrandName(newBrand.name);
      }
      // scope === 'org': effectiveBrandId stays undefined → workspace-level

      const res = await api.ingestBrandDoc(
        docText.trim(),
        scope === 'org' ? (workspaceName.trim() || undefined) : undefined,
        effectiveBrandId,
      );
      setResult(res);
      setBrandKit(null);
      setKitWarning(false);
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
      const effectiveBrandId = scope === 'update_brand' || scope === 'new_brand' ? (targetBrandId || undefined) : undefined;
      const res: BrandKitResponse = await api.generateBrandKit(additionalContext, effectiveBrandId);
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

  const byokCount = providers.filter(p => p.has_byok_key).length;

  // ── Result view (post-ingest) ────────────────────────────────────────────────

  if (result) {
    const { workspace } = result;
    const profile = result.profile || workspace.brand || {};
    const isBrandScope = scope === 'update_brand' || scope === 'new_brand';
    const visibleProducts = isBrandScope
      ? workspace.products.filter(p => p.brand_id === targetBrandId)
      : workspace.products.filter(p => !p.brand_id);
    const visibleAudiences = isBrandScope
      ? workspace.audiences.filter(a => a.brand_id === targetBrandId)
      : workspace.audiences.filter(a => !a.brand_id);

    return (
      <div className="admin-page">
        <div className="admin-page-header">
          <div>
            <div className="admin-page-title">Brand Brief Processed</div>
            <div className="admin-page-subtitle">
              {scope === 'new_brand'
                ? `${result.brand_name} created and populated from your document`
                : isBrandScope
                  ? `${targetBrandName} updated from your document`
                  : 'Workspace populated from your document'}
            </div>
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
              <div style={{ maxHeight: 180, overflow: 'auto', whiteSpace: 'pre-wrap', fontSize: 12, lineHeight: 1.6, border: '.5px solid var(--border)', borderRadius: 0, padding: 12, marginBottom: 12 }}>
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
          {error && <div style={{ fontSize: 12, color: 'var(--error)', marginTop: 8 }}>{error}</div>}
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <button
            className="btn btn-dark"
            onClick={() => {
              if (isBrandScope && targetBrandId) navigate(`/admin/brands/${targetBrandId}`);
              else navigate('/admin/workspace');
            }}
          >
            {isBrandScope ? 'Review Brand →' : 'Review Workspace →'}
          </button>
          <button className="btn btn-ghost" onClick={() => { setResult(null); setDocText(''); setWorkspaceName(''); }}>
            Submit Another Document
          </button>
        </div>
      </div>
    );
  }

  // ── Loading ──────────────────────────────────────────────────────────────────

  if (scopeStep === 'loading') {
    return (
      <div className="admin-page">
        <div className="loading-full"><span className="spinner" /></div>
      </div>
    );
  }

  // ── Step 0A: First import — is this your Organization or a Brand? ─────────────

  if (scopeStep === 'org_or_brand') {
    return (
      <div className="admin-page">
        <div className="admin-page-header">
          <div>
            <div className="admin-page-title">Set Up BOS</div>
            <div className="admin-page-subtitle">Tell us what you're setting up so we can scope it correctly.</div>
          </div>
        </div>

        <div className="admin-card">
          <div className="admin-card-title">What is this first brief for?</div>
          <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 20 }}>
            Choose correctly — this determines whether the brief is saved at the organization level or as a brand within your organization.
          </div>

          {!showBrandFields ? (
            <div style={{ display: 'grid', gap: 12 }}>
              <button
                className="btn btn-secondary"
                style={{ textAlign: 'left', padding: '14px 18px', height: 'auto', display: 'block' }}
                onClick={handleChooseOrg}
              >
                <div style={{ fontWeight: 700, marginBottom: 2 }}>This is my Organization</div>
                <div style={{ fontSize: 12, fontWeight: 400, opacity: 0.8 }}>
                  The brief describes the business as a whole. BOS treats this as your organization profile.
                </div>
              </button>
              <button
                className="btn btn-secondary"
                style={{ textAlign: 'left', padding: '14px 18px', height: 'auto', display: 'block' }}
                onClick={handleChooseBrand}
              >
                <div style={{ fontWeight: 700, marginBottom: 2 }}>This is a Brand within my Organization</div>
                <div style={{ fontSize: 12, fontWeight: 400, opacity: 0.8 }}>
                  The brief describes one brand or client. You'll name your organization first, then this becomes a sub-brand.
                </div>
              </button>
            </div>
          ) : (
            <div>
              <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 16 }}>
                Name your organization (the parent), then name this brand.
              </div>
              <div className="form-group">
                <label className="label">Organization Name <span className="label-hint">required</span></label>
                <input
                  className="input"
                  value={orgName}
                  onChange={e => setOrgName(e.target.value)}
                  placeholder="e.g. Acme Agency"
                />
              </div>
              <div className="form-group">
                <label className="label">Brand Name <span className="label-hint">required — will be created as a new brand</span></label>
                <input
                  className="input"
                  value={newBrandName}
                  onChange={e => setNewBrandName(e.target.value)}
                  placeholder="e.g. Klaroha"
                />
              </div>
              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  className="btn btn-dark"
                  onClick={handleConfirmBrandScope}
                  disabled={!newBrandName.trim() || !orgName.trim()}
                >
                  Continue — Import Brief for {newBrandName.trim() || 'Brand'}
                </button>
                <button className="btn btn-ghost" onClick={() => setShowBrandFields(false)}>← Back</button>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Step 0B: Brands exist — select target ────────────────────────────────────

  if (scopeStep === 'select_target') {
    return (
      <div className="admin-page">
        <div className="admin-page-header">
          <div>
            <div className="admin-page-title">Import Brand Brief</div>
            <div className="admin-page-subtitle">Choose which brand you're importing for, or create a new one.</div>
          </div>
        </div>

        <div className="admin-card">
          <div className="admin-card-title">Who is this brief for?</div>
          <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 16 }}>
            Each import is scoped to a specific brand. Select an existing brand to update its brief, or create a new one.
          </div>

          <div style={{ display: 'grid', gap: 8, marginBottom: 16 }}>
            {existingBrands.map(brand => (
              <button
                key={brand.id}
                className={`btn ${selectedExisting === brand.id ? 'btn-secondary' : 'btn-ghost'}`}
                style={{ textAlign: 'left', padding: '12px 16px', height: 'auto', display: 'block' }}
                onClick={() => handleSelectExistingBrand(brand)}
              >
                <div style={{ fontWeight: 700 }}>{brand.name}</div>
                {brand.voice && <div style={{ fontSize: 12, fontWeight: 400, opacity: 0.7 }}>Voice: {brand.voice}</div>}
              </button>
            ))}
          </div>

          <div style={{ borderTop: '1px solid var(--border)', paddingTop: 16 }}>
            {!showNewBrandField ? (
              <button className="btn btn-secondary" onClick={handleSelectNewBrand}>
                + Import for a new brand
              </button>
            ) : (
              <div>
                <div className="form-group">
                  <label className="label">New Brand Name <span className="label-hint">required</span></label>
                  <input
                    className="input"
                    value={newBrandName}
                    onChange={e => setNewBrandName(e.target.value)}
                    placeholder="e.g. Nexus Labs"
                    autoFocus
                  />
                </div>
                <div style={{ display: 'flex', gap: 10 }}>
                  <button
                    className="btn btn-dark"
                    onClick={handleConfirmNewBrand}
                    disabled={!newBrandName.trim()}
                  >
                    Continue — Import for {newBrandName.trim() || 'New Brand'}
                  </button>
                  <button className="btn btn-ghost" onClick={() => { setShowNewBrandField(false); setNewBrandName(''); }}>
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ── Form ─────────────────────────────────────────────────────────────────────

  const isUpdateMode = scope === 'update_brand';
  const isNewBrand   = scope === 'new_brand';
  const isOrg        = scope === 'org';

  const scopeLabel = isUpdateMode
    ? targetBrandName
    : isNewBrand
      ? newBrandName
      : 'Organization';

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">
            {isUpdateMode ? `Update Brief — ${scopeLabel}` : isNewBrand ? `Import Brief — ${scopeLabel}` : 'Organization Setup'}
          </div>
          <div className="admin-page-subtitle">
            {isUpdateMode
              ? `Updating profile, products, audiences, and Brand Kit for ${scopeLabel}. This brief is locked to this brand.`
              : isNewBrand
                ? `Creating ${scopeLabel} as a new brand within your organization and importing its brief.`
                : 'Guided setup: import the organization brief, generate the required Campaign Brand Kit, then optionally add BYOK provider access.'}
          </div>
        </div>
        {!isUpdateMode && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => { setScopeStep(existingBrands.length > 0 ? 'select_target' : 'org_or_brand'); setScope(null); setError(null); setKitWarning(false); }}
          >
            ← Change target
          </button>
        )}
      </div>

      {/* Scope lock badge for update mode */}
      {isUpdateMode && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px', background: 'var(--ivory)', border: '.5px solid var(--border-warm)', borderRadius: 0, fontSize: 13 }}>
          <span className="badge badge-info">Locked scope</span>
          <span>This import will only update <strong>{scopeLabel}</strong>. It cannot write to any other brand or the organization profile.</span>
        </div>
      )}

      {/* Existing brand kit warning */}
      {kitWarning && (
        <div style={{ padding: '10px 14px', background: 'var(--linen)', border: '.5px solid var(--border-warm)', borderRadius: 0, fontSize: 13, color: 'var(--ink-body)' }}>
          <strong>Existing brand kit found</strong> — importing this brief will replace the current profile, products, and audiences for {scopeLabel}. The existing Campaign Brand Kit will need to be regenerated after import.
        </div>
      )}

      {/* Step 1 — Brand Brief */}
      <div className="admin-card" style={{ marginBottom: 16 }}>
        <div className="admin-card-title">Step 1 — Import Brand Brief</div>
        <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 16 }}>
          Paste any brand document — a brief, one-pager, deck notes, or description. BOS will extract brand voice,
          tone, values, products, and audiences automatically, then write them into{' '}
          {isUpdateMode ? `the ${scopeLabel} brand record` : isNewBrand ? `the new ${scopeLabel} brand` : 'the organization profile'}.
        </div>
        <form onSubmit={handleIngest}>
          {isOrg && (
            <div className="form-group">
              <label className="label">
                Organization Name Override <span className="label-hint">optional — leave blank to extract from document</span>
              </label>
              <input
                className="input"
                value={workspaceName}
                onChange={e => setWorkspaceName(e.target.value)}
                placeholder="e.g. Acme Agency"
                disabled={ingesting}
              />
            </div>
          )}
          {isUpdateMode && (
            <div className="form-group">
              <label className="label">
                Brand Name Override <span className="label-hint">optional — leave blank to let the brief rename {scopeLabel}</span>
              </label>
              <input
                className="input"
                value={workspaceName}
                onChange={e => setWorkspaceName(e.target.value)}
                placeholder={`Current: ${scopeLabel}; leave blank to keep or extract new name`}
                disabled={ingesting}
              />
            </div>
          )}
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
            <div style={{ padding: '8px 12px', background: 'var(--ivory)', border: '.5px solid var(--error)', borderRadius: 0, fontSize: 13, color: 'var(--error)', marginBottom: 12 }}>
              {error}
            </div>
          )}
          <button
            type="submit"
            className="btn btn-dark"
            disabled={ingesting || !docText.trim()}
          >
            {ingesting
              ? 'Processing…'
              : isUpdateMode
                ? `Update ${scopeLabel} Profile`
                : isNewBrand
                  ? `Create ${scopeLabel} and Import Brief`
                  : 'Create Organization Profile'}
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
          Required before launching the first campaign. It stores the basic color palette, tone of voice, typography, campaign components, and platform consistency rules as a tagged document.
        </div>
        {brandKit ? (
          <div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }}>
              <span style={{ fontSize: 13 }}><strong>{brandKit.title}</strong></span>
              <span className={brandKit.status === 'approved' ? 'badge badge-success' : 'badge badge-warning'}>
                {brandKit.status}
              </span>
              <button className="btn btn-ghost btn-sm" onClick={handleCopyBrandKit}>
                {kitCopied ? 'Copied' : 'Copy Markdown'}
              </button>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => (isUpdateMode || isNewBrand) && targetBrandId ? navigate(`/admin/brands/${targetBrandId}`) : navigate('/admin/workspace')}
              >
                {(isUpdateMode || isNewBrand) && targetBrandId ? 'Open Brand →' : 'Open in Workspace →'}
              </button>
              {brandKit.status !== 'approved' && (
                <button className="btn btn-dark btn-sm" onClick={handleApproveBrandKit} disabled={kitBusy}>
                  {kitBusy ? 'Approving…' : 'Approve'}
                </button>
              )}
            </div>
            <div style={{ maxHeight: 420, overflow: 'auto', whiteSpace: 'pre-wrap', fontSize: 12, lineHeight: 1.6, border: '.5px solid var(--border)', borderRadius: 0, padding: 12, background: 'var(--ivory)' }}>
              {brandKit.content_markdown}
            </div>
          </div>
        ) : (
          <button className="btn btn-dark btn-sm" onClick={() => handleGenerateBrandKit()} disabled={kitBusy}>
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
          Bring-your-own-key is optional. Add BYOK if you want runs billed directly to your provider account.
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
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => navigate('/admin/providers', {
            state: (isUpdateMode || isNewBrand) && targetBrandId
              ? { brand_id: targetBrandId, brand_name: targetBrandName || newBrandName }
              : undefined,
          })}
        >
          Manage BYOK / Provider Access →
        </button>
      </div>
    </div>
  );
}
