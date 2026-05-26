import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import type {
  DecisionBriefOut,
  MemoryEventOut,
  ObjectiveOut,
  OutcomeRecordOut,
  PendingDecisionOut,
} from '../../api/types';
import { timeAgo } from '../../utils/runs';

function StatusDot({ ok, warn }: { ok?: boolean; warn?: boolean }) {
  const cls = ok ? 'green' : warn ? 'amber' : 'grey';
  return <span className={`status-dot status-dot-${cls}`} />;
}

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

export function AdminObjectiveLoop() {
  const [objective, setObjective] = useState<ObjectiveOut | null>(null);
  const [outcomes, setOutcomes] = useState<OutcomeRecordOut[]>([]);
  const [events, setEvents] = useState<MemoryEventOut[]>([]);
  const [briefs, setBriefs] = useState<DecisionBriefOut[]>([]);
  const [pending, setPending] = useState<PendingDecisionOut[]>([]);
  const [gmailConnected, setGmailConnected] = useState(false);
  const [brandKitReady, setBrandKitReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [generatingBrief, setGeneratingBrief] = useState(false);

  useEffect(() => {
    setLoading(true);
    Promise.allSettled([
      api.getActiveObjective().catch(() => null),
      api.getOutcomes({ limit: 8 }).catch(() => ({ outcomes: [], total: 0 })),
      api.getMemoryEvents({ limit: 20 }).catch(() => ({ events: [], total: 0 })),
      api.getDecisionBriefs({ limit: 5 }).catch(() => ({ decision_briefs: [], total: 0 })),
      api.getPendingDecisions({ status: 'open' }).catch(() => ({ pending_decisions: [], total: 0 })),
      api.listSocialConnections().catch(() => []),
      api.getLatestBrandKit('approved').catch(() => null),
    ]).then(([obj, out, mem, db, pd, social, kit]) => {
      if (obj.status === 'fulfilled') setObjective(obj.value);
      if (out.status === 'fulfilled') setOutcomes(out.value.outcomes);
      if (mem.status === 'fulfilled') setEvents(mem.value.events);
      if (db.status === 'fulfilled') setBriefs(db.value.decision_briefs);
      if (pd.status === 'fulfilled') setPending(pd.value.pending_decisions);
      if (social.status === 'fulfilled') setGmailConnected((social.value as any[]).some((c: any) => c.platform === 'gmail' && c.status === 'active'));
      if (kit.status === 'fulfilled') setBrandKitReady(!!kit.value?.id);
      setLoading(false);
    });
  }, []);

  async function handleGenerateBrief() {
    setGeneratingBrief(true);
    try {
      const brief = await api.generateDecisionBrief({
        objective_id: objective?.id,
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

  const loopReady = gmailConnected && brandKitReady && !!objective;

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">Objective Loop</div>
          <div className="admin-page-subtitle">Active objective, memory ledger, outcomes, and decision briefs for the Gmail-only loop.</div>
        </div>
        {objective && (
          <button
            className="btn btn-primary"
            onClick={handleGenerateBrief}
            disabled={generatingBrief}
          >
            {generatingBrief ? 'Generating…' : 'Generate Decision Brief'}
          </button>
        )}
      </div>

      {/* Loop readiness */}
      <div className="admin-card" style={{ marginBottom: 24 }}>
        <div className="admin-card-title">Loop Readiness</div>
        <div className="settings-list">
          <div className="settings-row">
            <div className="settings-row-info">
              <div className="settings-row-name">Active Objective</div>
              <div className="settings-row-desc">
                {objective ? objective.summary : 'No active objective — create one to start the loop.'}
              </div>
            </div>
            <StatusDot ok={!!objective} warn={!objective} />
            <span className="settings-row-status-text">{objective ? objective.status : 'Missing'}</span>
          </div>
          <div className="settings-row">
            <div className="settings-row-info">
              <div className="settings-row-name">Gmail Connection</div>
              <div className="settings-row-desc">Required for outreach artifact execution.</div>
            </div>
            <StatusDot ok={gmailConnected} warn={!gmailConnected} />
            <span className="settings-row-status-text">{gmailConnected ? 'Connected' : 'Not connected'}</span>
          </div>
          <div className="settings-row">
            <div className="settings-row-info">
              <div className="settings-row-name">Campaign Brand Kit</div>
              <div className="settings-row-desc">Brand voice, product brief, ICP — read from database.</div>
            </div>
            <StatusDot ok={brandKitReady} warn={!brandKitReady} />
            <span className="settings-row-status-text">{brandKitReady ? 'Approved' : 'Not approved'}</span>
          </div>
        </div>
        {loopReady && (
          <div className="admin-notice admin-notice-success" style={{ marginTop: 12 }}>
            Loop ready — Gmail connected, brand kit approved, objective active.
          </div>
        )}
      </div>

      {/* Active objective detail */}
      {objective && (
        <div className="admin-card" style={{ marginBottom: 24 }}>
          <div className="admin-card-title">Active Objective</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div className="kv-row">
              <span className="kv-key">Summary</span>
              <span className="kv-val">{objective.summary}</span>
            </div>
            <div className="kv-row">
              <span className="kv-key">Success metric</span>
              <span className="kv-val">{objective.success_metric}</span>
            </div>
            <div className="kv-row">
              <span className="kv-key">Horizon</span>
              <span className="kv-val">{objective.horizon}</span>
            </div>
            <div className="kv-row">
              <span className="kv-key">Status</span>
              <span className="kv-val">
                <span className={`badge ${objective.status === 'active' ? 'badge-success' : 'badge-neutral'}`}>
                  {objective.status}
                </span>
              </span>
            </div>
          </div>
        </div>
      )}

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
