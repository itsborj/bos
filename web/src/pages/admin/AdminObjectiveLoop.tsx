import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import { useActiveContext } from '../../context/ActiveContext';
import type {
  BrandResponse,
  DecisionBriefOut,
  MemoryEventOut,
  OnboardingStatus,
  OutcomeRecordOut,
  PendingDecisionOut,
  PluginInfo,
  ProviderInfo,
  SocialConnectionResponse,
} from '../../api/types';
import { timeAgo } from '../../utils/runs';
import { buildStreamActivationChecklist, type StreamActivationChecklistItem } from '../../utils/streamActivationChecklist';

function confidenceBadge(confidence: string) {
  if (confidence.toLowerCase().includes('known')) return <span className="badge badge-success">{confidence}</span>;
  if (confidence.toLowerCase().includes('directional')) return <span className="badge badge-warning">{confidence}</span>;
  return <span className="badge badge-neutral">{confidence}</span>;
}

function eventTypeBadge(type: string) {
  if (type === 'decision_made') return <span className="badge badge-success">{type}</span>;
  if (type === 'decision_not_to_act') return <span className="badge badge-warning">{type}</span>;
  if (type === 'outcome_recorded') return <span className="badge badge-info">{type}</span>;
  if (type === 'artifact_approved') return <span className="badge badge-success">{type}</span>;
  if (type === 'constraint_flag') return <span className="badge badge-danger">{type}</span>;
  return <span className="badge badge-neutral">{type}</span>;
}

type SetupChecklistItem = StreamActivationChecklistItem;

function ChecklistBullet({ item }: { item: SetupChecklistItem }) {
  return (
    <li style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
        <span className={`badge badge-${item.ok ? 'success' : 'warning'}`} style={{ minWidth: 52, textAlign: 'center' }}>
          {item.ok ? 'Done' : 'Todo'}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 800, fontSize: 13 }}>{item.label}</div>
          <div style={{ color: 'var(--text2)', fontSize: 12, marginTop: 2 }}>{item.detail}</div>
          <div style={{ color: 'var(--text2)', fontSize: 11, marginTop: 4 }}>Required by: {item.requiredBy}</div>
        </div>
        <Link className="btn btn-ghost btn-sm" to={item.to} state={item.state} style={{ flexShrink: 0 }}>
          Open →
        </Link>
      </div>
    </li>
  );
}

export function AdminObjectiveLoop() {
  const { activeBrand } = useActiveContext();
  const [outcomes, setOutcomes] = useState<OutcomeRecordOut[]>([]);
  const [events, setEvents] = useState<MemoryEventOut[]>([]);
  const [briefs, setBriefs] = useState<DecisionBriefOut[]>([]);
  const [pending, setPending] = useState<PendingDecisionOut[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [brand, setBrand] = useState<BrandResponse | null>(null);
  const [onboardingStatus, setOnboardingStatus] = useState<OnboardingStatus | null>(null);
  const [connections, setConnections] = useState<SocialConnectionResponse[]>([]);
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [generatingBrief, setGeneratingBrief] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const brandId = activeBrand?.id;
    setLoading(true);
    setOutcomes([]);
    setEvents([]);
    setBriefs([]);
    setPending([]);
    setProviders([]);
    setBrand(null);
    setOnboardingStatus(null);
    setConnections([]);
    setPlugins([]);

    async function load() {
      const [out, mem, db, pd, social, prov, brands, onboarding, pluginResult] = await Promise.allSettled([
        api.getOutcomes({ brand_id: brandId, limit: 8 }).catch(() => ({ outcomes: [], total: 0 })),
        api.getMemoryEvents({ brand_id: brandId, limit: 20 }).catch(() => ({ events: [], total: 0 })),
        api.getDecisionBriefs({ brand_id: brandId, limit: 5 }).catch(() => ({ decision_briefs: [], total: 0 })),
        api.getPendingDecisions({ brand_id: brandId, status: 'open' }).catch(() => ({ pending_decisions: [], total: 0 })),
        api.listSocialConnections(brandId).catch(() => []),
        api.getProviders(brandId).catch(() => ({ providers: [] as ProviderInfo[] })),
        api.getBrands().catch(() => ({ brands: [] as BrandResponse[], total: 0 })),
        brandId ? api.getOnboardingStatus(brandId).catch(() => null) : Promise.resolve(null),
        api.listPlugins(brandId).catch(() => ({ plugins: [] as PluginInfo[] })),
      ]);

      if (cancelled) return;
      if (out.status === 'fulfilled') setOutcomes(out.value.outcomes);
      if (mem.status === 'fulfilled') setEvents(mem.value.events);
      if (db.status === 'fulfilled') setBriefs(db.value.decision_briefs);
      if (pd.status === 'fulfilled') setPending(pd.value.pending_decisions);
      if (social.status === 'fulfilled') setConnections(social.value as SocialConnectionResponse[]);
      if (prov.status === 'fulfilled') setProviders(prov.value.providers ?? []);
      if (brands.status === 'fulfilled') setBrand((brands.value.brands ?? []).find(b => b.id === brandId) ?? null);
      if (onboarding.status === 'fulfilled') setOnboardingStatus(onboarding.value);
      if (pluginResult.status === 'fulfilled') setPlugins(pluginResult.value.plugins ?? []);

      if (!cancelled) setLoading(false);
    }

    void load();
    return () => { cancelled = true; };
  }, [activeBrand?.id]);

  useEffect(() => {
    if (loading) return;
    const hash = window.location.hash;
    if (!hash) return;
    const targetId = decodeURIComponent(hash.slice(1));
    const timer = window.setTimeout(() => {
      document.getElementById(targetId)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 120);
    return () => window.clearTimeout(timer);
  }, [loading]);

  async function handleGenerateBrief() {
    setGeneratingBrief(true);
    try {
      const brief = await api.generateDecisionBrief({
        brand_id: activeBrand?.id,
      });
      setBriefs(prev => [brief, ...prev]);
    } catch {
      // surface nothing — brief gen can fail if data is thin
    } finally {
      setGeneratingBrief(false);
    }
  }

  async function handleResolve(id: string) {
    await api.resolvePendingDecision(id).catch(() => {});
    setPending(prev => prev.filter(p => p.id !== id));
  }

  if (loading) {
    return <div className="admin-page"><div className="loading-full"><span className="spinner" /></div></div>;
  }

  const brandId = activeBrand?.id;
  const checklist = buildStreamActivationChecklist({
    brandId,
    brandName: activeBrand?.name || brand?.name || '',
    providers,
    brand,
    onboardingStatus,
    connections,
    plugins,
  });
  const requiredChecklist: SetupChecklistItem[] = checklist.items;
  const completedRequired = checklist.completed;
  const loopReady = checklist.ready;

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">Stream Setup</div>
          <div className="admin-page-subtitle">Setup readiness, memory ledger, outcomes, and decision briefs for Stream monitoring.</div>
        </div>
        <button
          className="btn btn-primary"
          onClick={handleGenerateBrief}
          disabled={generatingBrief}
        >
          {generatingBrief ? 'Generating…' : 'Generate Decision Brief'}
        </button>
      </div>

      {/* Stream activation checklist */}
      <div className="admin-card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', marginBottom: 10 }}>
          <div>
            <div className="admin-card-title" style={{ marginBottom: 4 }}>Stream Activation Checklist</div>
            <div style={{ fontSize: 12, color: 'var(--text2)' }}>
              Stream stays inactive until every required setup item below is complete{activeBrand?.name ? ` for ${activeBrand.name}` : ''}.
            </div>
          </div>
          <span className={`badge badge-${loopReady ? 'success' : 'warning'}`} style={{ whiteSpace: 'nowrap' }}>
            {completedRequired}/{requiredChecklist.length} complete
          </span>
        </div>
        <ul style={{ listStyle: 'disc', paddingLeft: 18, margin: 0 }}>
          {requiredChecklist.map(item => <ChecklistBullet key={item.key} item={item} />)}
        </ul>
        {loopReady ? (
          <div className="admin-notice admin-notice-success" style={{ marginTop: 12 }}>
            Stream ready — all setup requirements are complete.
          </div>
        ) : (
          <div className="admin-notice admin-notice-warning" style={{ marginTop: 12 }}>
            Stream activation blocked — complete the Todo items above before expecting decision, artifact, or outcome cards.
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>
        {/* Decision briefs */}
        <div className="admin-card">
          <div className="admin-card-title">
            Decision Briefs
            <span className="admin-card-count">{briefs.length}</span>
          </div>
          {briefs.length === 0 ? (
            <div className="empty-state-inline">No briefs yet. Generate one once you have outcome data.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {briefs.map(b => (
                <div key={b.id} className="loop-item">
                  <div className="loop-item-top">
                    {confidenceBadge(b.confidence)}
                    <span className="loop-item-ts">{timeAgo(b.created_at)}</span>
                  </div>
                  <div className="loop-item-body">{b.summary}</div>
                  {b.recommended_next && (
                    <div className="loop-item-next">Next — {b.recommended_next}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Pending decisions */}
        <div className="admin-card">
          <div className="admin-card-title">
            Pending Decisions
            <span className="admin-card-count">{pending.length}</span>
          </div>
          {pending.length === 0 ? (
            <div className="empty-state-inline">No open decisions.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {pending.map(p => (
                <div key={p.id} className="loop-item loop-item-warn">
                  <div className="loop-item-body">{p.what_is_deferred}</div>
                  <div className="loop-item-meta">Waiting for: {p.waiting_for}</div>
                  {p.action_blocked && (
                    <div className="loop-item-meta" style={{ color: 'var(--color-danger)' }}>Blocked: {p.action_blocked}</div>
                  )}
                  <button
                    className="btn btn-ghost btn-sm"
                    style={{ marginTop: 6 }}
                    onClick={() => handleResolve(p.id)}
                  >
                    Mark resolved
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Outcome records */}
      <div className="admin-card" style={{ marginBottom: 24 }}>
        <div className="admin-card-title">
          Outcome Records
          <span className="admin-card-count">{outcomes.length}</span>
        </div>
        {outcomes.length === 0 ? (
          <div className="empty-state-inline">No outcomes recorded yet. Use the CMO to record a manual outcome after a send.</div>
        ) : (
          <table className="admin-table">
            <thead>
              <tr>
                <th>Summary</th>
                <th>Confidence</th>
                <th>Recorded</th>
              </tr>
            </thead>
            <tbody>
              {outcomes.map(o => (
                <tr key={o.id}>
                  <td>{o.summary}</td>
                  <td><span className="badge badge-neutral">{o.confidence_source}</span></td>
                  <td style={{ whiteSpace: 'nowrap', color: 'var(--color-text-muted)' }}>{timeAgo(o.recorded_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Memory ledger */}
      <div className="admin-card">
        <div className="admin-card-title">
          Memory Ledger
          <span className="admin-card-count">{events.length}</span>
        </div>
        {events.length === 0 ? (
          <div className="empty-state-inline">No memory events yet. Events write automatically as artifacts are approved, outcomes recorded, and decisions made.</div>
        ) : (
          <table className="admin-table">
            <thead>
              <tr>
                <th>Event</th>
                <th>Summary</th>
                <th>Tags</th>
                <th>When</th>
              </tr>
            </thead>
            <tbody>
              {events.map(e => (
                <tr key={e.id}>
                  <td style={{ whiteSpace: 'nowrap' }}>{eventTypeBadge(e.event_type)}</td>
                  <td style={{ maxWidth: 320 }}>{e.summary}</td>
                  <td>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                      {e.topic_tags.map(t => (
                        <span key={t} className="tag-chip">{t}</span>
                      ))}
                    </div>
                  </td>
                  <td style={{ whiteSpace: 'nowrap', color: 'var(--color-text-muted)' }}>{timeAgo(e.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
