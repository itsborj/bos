import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { useUI } from '../context/UIContext';
import { BlockRenderer } from '../components/blocks/BlockRenderer';
import { ReportsView } from '../pages/ReportsView';
import { SurfaceProvider } from '../surfaces/SurfaceContext';
import type { ArtifactRef } from '../utils/artifacts';
import { artifactStatusLabel, buildArtifactRef } from '../utils/artifacts';
import type { ChatHistoryItem, RunResponse } from '../api/types';
import type { BriefingBlock } from '../types/stream';

type MsgRole = 'ai' | 'user';
type ViewMode = 'chat' | 'reports';

interface Msg {
  id: string;
  role: MsgRole;
  text?: string;
  steps?: string[];        // live step labels shown while streaming
  stepsComplete?: boolean; // all steps done — show all as ✓, no active pulse
  artifactRef?: ArtifactRef;
  runResult?: RunResponse; // legacy persisted chat messages; rendered as artifact refs only
  time: Date;
}

const STORAGE_KEY = 'bos_chat_messages';

function uid() { return Math.random().toString(36).slice(2); }
function fmtTime(d: Date) { return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }

function normalizeStoredMessage(m: any): Msg {
  const artifactRef = m.artifactRef || (m.runResult ? buildArtifactRef(m.runResult as RunResponse) : undefined);
  return { ...m, artifactRef, runResult: undefined, time: new Date(m.time) };
}

function buildHistory(msgs: Msg[]): ChatHistoryItem[] {
  return msgs
    .filter(m => m.text && m.text !== '__typing__')
    .map(m => ({ role: m.role, text: m.text! }));
}

function textToBlock(text: string): BriefingBlock {
  return {
    id: uid(),
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
        <div className="artifact-eyebrow">Workspace artifact</div>
        <div className="artifact-title">{refData.title}</div>
        <div className="artifact-meta">
          {artifactStatusLabel(refData.status)} · {refData.type.replace(/_/g, ' ')} · Preview in Workspace/Stream
        </div>
      </div>
      <button className="artifact-btn primary" onClick={() => onOpen(refData.artifact_id)}>
        Review →
      </button>
    </div>
  );
}

export function CmoChat() {
  const { openWorkspace, openSettings, openRun, activeBrand, setActiveBrand, activeCampaign, setActiveCampaign, pendingRunItems } = useUI();
  const [viewMode, setViewMode] = useState<ViewMode>('chat');
  const [pendingPlan, setPendingPlan] = useState<boolean>(false);
  const [msgs, setMsgs] = useState<Msg[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
          return parsed.map(normalizeStoredMessage);
        }
      }
    } catch (e) {
      console.error('Failed to load chat history', e);
    }
    return [];
  });
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const toSave = msgs.filter(m => m.text !== '__typing__');
    if (toSave.length > 0) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
    window.dispatchEvent(new CustomEvent('bos:chat-updated'));
  }, [msgs]);

  useEffect(() => {
    const handleNew = () => setMsgs([]);
    const handleLoad = (event: Event) => {
      const messages = (event as CustomEvent).detail;
      if (Array.isArray(messages)) {
        setMsgs(messages.map(normalizeStoredMessage));
      }
    };
    window.addEventListener('bos:new-chat', handleNew);
    window.addEventListener('bos:load-chat', handleLoad);
    return () => {
      window.removeEventListener('bos:new-chat', handleNew);
      window.removeEventListener('bos:load-chat', handleLoad);
    };
  }, []);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [msgs]);

  function handleKlarAction(action: import('../api/types').KlarAction | null | undefined) {
    if (!action) return;
    if (action.action === 'brand_switch') {
      const d = action.data as { brand_id: string; brand_name: string };
      setActiveBrand({ id: d.brand_id, name: d.brand_name });
    } else if (action.action === 'brand_clear') {
      setActiveBrand(null);
    } else if (action.action === 'plan_draft') {
      setPendingPlan(true);
      const pd = action.data as { brand_id?: string; brand_name?: string };
      if (pd?.brand_id && pd?.brand_name) setActiveBrand({ id: pd.brand_id, name: pd.brand_name });
    } else if (action.action === 'plan_confirmed') {
      const d = action.data as { campaign_id: string; campaign_name: string };
      setActiveCampaign({ id: d.campaign_id, name: d.campaign_name });
      setPendingPlan(false);
    }
  }

  async function send(text: string, { skipUserMessage = false } = {}) {
    if (busy) return;
    const trimmed = text.trim();
    if (!trimmed) return;

    const history = buildHistory(msgs);

    if (!skipUserMessage) {
      setMsgs(m => [...m, { id: uid(), role: 'user', text: trimmed, time: new Date() }]);
    }
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    setBusy(true);

    const typingId = uid();
    setMsgs(m => [...m, { id: typingId, role: 'ai', text: '__typing__', steps: [], time: new Date() }]);

    try {
      for await (const event of api.chatStream(trimmed, history, activeBrand?.id ?? null, activeCampaign?.id ?? null)) {
        if (event.type === 'step') {
          setMsgs(m => m.map(msg =>
            msg.id === typingId
              ? { ...msg, steps: [...(msg.steps ?? []), event.label] }
              : msg
          ));
        } else if (event.type === 'module_result') {
          const refData = event.artifact_ref;
          setMsgs(m => [...m, { id: uid(), role: 'ai', artifactRef: refData, time: new Date() }]);
        } else if (event.type === 'reply') {
          handleKlarAction(event.klar_action);
          setMsgs(m => {
            // Mark step log complete (keeps it visible as ✓ list), then append reply
            const withComplete = m.map(msg =>
              msg.id === typingId ? { ...msg, stepsComplete: true } : msg
            );
            // If no steps accumulated, remove the typing bubble entirely
            const hasSteps = (m.find(x => x.id === typingId)?.steps ?? []).length > 0;
            const base = hasSteps ? withComplete : m.filter(x => x.id !== typingId);
            return event.text
              ? base.concat([{ id: uid(), role: 'ai', text: event.text, time: new Date() }])
              : base;
          });
        } else if (event.type === 'done') {
          // Remove typing bubble only if it has no steps (step log stays if it has steps)
          setMsgs(m => {
            const typing = m.find(x => x.id === typingId);
            if (!typing || (typing.steps ?? []).length > 0) return m;
            return m.filter(x => x.id !== typingId);
          });
        } else if (event.type === 'error') {
          setMsgs(m =>
            m.filter(x => x.id !== typingId).concat({
              id: uid(), role: 'ai', text: event.message, time: new Date(),
            })
          );
        }
      }
    } catch (e: unknown) {
      setMsgs(m =>
        m.filter(x => x.id !== typingId).concat({
          id: uid(), role: 'ai',
          text: `Error: ${e instanceof Error ? e.message : 'Something went wrong.'}`,
          time: new Date(),
        })
      );
    } finally {
      setBusy(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input); }
  }

  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  }

  async function handleOpenArtifact(artifactId: string) {
    const run = await api.getRun(artifactId);
    openRun(run);
  }

  const contextParts = [
    activeBrand?.name ? `Brand: ${activeBrand.name}` : 'No brand selected',
    activeCampaign?.name ? `Campaign: ${activeCampaign.name}` : 'No campaign selected',
    `${pendingRunItems.length} need attention`,
  ];

  const quickActions = [
    'What can you do?',
    'Plan a campaign',
  ];

  return (
    <div className="bos-cmo">
      {/* ── Header ── */}
      <div className="bos-cmo-header">
        <div className="bos-cmo-header-left">
          <div className="bos-cmo-avatar">CMO</div>
          <div>
            <div className="bos-cmo-name">Chief Marketing Officer</div>
            <div className="bos-cmo-status">{contextParts.join(' · ')}</div>
          </div>
        </div>
        <div className="bos-cmo-header-actions">
          <button 
            className={`bos-header-btn ${viewMode === 'reports' ? 'primary' : ''}`} 
            onClick={() => setViewMode(v => v === 'reports' ? 'chat' : 'reports')}
          >
            {viewMode === 'reports' ? 'Back to Chat' : 'View Reports'}
          </button>
          <button className="bos-header-btn" onClick={() => openWorkspace()}>Workspace →</button>
        </div>
      </div>

      {/* ── Messages ── */}
      <div className="bos-cmo-messages">
        {viewMode === 'reports' ? (
          <ReportsView />
        ) : msgs.map((msg, idx) => {
          const showSender = idx === 0 || msgs[idx - 1].role !== msg.role;

          if (msg.text === '__typing__') {
            const steps = msg.steps ?? [];
            const complete = msg.stepsComplete ?? false;
            return (
              <div key={msg.id} className="bos-msg">
                <div className="bos-msg-avatar">CMO</div>
                <div className="bos-msg-body">
                  {steps.length > 0 ? (
                    <div className={`bos-cmo-steps${complete ? ' bos-cmo-steps-done' : ''}`}>
                      {steps.map((label, i) => {
                        const done = complete || i < steps.length - 1;
                        return (
                          <div key={i} className={`bos-step ${done ? 'bos-step-done' : 'bos-step-active'}`}>
                            <span className="bos-step-icon">{done ? '✓' : '●'}</span>
                            <span className="bos-step-label">{label}</span>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="bos-cmo-typing">
                      <div className="bos-typing-dot" />
                      <div className="bos-typing-dot" />
                      <div className="bos-typing-dot" />
                    </div>
                  )}
                </div>
              </div>
            );
          }

          const artifactRef = msg.artifactRef || (msg.runResult ? buildArtifactRef(msg.runResult) : null);
          if (artifactRef) {
            return (
              <div key={msg.id} className="bos-msg">
                <div className="bos-msg-avatar">CMO</div>
                <div className="bos-msg-body">
                  <ArtifactReferenceCard refData={artifactRef} onOpen={handleOpenArtifact} />
                </div>
              </div>
            );
          }

          if (msg.role === 'user') {
            return (
              <div key={msg.id} className="bos-msg bos-msg-user">
                <div className="bos-msg-avatar">YOU</div>
                <div className="bos-msg-body">
                  {showSender && <span className="bos-msg-sender" style={{ textAlign: 'right' }}>You · {fmtTime(msg.time)}</span>}
                  <div className="bos-msg-text bos-msg-text-user">{msg.text}</div>
                </div>
              </div>
            );
          }

          return (
            <div key={msg.id} className="bos-msg">
              <div className="bos-msg-avatar">CMO</div>
              <div className="bos-msg-body">
                {showSender && <span className="bos-msg-sender">CMO · {fmtTime(msg.time)}</span>}
                <SurfaceProvider type="chat-inline">
                  <BlockRenderer block={textToBlock(msg.text!)} />
                </SurfaceProvider>
              </div>
            </div>
          );
        })}
        {viewMode !== 'reports' && <div ref={bottomRef} />}
      </div>

      {/* ── Input ── */}
      <div className="bos-cmo-input-area">
        {pendingPlan && (
          <div style={{ display: 'flex', gap: 8, marginBottom: 10, padding: '10px 14px', background: 'var(--soft-ivory)', borderRadius: 8, border: '1px solid var(--warm-gold)', alignItems: 'center' }}>
            <span style={{ fontSize: 13, color: 'var(--stone-deep)', flex: 1 }}>Plan drafted — confirm to create the campaign and tag all runs to it.</span>
            <button
              className="btn btn-dark btn-sm"
              onClick={() => send('@klar confirm', { skipUserMessage: false })}
              disabled={busy}
            >
              Confirm Plan
            </button>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setPendingPlan(false)}
              disabled={busy}
            >
              Dismiss
            </button>
          </div>
        )}
        <div className="bos-quick-actions" aria-label="Suggested CMO actions">
          <button type="button" onClick={() => window.dispatchEvent(new CustomEvent('bos:new-chat'))} disabled={busy}>
            New Chat
          </button>
          {quickActions.map(action => (
            <button key={action} type="button" onClick={() => send(action)} disabled={busy}>
              {action}
            </button>
          ))}
        </div>
        <div className="bos-input-row">
          <textarea
            ref={textareaRef}
            className="bos-cmo-textarea"
            rows={1}
            placeholder="Direct your CMO — brief a campaign, request a revision, or ask for a report..."
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            disabled={busy}
          />
          <button
            className="bos-cmo-send"
            onClick={() => send(input)}
            disabled={busy || !input.trim()}
          >
            Send
          </button>
        </div>
        <div className="bos-input-hint">
          Shift+Enter for new line ·{' '}
          <span className="bos-input-hint-link" onClick={() => openSettings('history')}>Run history</span>
          {' '}·{' '}
          <span className="bos-input-hint-link" onClick={() => { window.location.href = '/admin/workspace'; }}>Admin Workspace</span>
        </div>
      </div>
    </div>
  );
}
