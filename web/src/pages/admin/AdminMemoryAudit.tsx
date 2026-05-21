import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { HandoffBriefOut, MemoryEventOut, OutcomeRecordOut } from '../../api/types';

function timeAgoShort(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const d = Math.floor(diff / 86400000);
  if (d > 0) return `${d}d ago`;
  const h = Math.floor(diff / 3600000);
  if (h > 0) return `${h}h ago`;
  return 'just now';
}

function eventLabel(type: string): string {
  const map: Record<string, string> = {
    decision_made: 'Decision',
    decision_not_to_act: 'Decision',
    outcome_recorded: 'Outcome',
    artifact_approved: 'Artifact approved',
    constraint_flag: 'Constraint',
  };
  return map[type] || type.replace(/_/g, ' ');
}

export function AdminMemoryAudit() {
  const [outcomes, setOutcomes] = useState<OutcomeRecordOut[]>([]);
  const [events, setEvents] = useState<MemoryEventOut[]>([]);
  const [brief, setBrief] = useState<HandoffBriefOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [briefLoading, setBriefLoading] = useState(false);

  useEffect(() => {
    Promise.allSettled([
      api.getOutcomes({ limit: 10 }),
      api.getMemoryEvents({ limit: 20 }),
    ]).then(([out, mem]) => {
      if (out.status === 'fulfilled') setOutcomes(out.value.outcomes);
      if (mem.status === 'fulfilled') setEvents(mem.value.events);
    }).finally(() => setLoading(false));
  }, []);

  async function loadBrief() {
    setBriefLoading(true);
    try {
      const b = await api.getHandoffBrief();
      setBrief(b);
    } catch {
      // brief generation requires backend context
    } finally {
      setBriefLoading(false);
    }
  }

  const records = [
    ...outcomes.map(o => ({
      key: o.id,
      label: `Outcome · ${o.summary.slice(0, 60)}`,
      desc: `Recorded ${timeAgoShort(o.recorded_at)} · ${o.confidence_source}`,
    })),
    ...events.filter(e => e.event_type.startsWith('decision')).map(e => ({
      key: e.id,
      label: `${eventLabel(e.event_type)} · ${e.summary.slice(0, 60)}`,
      desc: `${timeAgoShort(e.created_at)}${e.rationale ? ` · ${e.rationale.slice(0, 80)}` : ''}`,
    })),
  ].sort((a, b) => b.key.localeCompare(a.key)).slice(0, 10);

  const firstAction = brief?.recommended_first_action;
  const knownRisks = brief?.known_risks ?? [];
  const decidedAgainst = brief?.decided_against ?? [];
  const pendingDecs = brief?.pending_decisions ?? [];
  const committedActions = brief?.committed_actions ?? [];
  const perfNarrative = brief?.performance_narrative as any;

  return (
    <div>
      <div className="admin-section-title">Memory &amp; Audit</div>
      <div className="admin-section-sub">Outcome records, decision rationales, and the current handoff brief.</div>

      <div className="settings-group">
        <div className="settings-group-label">Recent records</div>
        {loading ? (
          <div style={{ padding: '16px 0', color: 'var(--muted-stone)', fontSize: 13 }}>Loading…</div>
        ) : records.length === 0 ? (
          <div style={{ padding: '16px 0', color: 'var(--muted-stone)', fontSize: 13 }}>No memory records yet. Approved artifacts and recorded outcomes will appear here.</div>
        ) : records.map(r => (
          <div className="settings-row" key={r.key}>
            <div className="settings-row-info">
              <div className="settings-row-name">{r.label}</div>
              <div className="settings-row-desc">{r.desc}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="settings-group">
        <div className="settings-group-label">
          <span>Handoff brief{brief ? ` · ${new Date(brief.generated_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}` : ''}</span>
          {!brief && (
            <button className="action-link" onClick={loadBrief} disabled={briefLoading}>
              {briefLoading ? 'Generating…' : '+ Generate brief'}
            </button>
          )}
        </div>

        {brief ? (
          <div className="hb-card" style={{ marginTop: 14 }}>
            {brief.active_objectives.length > 0 && (
              <div className="hb-row">
                <div className="hb-label">Active objectives</div>
                <div className="hb-body">
                  {(brief.active_objectives as any[]).map((o, i) => (
                    <div key={i}>{o.summary || JSON.stringify(o)}</div>
                  ))}
                </div>
              </div>
            )}
            {perfNarrative && (
              <div className="hb-row">
                <div className="hb-label">Recent performance</div>
                <div className="hb-body">{perfNarrative.narrative || perfNarrative.summary || JSON.stringify(perfNarrative)}</div>
              </div>
            )}
            {pendingDecs.length > 0 && (
              <div className="hb-row">
                <div className="hb-label">Pending decisions</div>
                <div className="hb-body">{pendingDecs.map((d: any) => d.summary || d.question).join(' · ')}</div>
              </div>
            )}
            {committedActions.length > 0 && (
              <div className="hb-row">
                <div className="hb-label">Committed actions</div>
                <div className="hb-body">{(committedActions as any[]).map(a => a.action || JSON.stringify(a)).join(' · ')}</div>
              </div>
            )}
            {knownRisks.length > 0 && (
              <div className="hb-row">
                <div className="hb-label">Known risks</div>
                <div className="hb-body">{knownRisks.join(' · ')}</div>
              </div>
            )}
            {decidedAgainst.length > 0 && (
              <div className="hb-row">
                <div className="hb-label">Decided against</div>
                <div className="hb-body">{decidedAgainst.join(' · ')}</div>
              </div>
            )}
            {firstAction && (
              <div className="hb-row">
                <div className="hb-label">Recommended first action</div>
                <div className="hb-body rec">{firstAction}</div>
              </div>
            )}
          </div>
        ) : !briefLoading ? (
          <div style={{ padding: '16px 0', color: 'var(--muted-stone)', fontSize: 13 }}>
            Generate a brief to see the current state summary for handoff or review.
          </div>
        ) : null}
      </div>
    </div>
  );
}
