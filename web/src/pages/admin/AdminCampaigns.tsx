import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { api } from '../../api/client';
import type { CampaignOut, CampaignSheetResponse, CampaignRowOut } from '../../api/types';
import { useActiveContext } from '../../context/ActiveContext';
import type { ActiveBrand } from '../../context/UIContext';

const STATUS_META: Record<string, { label: string; cls: string }> = {
  draft:    { label: 'Draft',    cls: 'badge-muted' },
  active:   { label: 'Active',   cls: 'badge-success' },
  complete: { label: 'History',  cls: 'badge-info' },
  archived: { label: 'Archived', cls: 'badge-muted' },
};

const SIGNAL_CLS: Record<string, string> = {
  active_context: 'badge-success',
  ready: 'badge-success',
  has_results: 'badge-success',
  history: 'badge-muted',
  archived: 'badge-muted',
  needs_brand: 'badge-warning',
  needs_message_focus: 'badge-warning',
  needs_approval: 'badge-warning',
  draft: 'badge-muted',
};

type CampaignNavState = { brand_id?: string; brand_name?: string } | null;

function statusMeta(status: string) {
  return STATUS_META[status] ?? { label: status, cls: 'badge-muted' };
}

function signalCls(state?: string): string {
  return (state && SIGNAL_CLS[state]) || 'badge-muted';
}

function nextStatus(current: string): string | null {
  if (current === 'draft') return 'active';
  if (current === 'active') return 'complete';
  if (current === 'complete') return 'archived';
  return null;
}

function statusActionLabel(next: string): string {
  if (next === 'active') return 'Start tracking';
  if (next === 'complete') return 'Mark complete';
  if (next === 'archived') return 'Archive';
  return `Move to ${statusMeta(next).label}`;
}

function statusChangeConfirmation(current: string, next: string, name: string): string | null {
  if (current === 'active' && next === 'complete') {
    return `Mark “${name}” complete?\n\nCompleted campaigns move to History and stop being live CMO context. Use this only when execution is actually finished.`;
  }
  if (current === 'complete' && next === 'archived') {
    return `Archive “${name}”?\n\nArchived campaigns remain historical records and are not live CMO context.`;
  }
  return null;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const d = Math.floor(diff / 86400000);
  if (d < 1) return 'Today';
  if (d === 1) return 'Yesterday';
  if (d < 30) return `${d}d ago`;
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function textValue(value: unknown): string {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    return textValue(obj.value ?? obj.label ?? obj.summary ?? obj.name ?? '');
  }
  return '';
}

function rowPayload(row: CampaignRowOut): Record<string, unknown> {
  return row.raw_payload && typeof row.raw_payload === 'object' ? row.raw_payload : {};
}

function pushUnique(target: string[], value: unknown, limit = 6) {
  const text = textValue(value).trim();
  if (!text || target.includes(text) || target.length >= limit) return;
  target.push(text);
}

function collectRowPayloadValues(rows: CampaignRowOut[], keys: string[], limit = 6): string[] {
  const out: string[] = [];
  for (const row of rows) {
    const payload = rowPayload(row);
    for (const key of keys) {
      const value = payload[key];
      if (Array.isArray(value)) {
        for (const item of value) {
          if (typeof item === 'object' && item) {
            pushUnique(out, (item as Record<string, unknown>).value ?? (item as Record<string, unknown>).name ?? (item as Record<string, unknown>).label, limit);
          } else {
            pushUnique(out, item, limit);
          }
        }
      } else if (typeof value === 'object' && value) {
        const rec = value as Record<string, unknown>;
        pushUnique(out, rec.value ?? rec.name ?? rec.label ?? rec.summary, limit);
      } else {
        pushUnique(out, value, limit);
      }
      if (out.length >= limit) return out;
    }
  }
  return out;
}

function strategyRow(rows: CampaignRowOut[]): CampaignRowOut | undefined {
  return rows.find(row => row.distribution_channel === 'campaign_strategy' || row.channel_role === 'strategy');
}

function deriveCampaignOverview(sheet: CampaignSheetResponse, campaign: CampaignOut, brandName?: string | null) {
  const rows = sheet.rows || [];
  const seedRow = strategyRow(rows) || rows[0];
  const payload = seedRow ? rowPayload(seedRow) : {};
  const intent = textValue(payload.initial_intent) || textValue(seedRow?.planned_activity);
  const objective = textValue(payload.objective) || textValue(payload.business_objective) || textValue(payload.goal) || intent;
  const messageFocus = textValue(payload.message_focus) || textValue(payload.message_angle) || campaign.message_angle;
  const changed = rows.map(row => textValue(row.what_changed)).filter(Boolean).slice(0, 5);
  const needs = rows.flatMap(row => ([
    row.blocker ? `Blocker — ${row.blocker}` : '',
    row.decision_needed ? `Decision — ${row.decision_needed}` : '',
    row.owner && row.next_action ? `${row.owner} — ${row.next_action}` : '',
  ].filter(Boolean))).slice(0, 5);
  const actors = collectRowPayloadValues(rows, ['actors', 'audiences', 'audience', 'target_audience'], 6);
  const offers = collectRowPayloadValues(rows, ['offers', 'offer', 'product', 'product_name'], 3);
  const next = textValue(seedRow?.next_action) || textValue(rows.find(row => row.next_action)?.next_action) || 'Confirm the next campaign action.';
  return {
    campaign: {
      id: campaign.id,
      name: campaign.name,
      status: campaign.status,
      brand_name: brandName || null,
    },
    intent,
    objective,
    messageFocus,
    changed,
    needs,
    actors,
    offers,
    next,
    sheetRows: rows,
  };
}

export function AdminCampaigns() {
  const location = useLocation();
  const navState = location.state as CampaignNavState;
  const { activeBrand, setActiveBrand, activeCampaign, setActiveCampaign, brands } = useActiveContext();
  const [campaigns, setCampaigns] = useState<CampaignOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [creatingForBrand, setCreatingForBrand] = useState<ActiveBrand | null>(null);
  const [newIntent, setNewIntent] = useState('');
  const [saving, setSaving] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [overviewSheet, setOverviewSheet] = useState<CampaignSheetResponse | null>(null);
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [reviewSheet, setReviewSheet] = useState<CampaignSheetResponse | null>(null);

  useEffect(() => {
    if (navState?.brand_id && navState?.brand_name) {
      setActiveBrand({ id: navState.brand_id, name: navState.brand_name });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navState?.brand_id, navState?.brand_name]);

  useEffect(() => {
    // Guard against out-of-order responses: an unscoped ("All brands") fetch
    // can be slower than a brand-scoped one issued right after it (more rows,
    // more per-row signal queries), so a naive .then(setCampaigns) can let the
    // slower, stale response clobber the newer one. Every other async effect
    // in this file already follows this cancelled-guard pattern.
    let cancelled = false;
    setLoading(true);
    api.listCampaigns(activeBrand?.id ?? null)
      .then(res => { if (!cancelled) setCampaigns(res); })
      .catch(() => { if (!cancelled) setError('Could not load campaigns.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [activeBrand?.id]);

  useEffect(() => {
    let cancelled = false;
    setOverviewSheet(null);
    if (!activeCampaign?.id) return;
    api.getCampaignSheet(activeCampaign.id)
      .then(res => { if (!cancelled) setOverviewSheet(res); })
      .catch(() => { if (!cancelled) setOverviewSheet(null); });
    return () => { cancelled = true; };
  }, [activeCampaign?.id]);

  useEffect(() => {
    let cancelled = false;
    setReviewSheet(null);
    if (!reviewingId) return;
    api.getCampaignSheet(reviewingId)
      .then(res => { if (!cancelled) setReviewSheet(res); })
      .catch(() => { if (!cancelled) setReviewSheet(null); });
    return () => { cancelled = true; };
  }, [reviewingId]);

  useEffect(() => {
    setReviewingId(null);
  }, [activeBrand?.id]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const intent = newIntent.trim();
    if (!intent || !creatingForBrand) return;
    const name = intent.split('\n')[0].trim().slice(0, 120) || 'Untitled Campaign';
    setSaving(true);
    setError(null);
    try {
      const created = await api.createCampaign({
        name,
        status: 'active',
        brand_id: creatingForBrand.id,
        campaign_json: { initial_intent: intent },
      });
      setCampaigns(prev => [created, ...prev]);
      setActiveBrand(creatingForBrand);
      setActiveCampaign({ id: created.id, name: created.name, brand_id: created.brand_id ?? null, status: created.status });
      setNewIntent('');
      setCreatingForBrand(null);
    } catch {
      setError('Failed to create campaign.');
    } finally {
      setSaving(false);
    }
  }

  async function handleAdvance(campaign: CampaignOut) {
    const next = nextStatus(campaign.status);
    if (!next) return;
    const confirmation = statusChangeConfirmation(campaign.status, next, campaign.name);
    if (confirmation && !window.confirm(confirmation)) return;
    setUpdatingId(campaign.id);
    try {
      const updated = await api.updateCampaign(campaign.id, {
        status: next,
        confirm_status_change: !!confirmation,
      });
      setCampaigns(prev => prev.map(c => c.id === campaign.id ? updated : c));
      if (activeCampaign?.id === campaign.id && updated.status !== 'active') {
        setActiveCampaign(null);
      }
    } catch {
      setError('Failed to update status.');
    } finally {
      setUpdatingId(null);
    }
  }

  async function handleDelete(campaign: CampaignOut) {
    if (!['draft', 'archived'].includes(campaign.status)) {
      setError('Only draft or archived campaigns can be deleted. Complete/archive campaign history first.');
      return;
    }
    const ok = window.confirm(`Delete “${campaign.name}”?\n\nThis permanently removes the campaign record. CMO chat cannot delete campaigns.`);
    if (!ok) return;
    setDeletingId(campaign.id);
    setError(null);
    try {
      await api.deleteCampaign(campaign.id);
      setCampaigns(prev => prev.filter(c => c.id !== campaign.id));
      if (activeCampaign?.id === campaign.id) setActiveCampaign(null);
      if (reviewingId === campaign.id) setReviewingId(null);
    } catch {
      setError('Failed to delete campaign. Only draft or archived campaigns can be deleted.');
    } finally {
      setDeletingId(null);
    }
  }

  function handleBrandFilterChange(brandId: string) {
    const selected = brands.find(brand => brand.id === brandId);
    setActiveBrand(selected ? { id: selected.id, name: selected.name } : null);
    if (!selected || !activeCampaign?.brand_id || activeCampaign.brand_id !== selected.id) {
      setActiveCampaign(null);
    }
  }

  function handleUseCampaign(campaign: CampaignOut) {
    const brand = brands.find(b => b.id === campaign.brand_id);
    if (brand) setActiveBrand({ id: brand.id, name: brand.name });
    if (campaign.status !== 'active') return;
    setActiveCampaign({ id: campaign.id, name: campaign.name, brand_id: campaign.brand_id ?? null, status: campaign.status });
  }

  function handleReview(campaign: CampaignOut) {
    setReviewingId(campaign.id);
  }

  async function handleResume(campaign: CampaignOut) {
    const brand = brands.find(b => b.id === campaign.brand_id) || activeBrand;
    if (!brand) {
      setError('Cannot resume: this campaign has no brand attached.');
      return;
    }
    setCreatingForBrand({ id: brand.id, name: brand.name });
    setNewIntent('');
    try {
      const sheet = await api.getCampaignSheet(campaign.id);
      const summary = deriveCampaignOverview(sheet, campaign, brand.name);
      const seed = summary.objective || summary.intent || summary.messageFocus;
      if (seed) setNewIntent(`Continuing from "${campaign.name}": ${seed}`);
    } catch {
      // No prior overview to seed from — form still opens for manual entry.
    }
  }

  const grouped = !activeBrand;
  const brandGroups: Array<{ id: string | null; label: ActiveBrand | null; campaigns: CampaignOut[] }> = grouped
    ? [
        ...brands.map(b => ({ id: b.id, label: { id: b.id, name: b.name }, campaigns: campaigns.filter(c => c.brand_id === b.id) })),
        {
          id: null,
          label: null,
          campaigns: campaigns.filter(c => !c.brand_id || !brands.some(b => b.id === c.brand_id)),
        },
      ].filter(g => g.id !== null || g.campaigns.length > 0)
    : [{ id: activeBrand!.id, label: activeBrand, campaigns }];

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">Campaign Board</div>
          <div className="admin-page-subtitle">
            {activeBrand
              ? `Brand foundation is always available for ${activeBrand.name}. Use an active campaign only when work needs tracked continuation, attribution, or optimization.`
              : 'Campaigns grouped by brand. Active campaigns are tracked work; completed campaigns are history/templates.'}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {activeCampaign?.status === 'active' && (
            <span className="badge badge-success" title="Live campaign context currently sent to CMO">
              CMO: {activeCampaign.name}
            </span>
          )}
          <label className="bos-proto-brand-chip bos-proto-brand-select" title="Filter Campaign Board by brand">
            <span>Brand filter</span>
            <select
              aria-label="Filter Campaign Board by brand"
              value={activeBrand?.id ?? ''}
              disabled={brands.length === 0}
              onChange={e => handleBrandFilterChange(e.target.value)}
            >
              <option value="">All brands</option>
              {brands.map(brand => <option key={brand.id} value={brand.id}>{brand.name}</option>)}
            </select>
          </label>
        </div>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 16 }} onClick={() => setError(null)}>
          {error}
        </div>
      )}

      {overviewSheet && activeCampaign && (() => {
        const activeCampaignRow = campaigns.find(c => c.id === activeCampaign.id) || {
          id: activeCampaign.id,
          name: activeCampaign.name,
          status: activeCampaign.status,
          brand_id: activeCampaign.brand_id,
          signal: undefined,
          created_at: '',
          updated_at: '',
        } as CampaignOut;
        return <CampaignOverviewCard overview={deriveCampaignOverview(overviewSheet, activeCampaignRow, activeBrand?.name)} />;
      })()}
      {reviewSheet && (() => {
        const campaign = campaigns.find(c => c.id === reviewingId);
        if (!campaign) return null;
        return (
        <CampaignOverviewCard
          overview={deriveCampaignOverview(reviewSheet, campaign, activeBrand?.name)}
          title="Campaign Review (read-only)"
          onClose={() => setReviewingId(null)}
        />
        );
      })()}

      {creatingForBrand && (
        <form onSubmit={handleCreate}>
          <div className="admin-card" style={{ marginBottom: 20 }}>
            <div className="admin-card-title">New Campaign for {creatingForBrand.name}</div>
            <div className="form-group" style={{ marginBottom: 16 }}>
              <label className="label">What are we trying to make happen?</label>
              <textarea
                className="input"
                placeholder="e.g. Start a campaign to drive more qualified inquiries for Golden Gate Memorial."
                value={newIntent}
                onChange={e => setNewIntent(e.target.value)}
                autoFocus
                rows={4}
                style={{ resize: 'vertical' }}
              />
              <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 6 }}>
                BOS will infer the first campaign snapshot from this intent and the approved Brand Kit.
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button type="submit" className="btn btn-dark" disabled={!newIntent.trim() || saving}>
                {saving ? 'Creating…' : 'Create Campaign'}
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => { setCreatingForBrand(null); setNewIntent(''); }}>
                Cancel
              </button>
            </div>
          </div>
        </form>
      )}

      {loading ? (
        <div className="admin-card">
          <div className="loading-full"><span className="spinner" /></div>
        </div>
      ) : (
        brandGroups.map(group => (
          <CampaignBrandGroup
            key={group.id ?? 'unassigned'}
            brandLabel={group.label?.name ?? 'Unassigned'}
            campaigns={group.campaigns}
            updatingId={updatingId}
            deletingId={deletingId}
            activeCampaignId={activeCampaign?.id ?? null}
            onAdvance={handleAdvance}
            onDelete={handleDelete}
            onUseCampaign={handleUseCampaign}
            onReview={handleReview}
            onResume={handleResume}
            onNewCampaign={group.label ? () => setCreatingForBrand(group.label!) : undefined}
          />
        ))
      )}
    </div>
  );
}

function CampaignOverviewCard({
  overview,
  title = 'Campaign Continuation Brief',
  onClose,
}: {
  overview: ReturnType<typeof deriveCampaignOverview>;
  title?: string;
  onClose?: () => void;
}) {
  const intent = overview.intent;
  const objective = overview.objective;
  const messageFocus = overview.messageFocus;
  const changed = overview.changed;
  const needs = overview.needs;
  const actors = overview.actors;
  const offers = overview.offers;
  const next = overview.next;
  const sheetRows = overview.sheetRows || [];

  return (
    <div className="admin-card" style={{ marginBottom: 20, borderLeft: '3px solid var(--brand)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'flex-start', marginBottom: 14 }}>
        <div>
          <div className="admin-card-title">{title}</div>
          <div style={{ color: 'var(--text2)', fontSize: 13 }}>
            {overview.campaign.brand_name || 'Selected brand'} · {overview.campaign.name} · {overview.campaign.status}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span className={`badge ${statusMeta(overview.campaign.status).cls}`}>{statusMeta(overview.campaign.status).label}</span>
          {onClose && (
            <button className="btn btn-ghost btn-sm" onClick={onClose}>Close</button>
          )}
        </div>
      </div>

      {sheetRows.length > 0 && (
        <div style={{ marginBottom: 14, padding: 12, borderRadius: 10, background: 'var(--surface2)' }}>
          <div style={{ fontSize: 12, color: 'var(--text2)', fontWeight: 700, marginBottom: 6 }}>Campaign operating sheet</div>
          <div style={{ display: 'grid', gap: 6 }}>
            {sheetRows.slice(0, 4).map(row => {
              const metrics = [
                row.primary_kpi && row.actual ? `${row.primary_kpi}: ${row.actual}` : row.primary_kpi || row.actual || null,
                row.reach_metric ? `reach ${row.reach_metric}` : null,
                row.engagement_metric ? `engagement ${row.engagement_metric}` : null,
                row.action_metric ? `action ${row.action_metric}` : null,
                row.efficiency_metric ? `efficiency ${row.efficiency_metric}` : null,
                row.value_metric ? `value ${row.value_metric}` : null,
                row.reach != null ? `reach ${row.reach}` : null,
                row.impressions != null ? `impr ${row.impressions}` : null,
                row.clicks != null ? `clicks ${row.clicks}` : null,
                row.leads != null ? `leads ${row.leads}` : null,
                row.qualified_calls != null ? `qualified calls ${row.qualified_calls}` : null,
                row.conversions != null ? `conv ${row.conversions}` : null,
              ].filter(Boolean).join(' · ');
              return (
                <div key={row.id} style={{ fontSize: 13, lineHeight: 1.4 }}>
                  <strong>{row.time_period || 'latest'}</strong>{row.market ? ` / ${row.market}` : ''}{row.distribution_channel ? ` / ${row.distribution_channel}` : ''}: {metrics || 'metrics not reported'} · verdict <strong>{row.objective_verdict}</strong> · source {row.source_health} · verification {row.verification_status}
                  {row.what_changed && <div style={{ color: 'var(--text2)' }}>{row.what_changed}</div>}
                  {(row.top_learning || row.recommended_action || row.note) && <div style={{ color: 'var(--text2)' }}>{[row.top_learning, row.recommended_action, row.note].filter(Boolean).join(' · ')}</div>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text2)', fontWeight: 700, marginBottom: 6 }}>What are we trying to make happen?</div>
          <div style={{ fontSize: 14, lineHeight: 1.45 }}>{objective || intent || messageFocus || 'Campaign intent is not yet clear.'}</div>
          {messageFocus && <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 6 }}>Focus: {messageFocus}</div>}
        </div>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text2)', fontWeight: 700, marginBottom: 6 }}>Known context data</div>
          {actors.length > 0 || offers.length > 0 ? (
            <div style={{ fontSize: 13, lineHeight: 1.45 }}>
              {actors.length > 0 && <div><strong>Actors:</strong> {actors.join(' · ')}</div>}
              {offers.length > 0 && <div style={{ marginTop: 4 }}><strong>Offers:</strong> {offers.join(' · ')}</div>}
            </div>
          ) : <div style={{ fontSize: 14, color: 'var(--text2)' }}>No compact actor/offer context captured yet.</div>}
        </div>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text2)', fontWeight: 700, marginBottom: 6 }}>What changed since the last decision?</div>
          {changed.length > 0 ? (
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14, lineHeight: 1.45 }}>
              {changed.map((item, i) => <li key={i}>{item}</li>)}
            </ul>
          ) : <div style={{ fontSize: 14, color: 'var(--text2)' }}>No recent campaign changes reported.</div>}
        </div>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text2)', fontWeight: 700, marginBottom: 6 }}>What needs to happen next?</div>
          <div style={{ fontSize: 14, lineHeight: 1.45, fontWeight: 600 }}>{next || 'Confirm the next campaign action.'}</div>
          {needs.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 12, color: 'var(--text2)', fontWeight: 700, marginBottom: 4 }}>Needs operator</div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, lineHeight: 1.4 }}>
                {needs.map((item, i) => <li key={i}>{item}</li>)}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function CampaignBrandGroup({
  brandLabel,
  campaigns,
  updatingId,
  deletingId,
  activeCampaignId,
  onAdvance,
  onDelete,
  onUseCampaign,
  onReview,
  onResume,
  onNewCampaign,
}: {
  brandLabel: string;
  campaigns: CampaignOut[];
  updatingId: string | null;
  deletingId: string | null;
  activeCampaignId: string | null;
  onAdvance: (c: CampaignOut) => void;
  onDelete: (c: CampaignOut) => void;
  onUseCampaign: (c: CampaignOut) => void;
  onReview: (c: CampaignOut) => void;
  onResume: (c: CampaignOut) => void;
  onNewCampaign?: () => void;
}) {
  const current = campaigns.filter(c => c.status === 'active' || c.status === 'draft');
  const history = campaigns.filter(c => c.status === 'complete' || c.status === 'archived');

  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div style={{ fontWeight: 700, fontSize: 15 }}>{brandLabel}</div>
        {onNewCampaign && (
          <button className="btn btn-secondary btn-sm" onClick={onNewCampaign}>+ New Campaign</button>
        )}
      </div>
      {campaigns.length === 0 ? (
        <div className="admin-card">
          <div className="empty-state" style={{ padding: '32px 0' }}>
            <div className="empty-state-title">No campaigns yet</div>
            <div className="empty-state-text">Create a campaign to group briefs, runs, and artifacts together.</div>
          </div>
        </div>
      ) : (
        <>
          {current.length > 0 && (
            <CampaignSection
              title="Tracked work"
              helper="Only active rows are sent to CMO as campaign context. Draft rows are plans not yet in execution."
              campaigns={current}
              updatingId={updatingId}
              deletingId={deletingId}
              activeCampaignId={activeCampaignId}
              onAdvance={onAdvance}
              onDelete={onDelete}
              onUseCampaign={onUseCampaign}
              onReview={onReview}
              onResume={onResume}
            />
          )}
          {history.length > 0 && (
            <CampaignSection
              title="History"
              helper="Completed campaigns stay available for review or as templates. They are not live CMO context."
              campaigns={history}
              updatingId={updatingId}
              deletingId={deletingId}
              activeCampaignId={activeCampaignId}
              onAdvance={onAdvance}
              onDelete={onDelete}
              onUseCampaign={onUseCampaign}
              onReview={onReview}
              onResume={onResume}
            />
          )}
        </>
      )}
    </div>
  );
}

function CampaignSection({
  title,
  helper,
  campaigns,
  updatingId,
  deletingId,
  activeCampaignId,
  onAdvance,
  onDelete,
  onUseCampaign,
  onReview,
  onResume,
}: {
  title: string;
  helper?: string;
  campaigns: CampaignOut[];
  updatingId: string | null;
  deletingId: string | null;
  activeCampaignId: string | null;
  onAdvance: (c: CampaignOut) => void;
  onDelete: (c: CampaignOut) => void;
  onUseCampaign: (c: CampaignOut) => void;
  onReview: (c: CampaignOut) => void;
  onResume: (c: CampaignOut) => void;
}) {
  return (
    <div className="admin-card" style={{ marginBottom: 20 }}>
      <div className="admin-card-title">{title}</div>
      {helper && <div style={{ color: 'var(--text2)', fontSize: 12, marginBottom: 10 }}>{helper}</div>}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Board role</th>
              <th>Created</th>
              <th style={{ width: 320 }}></th>
            </tr>
          </thead>
          <tbody>
            {campaigns.map(c => {
              const { label, cls } = statusMeta(c.status);
              const next = nextStatus(c.status);
              const isDone = c.status === 'complete' || c.status === 'archived';
              const canDelete = c.status === 'draft' || c.status === 'archived';
              return (
                <tr key={c.id}>
                  <td style={{ fontWeight: 600 }}>{c.name}</td>
                  <td><span className={`badge ${cls}`}>{label}</span></td>
                  <td>
                    <span className={`badge ${signalCls(c.signal?.state)}`} style={{ fontSize: 11 }}>
                      {c.signal?.label ?? 'Unknown'}
                    </span>
                  </td>
                  <td style={{ color: 'var(--text2)', fontSize: 12 }}>{timeAgo(c.created_at)}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                      {c.status === 'active' && c.brand_id && (
                        <button
                          className={activeCampaignId === c.id ? 'btn btn-dark btn-sm' : 'btn btn-secondary btn-sm'}
                          onClick={() => onUseCampaign(c)}
                          style={{ whiteSpace: 'nowrap' }}
                        >
                          {activeCampaignId === c.id ? 'Selected' : 'Use in CMO'}
                        </button>
                      )}
                      {isDone && (
                        <>
                          <button className="btn btn-ghost btn-sm" onClick={() => onReview(c)} style={{ whiteSpace: 'nowrap' }}>
                            Review
                          </button>
                          <button className="btn btn-secondary btn-sm" onClick={() => onResume(c)} style={{ whiteSpace: 'nowrap' }}>
                            Start new from this
                          </button>
                        </>
                      )}
                      {next && (
                        <button
                          className={next === 'complete' || next === 'archived' ? 'btn btn-secondary btn-sm' : 'btn btn-ghost btn-sm'}
                          disabled={updatingId === c.id}
                          onClick={() => onAdvance(c)}
                          title={next === 'complete' ? 'Requires confirmation. Moves campaign to History and removes it from live CMO context.' : undefined}
                          style={{ whiteSpace: 'nowrap' }}
                        >
                          {updatingId === c.id ? '…' : statusActionLabel(next)}
                        </button>
                      )}
                      {canDelete && (
                        <button
                          className="btn btn-ghost btn-sm"
                          disabled={deletingId === c.id}
                          onClick={() => onDelete(c)}
                          title="Permanently delete this draft/archived campaign. CMO chat cannot delete campaigns."
                          style={{ whiteSpace: 'nowrap', color: 'var(--danger)' }}
                        >
                          {deletingId === c.id ? 'Deleting…' : 'Delete'}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
