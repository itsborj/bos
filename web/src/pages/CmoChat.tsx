import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
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
  const navigate = useNavigate();
  const isWorkflow = refData.renderer === 'strategy_workflow_preview';
  return (
    <div className="bos-chat-artifact-ref">
      <div>
        <div className="artifact-eyebrow">{isWorkflow ? 'Strategy Workflow' : 'Stream artifact'}</div>
        <div className="artifact-title">{refData.title}</div>
        <div className="artifact-meta">
          {artifactStatusLabel(refData.status)} · {refData.type.replace(/_/g, ' ')} · {isWorkflow ? 'Modular workflow' : 'Preview in Stream'}
        </div>
      </div>
      {isWorkflow ? (
        <button className="artifact-btn primary" onClick={() => navigate(refData.workspace_url)}>
          Open Strategy Workflow →
        </button>
      ) : (
        <button className="artifact-btn primary" onClick={() => onOpen(refData.artifact_id)}>
          Review in Stream →
        </button>
      )}
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
  const { activeBrand } = useUI();
  const {
    msgs, busy, streamCardCtx, activeObjective, activeCouncilSession,
    pendingReferences, addReference, removeReference, clearReferences,
    send, councilPass, councilFinalize, handleOutcomeConfirm, handleOutcomeCancel,
  } = useCmoChat();

  const [input, setInput] = useState('');
  const [refError, setRefError] = useState<string | null>(null);
  // Drive picker modal state
  const [driveModalOpen, setDriveModalOpen] = useState(false);
  const [driveFilter, setDriveFilter] = useState<'all' | 'image' | 'document'>('all');
  const [driveCurrentFolder, setDriveCurrentFolder] = useState<{ id: string; name: string } | null>(null);
  const [driveFolderStack, setDriveFolderStack] = useState<{ id: string; name: string }[]>([]);
  const [driveFolders, setDriveFolders] = useState<{ id: string; name: string }[]>([]);
  const [driveModalFiles, setDriveModalFiles] = useState<{ id: string; name: string; mimeType: string; size?: number; webViewLink?: string; thumbnailLink?: string }[]>([]);
  const [driveModalLoading, setDriveModalLoading] = useState(false);
  const [driveModalSelected, setDriveModalSelected] = useState<Set<string>>(new Set());
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [msgs]);
  useEffect(() => {
    const applyPrefill = (text: string) => {
      if (!text) return;
      setInput(text);
      window.setTimeout(() => {
        textareaRef.current?.focus();
        if (textareaRef.current) {
          textareaRef.current.style.height = 'auto';
          textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px';
        }
      }, 60);
    };
    try {
      const saved = sessionStorage.getItem('bos:cmo-prefill');
      if (saved) {
        sessionStorage.removeItem('bos:cmo-prefill');
        applyPrefill(saved);
      }
    } catch {}
    const handler = (event: Event) => applyPrefill(String((event as CustomEvent).detail || ''));
    window.addEventListener('bos:cmo-prefill', handler);
    return () => window.removeEventListener('bos:cmo-prefill', handler);
  }, []);
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
    e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
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

  const DRIVE_ROOT = { id: 'root', name: 'My Drive' };

  async function openDrivePicker() {
    setDriveModalOpen(true);
    setDriveModalSelected(new Set());
    setDriveFilter('all');
    await loadDrivePickerFolder(DRIVE_ROOT, []);
  }

  async function loadDrivePickerFolder(folder: { id: string; name: string } | null, stack: { id: string; name: string }[]) {
    setDriveModalLoading(true);
    setDriveModalFiles([]);
    setDriveFolders([]);
    setRefError(null);
    try {
      const brandId = activeBrand?.id || '';
      if (!brandId) {
        setRefError('Select a brand with Google Drive connected first.');
        setDriveModalLoading(false);
        return;
      }
      const foldersRes = await api.listDriveFolders(brandId, folder?.id);
      const current = folder || { id: (foldersRes as any).folder_id || 'root', name: (foldersRes as any).folder_name || 'Drive' };
      const filesRes = await api.listDriveImages(brandId, current.id, 'all');
      setDriveCurrentFolder(current);
      setDriveFolderStack(stack);
      setDriveFolders(foldersRes.folders || []);
      setDriveModalFiles(filesRes.files || []);
    } catch (e) {
      setRefError(e instanceof Error ? e.message : 'Could not load Drive.');
    } finally {
      setDriveModalLoading(false);
    }
  }

  function toggleDriveModalFile(fileId: string) {
    setDriveModalSelected(prev => {
      const next = new Set(prev);
      if (next.has(fileId)) next.delete(fileId); else next.add(fileId);
      return next;
    });
  }

  const DOC_MIMES_SET = new Set([
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.ms-powerpoint',
    'application/pdf',
    'application/vnd.google-apps.document',
    'application/vnd.google-apps.presentation',
    'application/json',
    'text/plain',
  ]);

  function attachDriveSelected() {
    driveModalFiles
      .filter(f => driveModalSelected.has(f.id))
      .forEach(f => addReference({
        kind: DOC_MIMES_SET.has(f.mimeType) ? 'document' : 'image',
        source: 'google_drive',
        title: f.name,
        drive_file_id: f.id,
        drive_file_name: f.name,
        drive_web_view_link: f.webViewLink,
        mime_type: f.mimeType,
        thumbnail_link: f.thumbnailLink,
      }));
    setDriveModalOpen(false);
    setDriveModalSelected(new Set());
  }

  function doSend() {
    if (!input.trim() || busy) return;
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
                <div key={msg.id} className="msg-user">
                  <div>{msg.text}</div>
                  {msg.references && msg.references.length > 0 && (
                    <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'flex-end' }}>
                      {msg.references.map((ref, i) => (
                        <span key={i} className="g2src" style={{ fontSize: 10, background: 'rgba(255,255,255,0.16)' }}>
                          {ref.kind === 'image' ? '🖼️' : '📄'} {ref.title || ref.drive_file_name || 'Reference'}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
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
        {activeCouncilSession?.status === 'awaiting_c6' && (
          <div style={{ display: 'flex', gap: 8, marginBottom: 10, padding: '10px 14px', background: 'var(--status-warning-fill)', borderRadius: 0, border: '.5px solid var(--status-warning-border)', borderLeft: '2px solid var(--warning-amber)', alignItems: 'center' }}>
            <span style={{ fontSize: 13, color: 'var(--status-warning-text)', flex: 1 }}>
              {activeCouncilSession.pending_c6_prompt || 'The council is waiting for your input.'}
            </span>
            <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={councilPass} disabled={busy}>Continue</button>
            <button className="btn btn-ghost" style={{ fontSize: 12, color: 'var(--status-warning-text)' }} onClick={councilFinalize} disabled={busy}>Finalize</button>
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

        {pendingReferences.length > 0 && (
          <div style={{ marginBottom: 10, padding: 10, border: '1px solid var(--border)', borderRadius: 12, background: 'var(--surface)' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {pendingReferences.map((ref, i) => (
                <button key={i} type="button" className="btn btn-ghost" style={{ fontSize: 11 }} onClick={() => removeReference(i)} title="Remove reference">
                  {ref.kind === 'image' ? '🖼️' : ref.kind === 'document' ? '📄' : '📝'} {ref.title || ref.drive_file_name || 'Reference'} ×
                </button>
              ))}
              <button type="button" className="btn btn-ghost" style={{ fontSize: 11 }} onClick={clearReferences}>Clear all</button>
            </div>
          </div>
        )}

        {driveModalOpen && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            onClick={e => { if (e.target === e.currentTarget) setDriveModalOpen(false); }}>
            <div style={{ background: 'var(--white)', borderRadius: 0, padding: 24, width: 480, maxWidth: '95vw', maxHeight: '80vh', display: 'flex', flexDirection: 'column', gap: 12, border: '.5px solid var(--border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--brand)', fontFamily: 'var(--font-display)' }}>Pick from Drive</div>
                <button style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: 'var(--ink-muted)' }} onClick={() => setDriveModalOpen(false)}>✕</button>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                {(['all', 'image', 'document'] as const).map(f => (
                  <button key={f} type="button"
                    style={{ padding: '3px 12px', fontSize: 12, borderRadius: 2, border: '.5px solid', cursor: 'pointer', fontWeight: driveFilter === f ? 700 : 400, background: driveFilter === f ? 'var(--fill-active)' : 'transparent', color: driveFilter === f ? 'var(--brand)' : 'var(--ink-muted)', borderColor: driveFilter === f ? 'var(--brand)' : 'var(--border)' }}
                    onClick={() => { setDriveFilter(f); setDriveModalSelected(new Set()); }}>
                    {f === 'all' ? 'All' : f === 'image' ? 'Images' : 'Docs'}
                  </button>
                ))}
              </div>
              {driveCurrentFolder && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--ink-muted)', background: 'var(--bg-subtle)', border: '.5px solid var(--border)', borderRadius: 2, padding: '7px 9px' }}>
                  {driveFolderStack.length > 0 && (
                    <button className="artifact-btn ghost" style={{ padding: '2px 8px', fontSize: 11 }} disabled={driveModalLoading}
                      onClick={() => {
                        const nextStack = driveFolderStack.slice(0, -1);
                        loadDrivePickerFolder(nextStack[nextStack.length - 1] || DRIVE_ROOT, nextStack);
                      }}>
                      Back
                    </button>
                  )}
                  <span>Folder: <strong style={{ color: 'var(--ink-body)' }}>{driveCurrentFolder.name}</strong></span>
                </div>
              )}
              {driveModalLoading && <div style={{ color: 'var(--ink-muted)', fontSize: 13 }}>Loading Drive…</div>}
              {refError && <div style={{ color: 'var(--error)', fontSize: 13 }}>{refError}</div>}
              {!driveModalLoading && !refError && driveFolders.length === 0 && driveModalFiles.length === 0 && (
                <div style={{ color: 'var(--ink-muted)', fontSize: 13 }}>No folders or files found here.</div>
              )}
              {!driveModalLoading && (driveFolders.length > 0 || driveModalFiles.length > 0) && (
                <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {driveFolders.map(folder => (
                    <button key={folder.id}
                      style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', background: 'var(--linen)', border: '.5px solid var(--border-warm)', borderRadius: 2, cursor: 'pointer', textAlign: 'left', fontSize: 13 }}
                      onClick={() => { setDriveFilter('all'); setDriveModalSelected(new Set()); loadDrivePickerFolder(folder, [...driveFolderStack, folder]); }}>
                      <span style={{ fontSize: 20, flexShrink: 0 }}>📁</span>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--ink-body)' }}>{folder.name}</div>
                        <div style={{ color: 'var(--ink-muted)', fontSize: 11 }}>Open folder</div>
                      </div>
                    </button>
                  ))}
                  {driveModalFiles
                    .filter(f => driveFilter === 'all' || (driveFilter === 'image' ? f.mimeType.startsWith('image/') : DOC_MIMES_SET.has(f.mimeType)))
                    .map(f => {
                    const sel = driveModalSelected.has(f.id);
                    const isDoc = DOC_MIMES_SET.has(f.mimeType);
                    return (
                      <button key={f.id}
                        style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', background: sel ? 'var(--fill-active)' : 'transparent', border: `.5px solid ${sel ? 'var(--status-active-border)' : 'var(--border)'}`, borderRadius: 2, cursor: 'pointer', textAlign: 'left', fontSize: 13 }}
                        onClick={() => toggleDriveModalFile(f.id)}>
                        {isDoc
                          ? <span style={{ fontSize: 24, flexShrink: 0 }}>📄</span>
                          : f.thumbnailLink
                            ? <img src={f.thumbnailLink} alt={f.name} style={{ width: 44, height: 44, objectFit: 'cover', borderRadius: 2, flexShrink: 0, border: '.5px solid var(--border)' }} />
                            : <span style={{ fontSize: 20, flexShrink: 0 }}>🖼</span>
                        }
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--ink-body)' }}>{f.name}</div>
                          <div style={{ color: 'var(--ink-muted)', fontSize: 11 }}>{f.mimeType}{f.size ? ` · ${(f.size / 1024).toFixed(0)} KB` : ''}</div>
                        </div>
                        {sel && <span style={{ marginLeft: 'auto', color: 'var(--brand)', fontWeight: 700, flexShrink: 0 }}>✓</span>}
                      </button>
                    );
                  })}
                </div>
              )}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <button className="artifact-btn ghost" onClick={() => setDriveModalOpen(false)}>Cancel</button>
                {driveModalSelected.size > 0 && (
                  <button className="artifact-btn primary" onClick={attachDriveSelected}>
                    Attach {driveModalSelected.size} selected
                  </button>
                )}
              </div>
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
          <button
            className="btn-send"
            onClick={doSend}
            disabled={busy}
            title="Send"
          >
            ⏎
          </button>
          <button
            type="button"
            className="btn-send"
            onClick={openDrivePicker}
            disabled={busy}
            title="Attach from Drive"
          >
            {pendingReferences.length > 0
              ? <span style={{ fontSize: 11, fontWeight: 700 }}>{pendingReferences.length}</span>
              : <span style={{ fontSize: 15, lineHeight: 1 }}>+</span>
            }
          </button>
        </div>
      </div>
    </div>
  );
}
