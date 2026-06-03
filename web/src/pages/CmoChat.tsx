import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { useUI } from '../context/UIContext';
import { useCmoChat } from '../context/CmoChatContext';
import type { CouncilRoundMsg } from '../context/CmoChatContext';
import { BlockRenderer } from '../components/blocks/BlockRenderer';
import { SurfaceProvider } from '../surfaces/SurfaceContext';
import type { ArtifactRef } from '../utils/artifacts';
import { artifactStatusLabel, buildArtifactRef } from '../utils/artifacts';
import type { CouncilFinalizeResult, HandoffBriefOut, ObjectiveOut } from '../api/types';
import type { BriefingBlock } from '../types/stream';

const CARD_TYPE_LABELS: Record<string, string> = {
  decision_brief: 'Decision Brief',
  pending_artifact: 'Pending Artifact',
  outcome: 'Outcome',
  setup_blocker: 'Setup Blocker',
};

const OUTCOME_TYPES = [
  { value: 'reply_received', label: 'Reply received' },
  { value: 'meeting_booked', label: 'Meeting booked' },
  { value: 'deal_opened', label: 'Deal opened' },
  { value: 'no_response', label: 'No response' },
  { value: 'unsubscribed', label: 'Unsubscribed' },
  { value: 'other', label: 'Other' },
];

function fmtTime(d: Date) { return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }

function textToBlock(text: string): BriefingBlock {
  return {
    id: Math.random().toString(36).slice(2),
    timestamp: new Date().toISOString(),
    priority: 'normal',
    category: 'status',
    layout_hint: 'narrative',
    interaction: 'passive',
    content: text
  };
}

function ArtifactReferenceCard({ refData, onOpen }: { refData: ArtifactRef; onOpen: (artifactId: string) => void }) {
  return (
    <div className="bos-chat-artifact-ref">
      <div>
        <div className="artifact-eyebrow">Stream artifact</div>
        <div className="artifact-title">{refData.title}</div>
        <div className="artifact-meta">
          {artifactStatusLabel(refData.status)} · {refData.type.replace(/_/g, ' ')} · Preview in Stream
        </div>
      </div>
      <button className="artifact-btn primary" onClick={() => onOpen(refData.artifact_id)}>
        Review in Stream →
      </button>
    </div>
  );
}

function OutcomeFormMessage({
  msgId,
  objective,
  onConfirm,
  onCancel,
}: {
  msgId: string;
  objective: ObjectiveOut | null;
  onConfirm: (msgId: string, outcomeType: string, value: string, notes: string, objectiveSummary?: string) => Promise<void>;
  onCancel: (msgId: string) => void;
}) {
  const [outcomeType, setOutcomeType] = useState('reply_received');
  const [value, setValue] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    setSubmitting(true);
    await onConfirm(msgId, outcomeType, value, notes, objective?.summary);
  }

  return (
    <div className="bos-outcome-form">
      {objective && (
        <div className="bos-outcome-form-obj">
          <span className="bos-outcome-form-obj-label">Objective</span>
          <span className="bos-outcome-form-obj-title">{objective.summary}</span>
        </div>
      )}
      <div className="bos-outcome-form-field">
        <div className="bos-outcome-form-label">Outcome type</div>
        <select
          className="bos-outcome-form-select"
          value={outcomeType}
          onChange={e => setOutcomeType(e.target.value)}
          disabled={submitting}
        >
          {OUTCOME_TYPES.map(t => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </div>
      <div className="bos-outcome-form-field">
        <div className="bos-outcome-form-label">Metric / value</div>
        <input
          className="bos-outcome-form-input"
          type="text"
          placeholder="e.g. 35% open rate, 2 replies"
          value={value}
          onChange={e => setValue(e.target.value)}
          disabled={submitting}
        />
      </div>
      <div className="bos-outcome-form-field">
        <div className="bos-outcome-form-label">Notes for memory <span style={{ opacity: 0.55 }}>(optional)</span></div>
        <textarea
          className="bos-outcome-form-textarea"
          placeholder="Anything BOS should remember about this result..."
          value={notes}
          onChange={e => setNotes(e.target.value)}
          rows={2}
          disabled={submitting}
        />
      </div>
      <div className="bos-outcome-form-actions">
        <button
          className="btn btn-primary"
          style={{ fontSize: 12 }}
          onClick={handleSubmit}
          disabled={submitting || !value.trim()}
        >
          {submitting ? 'Recording…' : 'Record & update memory'}
        </button>
        <button
          className="btn btn-ghost"
          style={{ fontSize: 12 }}
          onClick={() => onCancel(msgId)}
          disabled={submitting}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function HandoffBriefMessage({ brief }: { brief: HandoffBriefOut }) {
  const generatedAt = new Date(brief.generated_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' });
  const firstObj = brief.active_objectives[0] as Record<string, unknown> | undefined;

  function plainText() {
    const lines: string[] = ['=== HANDOFF BRIEF ===', `Generated: ${generatedAt}`];
    if (firstObj) lines.push(`Objective: ${String(firstObj.summary ?? firstObj.title ?? '')}`);
    lines.push('');
    if (brief.working?.length) { lines.push('Active state:'); brief.working.forEach(w => lines.push(`  + ${w}`)); lines.push(''); }
    if (brief.not_working?.length) { lines.push('Not working:'); brief.not_working.forEach(w => lines.push(`  - ${w}`)); lines.push(''); }
    if (brief.pending_decisions?.length) { lines.push('Pending decisions:'); brief.pending_decisions.forEach(d => lines.push(`  • ${d.what_is_deferred}`)); lines.push(''); }
    if (brief.committed_actions?.length) { lines.push('Committed actions:'); (brief.committed_actions as Record<string, unknown>[]).forEach(a => lines.push(`  • ${String(a.action ?? a.summary ?? JSON.stringify(a))}`)); lines.push(''); }
    if (brief.known_risks?.length) { lines.push('Known risks:'); brief.known_risks.forEach(r => lines.push(`  ⚠ ${r}`)); lines.push(''); }
    if (brief.decided_against?.length) { lines.push('Decided against:'); brief.decided_against.forEach(d => lines.push(`  — ${d}`)); lines.push(''); }
    if (brief.recommended_first_action) lines.push(`Recommended first action: ${brief.recommended_first_action}`);
    lines.push('', 'Pass condition: A new CMO should be operational from this brief alone.');
    return lines.join('\n');
  }

  return (
    <div className="cmo-hb">
      <div className="cmo-hb-header">
        <div>
          <div className="cmo-hb-header-title">Handoff Brief</div>
          <div className="cmo-hb-header-obj">{firstObj ? String(firstObj.summary ?? firstObj.title ?? 'Active objective') : 'Active objective'}</div>
          {firstObj && <div className="cmo-hb-header-meta">Active objective</div>}
        </div>
        <div className="cmo-hb-header-ts">{generatedAt}</div>
      </div>
      <div className="cmo-hb-sections">
        {brief.working?.length > 0 && (
          <div className="cmo-hb-section">
            <div className="cmo-hb-label">Active state</div>
            <div className="cmo-hb-body">{brief.working.map((w, i) => <div key={i}>✓ {w}</div>)}</div>
          </div>
        )}
        {brief.not_working?.length > 0 && (
          <div className="cmo-hb-section">
            <div className="cmo-hb-label">Recent performance</div>
            <div className="cmo-hb-body">{brief.not_working.map((w, i) => <div key={i}>✗ {w}</div>)}</div>
          </div>
        )}
        {brief.pending_decisions?.length > 0 && (
          <div className="cmo-hb-section">
            <div className="cmo-hb-label">Pending decisions</div>
            <div className="cmo-hb-body">{brief.pending_decisions.map((d, i) => <div key={i}>{d.what_is_deferred}</div>)}</div>
          </div>
        )}
        {brief.committed_actions?.length > 0 && (
          <div className="cmo-hb-section">
            <div className="cmo-hb-label">Committed actions</div>
            <div className="cmo-hb-body">
              {(brief.committed_actions as Record<string, unknown>[]).map((a, i) => (
                <div key={i}>{String(a.action ?? a.summary ?? JSON.stringify(a))}</div>
              ))}
            </div>
          </div>
        )}
        {brief.known_risks?.length > 0 && (
          <div className="cmo-hb-section">
            <div className="cmo-hb-label">Known risks</div>
            <div className="cmo-hb-body">{brief.known_risks.map((r, i) => <div key={i}>⚠ {r}</div>)}</div>
          </div>
        )}
        {brief.decided_against?.length > 0 && (
          <div className="cmo-hb-section">
            <div className="cmo-hb-label">Decided against</div>
            <div className="cmo-hb-body">{brief.decided_against.map((d, i) => <div key={i}>— {d}</div>)}</div>
          </div>
        )}
        {brief.recommended_first_action && (
          <div className="cmo-hb-section cmo-hb-action">
            <div className="cmo-hb-label">Recommended first action</div>
            <div className="cmo-hb-body">{brief.recommended_first_action}</div>
          </div>
        )}
      </div>
      <div className="cmo-hb-footer">
        <span className="cmo-hb-pass">Pass condition: A new CMO should be operational from this brief alone.</span>
        <button className="btn-hb-copy" onClick={() => navigator.clipboard.writeText(plainText())}>Copy brief</button>
      </div>
    </div>
  );
}

function CouncilRoundMessage({ round }: { round: CouncilRoundMsg }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  return (
    <div className="council-round">
      <div className="council-round-header">
        <span className="council-badge">⬡ COUNCIL</span>
        <span className="council-round-label">Round {round.round_num}</span>
      </div>
      <div className="council-seats">
        {round.positions.map(pos => (
          <div key={pos.seat_id} className="council-seat">
            <button
              className="council-seat-header"
              onClick={() => setExpanded(e => e === pos.seat_id ? null : pos.seat_id)}
            >
              <span className="council-seat-id">{pos.seat_id.toUpperCase()}</span>
              <span className="council-seat-name">{pos.display_name !== pos.seat_id ? pos.display_name : ''}</span>
              <span className="council-seat-toggle">{expanded === pos.seat_id ? '▲' : '▼'}</span>
            </button>
            {expanded === pos.seat_id ? (
              <div className="council-seat-body">{pos.content}</div>
            ) : (
              <div className="council-seat-preview">{pos.content.slice(0, 120)}{pos.content.length > 120 ? '…' : ''}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function CouncilBriefMessage({ brief }: { brief: CouncilFinalizeResult }) {
  const [transcriptOpen, setTranscriptOpen] = useState(false);
  return (
    <div className="council-brief">
      <div className="council-brief-header">
        <span className="council-badge">⬡ COUNCIL BRIEF</span>
        <span className="council-brief-settled">✓ Settled · {brief.rounds_completed} round{brief.rounds_completed !== 1 ? 's' : ''}</span>
      </div>
      {brief.brief && <div className="council-brief-question">"{brief.brief}"</div>}
      {brief.settlement && (
        <div className="council-brief-section">
          <div className="council-brief-label">Settlement</div>
          <div className="council-brief-body">{brief.settlement}</div>
        </div>
      )}
      {brief.marching_orders.length > 0 && (
        <div className="council-brief-section">
          <div className="council-brief-label">Marching orders</div>
          <ol className="council-brief-list">
            {brief.marching_orders.map((item, i) => <li key={i}>{item}</li>)}
          </ol>
        </div>
      )}
      {brief.parked_decisions.length > 0 && (
        <div className="council-brief-section">
          <div className="council-brief-label">Parked decisions</div>
          <ul className="council-brief-list">
            {brief.parked_decisions.map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        </div>
      )}
      <button className="council-transcript-toggle" onClick={() => setTranscriptOpen(o => !o)}>
        {transcriptOpen ? '▲ Hide transcript' : '▼ Full transcript'}
      </button>
      {transcriptOpen && (
        <pre className="council-transcript">{brief.transcript}</pre>
      )}
    </div>
  );
}

export function CmoChat() {
  const { openSettings, activeBrand } = useUI();
  const {
    msgs, busy, pendingPlan, streamCardCtx, activeObjective, activeCouncilSession,
    setPendingPlan, send, councilPass, councilFinalize, handleOutcomeConfirm, handleOutcomeCancel,
  } = useCmoChat();

  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [msgs]);
  // Scroll to bottom when navigating back to /cmo after messages arrived while hidden.
  useEffect(() => {
    const handler = () => bottomRef.current?.scrollIntoView({ behavior: 'instant' });
    window.addEventListener('bos:chat-scroll-bottom', handler);
    return () => window.removeEventListener('bos:chat-scroll-bottom', handler);
  }, []);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input).then(() => {}); setInput(''); }
  }

  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  }

  async function handleOpenArtifact(artifactId: string) {
    // Focus the exact artifact in Stream. Do not navigate to Workspace; Stream is
    // the inline review surface for pending artifacts.
    try {
      const run = await api.getRun(artifactId, { includeAssets: false });
      window.dispatchEvent(new CustomEvent('bos:focus-artifact', { detail: run }));
    } catch {
      window.dispatchEvent(new CustomEvent('bos:focus-artifact', { detail: { run_id: artifactId } }));
    }
  }

  function doSend() {
    const text = input;
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    send(text);
  }

  const contextChips = [
    activeBrand?.name ? `Brand · ${activeBrand.name}` : null,
    activeObjective ? (activeObjective.summary.length > 40 ? `${activeObjective.summary.slice(0, 40)}…` : activeObjective.summary) : null,
    streamCardCtx ? `${CARD_TYPE_LABELS[streamCardCtx.type] ?? streamCardCtx.type}` : null,
    activeCouncilSession ? `⬡ Council in session` : null,
  ].filter(Boolean) as string[];

  return (
    <div className="cmo-pane">
      {contextChips.length > 0 && (
        <div className="cmo-ctx">
          {contextChips.map(chip => (
            <span key={chip} className="g2src" style={{ fontSize: 11 }}>{chip}</span>
          ))}
        </div>
      )}

      <div className="cmo-msgs">
        <div className="cmo-msgs-body">
          {msgs.map((msg, idx) => {
            const showSender = idx === 0 || msgs[idx - 1].role !== msg.role;

            if (msg.text === '__typing__') {
              const steps = msg.steps ?? [];
              const complete = msg.stepsComplete ?? false;
              return (
                <div key={msg.id}>
                  {showSender && <div className="msg-label">CMO</div>}
                  <div className="msg-ai">
                    {steps.length > 0 ? (
                      <div className={`cmo-steps${complete ? ' cmo-steps-done' : ''}`}>
                        {steps.map((label, i) => {
                          const done = complete || i < steps.length - 1;
                          return (
                            <div key={i} className={`cmo-step ${done ? 'cmo-step-done' : 'cmo-step-active'}`}>
                              <span className="cmo-step-icon">{done ? '✓' : '●'}</span>
                              <span className="cmo-step-label">{label}</span>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="cmo-typing">
                        <div className="cmo-typing-dot" />
                        <div className="cmo-typing-dot" />
                        <div className="cmo-typing-dot" />
                      </div>
                    )}
                  </div>
                </div>
              );
            }

            const artifactRef = msg.artifactRef || (msg.runResult ? buildArtifactRef(msg.runResult) : null);
            if (artifactRef) {
              return (
                <div key={msg.id}>
                  {showSender && <div className="msg-label">CMO</div>}
                  <div className="msg-ai">
                    <ArtifactReferenceCard refData={artifactRef} onOpen={handleOpenArtifact} />
                  </div>
                </div>
              );
            }

            if (msg.outcomeForm && !msg.outcomeConfirm) {
              return (
                <div key={msg.id}>
                  <div className="msg-label">CMO</div>
                  <div className="msg-ai">
                    <OutcomeFormMessage
                      msgId={msg.id}
                      objective={activeObjective}
                      onConfirm={handleOutcomeConfirm}
                      onCancel={handleOutcomeCancel}
                    />
                  </div>
                </div>
              );
            }

            if (msg.outcomeConfirm) {
              const c = msg.outcomeConfirm;
              const typeLabel = OUTCOME_TYPES.find(t => t.value === c.outcomeType)?.label ?? c.outcomeType;
              return (
                <div key={msg.id}>
                  <div className="msg-label">CMO</div>
                  <div className="msg-ai">
                    <div className="bos-outcome-confirm">
                      <div className="bos-outcome-confirm-tags">
                        <span className="bos-outcome-confirm-tag">{typeLabel}</span>
                        {c.objectiveSummary && <span className="bos-outcome-confirm-tag obj">{c.objectiveSummary}</span>}
                      </div>
                      <div className="bos-outcome-confirm-value">{c.value}</div>
                      <div className="bos-outcome-confirm-note">Next recommendation will incorporate this result.</div>
                    </div>
                  </div>
                </div>
              );
            }

            if (msg.handoffBrief) {
              return (
                <div key={msg.id}>
                  <div className="msg-label">CMO · handoff brief · {fmtTime(msg.time)}</div>
                  <HandoffBriefMessage brief={msg.handoffBrief} />
                </div>
              );
            }

            if (msg.councilRound) {
              return (
                <div key={msg.id}>
                  <div className="msg-label">Council · Round {msg.councilRound.round_num} · {fmtTime(msg.time)}</div>
                  <div className="msg-ai">
                    <CouncilRoundMessage round={msg.councilRound} />
                  </div>
                </div>
              );
            }

            if (msg.councilBrief) {
              return (
                <div key={msg.id}>
                  <div className="msg-label">Council · Brief · {fmtTime(msg.time)}</div>
                  <div className="msg-ai">
                    <CouncilBriefMessage brief={msg.councilBrief} />
                  </div>
                </div>
              );
            }

            if (msg.role === 'user') {
              return (
                <div key={msg.id} className="msg-user">{msg.text}</div>
              );
            }

            return (
              <div key={msg.id}>
                {showSender && <div className="msg-label">CMO · {fmtTime(msg.time)}</div>}
                <div className="msg-ai">
                  <SurfaceProvider type="chat-inline">
                    <BlockRenderer block={textToBlock(msg.text!)} />
                  </SurfaceProvider>
                </div>
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="cmo-input-wrap">
        {pendingPlan && (
          <div style={{ display: 'flex', gap: 8, marginBottom: 10, padding: '10px 14px', background: 'var(--green-bg)', borderRadius: 8, border: '1px solid var(--green-border)', alignItems: 'center' }}>
            <span style={{ fontSize: 13, color: 'var(--green-mid)', flex: 1 }}>Plan drafted — confirm to create the campaign and tag all runs to it.</span>
            <button
              className="btn btn-primary"
              style={{ fontSize: 12 }}
              onClick={() => send('@klar confirm', { skipUserMessage: false })}
              disabled={busy}
            >
              Confirm Plan
            </button>
            <button
              className="btn btn-ghost"
              style={{ fontSize: 12 }}
              onClick={() => setPendingPlan(false)}
              disabled={busy}
            >
              Dismiss
            </button>
          </div>
        )}

        {activeCouncilSession?.status === 'awaiting_c6' && (
          <div style={{ display: 'flex', gap: 8, marginBottom: 10, padding: '10px 14px', background: 'var(--amber-bg, #fffbeb)', borderRadius: 8, border: '1px solid var(--amber-border, #fde68a)', alignItems: 'center' }}>
            <span style={{ fontSize: 13, color: '#92400e', flex: 1 }}>
              {activeCouncilSession.pending_c6_prompt || 'The council is waiting for your input.'}
            </span>
            <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={councilPass} disabled={busy}>Continue</button>
            <button className="btn btn-ghost" style={{ fontSize: 12, color: '#b45309' }} onClick={councilFinalize} disabled={busy}>Finalize</button>
          </div>
        )}

        {streamCardCtx && (
          <div style={{ marginBottom: 10 }}>
            <div className="msg-label" style={{ marginBottom: 6 }}>Context actions</div>
            <div className="cmo-chips">
              <button type="button" className="btn btn-ghost" style={{ fontSize: 12 }} onClick={() => send('Why this angle?')} disabled={busy}>
                Why this angle?
              </button>
              <button type="button" className="btn btn-ghost" style={{ fontSize: 12 }} onClick={() => send('What happens after approval?')} disabled={busy}>
                What happens after approval?
              </button>
            </div>
          </div>
        )}

        <div className="cmo-composer">
          <textarea
            ref={textareaRef}
            className="cmo-ta"
            rows={1}
            placeholder={activeCouncilSession?.status === 'awaiting_c6'
              ? 'Respond to the council, or use Pass / Finalize above…'
              : 'Direct your CMO — brief a campaign, request a revision, or ask for a report...'}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            disabled={busy}
          />
          <div className="cmo-composer-foot">
            <span className="cmo-hint">
              Shift+Enter for new line ·{' '}
              <span className="cmo-hint-link" onClick={() => openSettings('history')}>History</span>
            </span>
            <button
              className="btn-send"
              onClick={doSend}
              disabled={busy || !input.trim()}
            >
              ↑
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
