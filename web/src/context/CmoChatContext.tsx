import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { buildArtifactRef } from '../utils/artifacts';
import type { ArtifactRef } from '../utils/artifacts';
import type { ChatHistoryItem, CouncilFinalizeResult, CouncilSessionState, HandoffBriefOut, KlarAction, ObjectiveOut, RunResponse } from '../api/types';
import { useUI } from './UIContext';

export type MsgRole = 'ai' | 'user';

export interface OutcomeConfirmData {
  outcomeType: string;
  value: string;
  objectiveSummary?: string;
}

export interface CouncilRoundMsg {
  round_num: number;
  positions: Array<{ seat_id: string; display_name: string; content: string; timestamp: string }>;
  c6_injection?: { content: string; round_boundary: number };
}

export interface Msg {
  id: string;
  role: MsgRole;
  text?: string;
  steps?: string[];
  stepsComplete?: boolean;
  artifactRef?: ArtifactRef;
  runResult?: RunResponse;
  time: Date;
  outcomeForm?: boolean;
  outcomeConfirm?: OutcomeConfirmData;
  handoffBrief?: HandoffBriefOut;
  councilRound?: CouncilRoundMsg;
  councilBrief?: CouncilFinalizeResult;
}

export interface StreamCardCtx {
  sourceType: 'update' | 'artifact';
  id: string;
  type: string;
  actionLabel: string;
  data_json?: Record<string, unknown>;
  priority?: string;
  source_key?: string;
}

const STORAGE_KEY = 'bos_chat_messages';

function uid() { return Math.random().toString(36).slice(2); }

function chatStorageKey(brandId?: string | null): string {
  return brandId ? `${STORAGE_KEY}:${brandId}` : STORAGE_KEY;
}

function normalizeStoredMessage(m: any): Msg {
  const artifactRef = m.artifactRef || (m.runResult ? buildArtifactRef(m.runResult as RunResponse) : undefined);
  return { ...m, artifactRef, runResult: undefined, time: new Date(m.time) };
}

function readStoredMessages(brandId?: string | null): Msg[] {
  try {
    const saved = localStorage.getItem(chatStorageKey(brandId));
    if (saved) {
      const parsed = JSON.parse(saved);
      if (Array.isArray(parsed)) return parsed.map(normalizeStoredMessage);
    }
  } catch {}
  return [];
}

function buildHistory(msgs: Msg[]): ChatHistoryItem[] {
  return msgs
    .filter(m => m.text && m.text !== '__typing__')
    .map(m => ({ role: m.role, text: m.text! }));
}

export interface ActiveCouncilSession {
  session_id: string;
  status: string;
  pending_c6_prompt: string | null;
}

export interface CmoChatContextValue {
  msgs: Msg[];
  busy: boolean;
  streamCardCtx: StreamCardCtx | null;
  activeObjective: ObjectiveOut | null;
  activeCouncilSession: ActiveCouncilSession | null;
  send: (text: string, opts?: { skipUserMessage?: boolean }) => Promise<void>;
  councilPass: () => Promise<void>;
  councilFinalize: () => Promise<void>;
  handleOutcomeConfirm: (msgId: string, outcomeType: string, value: string, notes: string, objectiveSummary?: string) => Promise<void>;
  handleOutcomeCancel: (msgId: string) => void;
}

export const CmoChatContext = createContext<CmoChatContextValue | null>(null);

export function useCmoChat(): CmoChatContextValue {
  const ctx = useContext(CmoChatContext);
  if (!ctx) throw new Error('useCmoChat must be inside CmoChatProvider');
  return ctx;
}

export function CmoChatProvider({ children }: { children: React.ReactNode }) {
  const { activeBrand, activeCampaign, setActiveBrand, setActiveCampaign, addPendingRun } = useUI();

  const [msgs, setMsgs] = useState<Msg[]>(() => readStoredMessages(activeBrand?.id));
  const [busy, setBusy] = useState(false);
  const [streamCardCtx, setStreamCardCtx] = useState<StreamCardCtx | null>(null);
  const [activeObjective, setActiveObjective] = useState<ObjectiveOut | null>(null);
  const [activeCouncilSession, setActiveCouncilSession] = useState<ActiveCouncilSession | null>(null);
  const skipNextSaveRef = useRef(false);

  useEffect(() => {
    skipNextSaveRef.current = true;
    setMsgs(readStoredMessages(activeBrand?.id));
    setStreamCardCtx(null);
    setActiveCouncilSession(null);
  }, [activeBrand?.id]);

  useEffect(() => {
    if (skipNextSaveRef.current) {
      skipNextSaveRef.current = false;
      return;
    }
    const key = chatStorageKey(activeBrand?.id);
    const toSave = msgs.filter(m => m.text !== '__typing__' && !m.outcomeForm);
    if (toSave.length > 0) {
      localStorage.setItem(key, JSON.stringify(toSave));
    } else {
      localStorage.removeItem(key);
    }
    window.dispatchEvent(new CustomEvent('bos:chat-updated'));
  }, [activeBrand?.id, msgs]);

  useEffect(() => {
    api.getActiveObjective(activeBrand?.id).catch(() => null).then(obj => setActiveObjective(obj));
  }, [activeBrand?.id]);

  useEffect(() => {
    const handleNew = () => setMsgs([]);
    const handleLoad = (event: Event) => {
      const messages = (event as CustomEvent).detail;
      if (Array.isArray(messages)) setMsgs(messages.map(normalizeStoredMessage));
    };
    const handleCardCtx = (event: Event) => {
      setStreamCardCtx((event as CustomEvent).detail as StreamCardCtx);
    };
    window.addEventListener('bos:new-chat', handleNew);
    window.addEventListener('bos:load-chat', handleLoad);
    window.addEventListener('bos:stream-card-context', handleCardCtx);
    return () => {
      window.removeEventListener('bos:new-chat', handleNew);
      window.removeEventListener('bos:load-chat', handleLoad);
      window.removeEventListener('bos:stream-card-context', handleCardCtx);
    };
  }, []);

  function handleKlarAction(action: KlarAction | null | undefined): CouncilSessionState | null {
    if (!action) return null;
    if (action.action === 'brand_switch') {
      const d = action.data as { brand_id: string; brand_name: string };
      setActiveBrand({ id: d.brand_id, name: d.brand_name });
    } else if (action.action === 'brand_clear') {
      setActiveBrand(null);
    } else if (action.action === 'plan_confirmed') {
      const d = action.data as { campaign_id: string; campaign_name: string };
      setActiveCampaign({ id: d.campaign_id, name: d.campaign_name });
    } else if (action.action === 'council_session') {
      const d = action.data as unknown as CouncilSessionState;
      setActiveCouncilSession({ session_id: d.session_id, status: d.status, pending_c6_prompt: d.pending_c6_prompt });
      return d;
    }
    return null;
  }

  function appendCouncilRound(result: CouncilSessionState) {
    const lastRound = result.rounds[result.rounds.length - 1] ?? [];
    const roundNum = result.rounds_completed;
    setActiveCouncilSession({ session_id: result.session_id, status: result.status, pending_c6_prompt: result.pending_c6_prompt });
    setMsgs(m => [...m, {
      id: uid(),
      role: 'ai',
      time: new Date(),
      councilRound: { round_num: roundNum, positions: lastRound },
    }]);
  }

  async function councilPass() {
    if (!activeCouncilSession || busy) return;
    setBusy(true);
    setMsgs(m => [...m, { id: uid(), role: 'user', text: '(continue)', time: new Date() }]);
    const typingId = uid();
    setMsgs(m => [...m, { id: typingId, role: 'ai', text: '__typing__', steps: ['Convening next round…'], time: new Date() }]);
    try {
      const result = await api.councilC6Respond(activeCouncilSession.session_id, null);
      setMsgs(m => m.filter(x => x.id !== typingId));
      appendCouncilRound(result);
    } catch (e: unknown) {
      setMsgs(m => m.filter(x => x.id !== typingId).concat({ id: uid(), role: 'ai', text: `Council error: ${e instanceof Error ? e.message : 'Something went wrong.'}`, time: new Date() }));
    } finally {
      setBusy(false);
    }
  }

  async function councilFinalize() {
    if (!activeCouncilSession || busy) return;
    setBusy(true);
    setMsgs(m => [...m, { id: uid(), role: 'user', text: '(finalize)', time: new Date() }]);
    try {
      const result = await api.councilFinalize(activeCouncilSession.session_id);
      setActiveCouncilSession(null);
      setMsgs(m => [...m, { id: uid(), role: 'ai', time: new Date(), councilBrief: result }]);
    } catch (e: unknown) {
      setMsgs(m => [...m, { id: uid(), role: 'ai', text: `Finalize error: ${e instanceof Error ? e.message : 'Something went wrong.'}`, time: new Date() }]);
    } finally {
      setBusy(false);
    }
  }

  async function send(text: string, { skipUserMessage = false } = {}) {
    if (busy) return;
    const trimmed = text.trim();
    if (!trimmed) return;

    // Route to council c6-respond when a session is active
    if (activeCouncilSession?.status === 'awaiting_c6') {
      if (!skipUserMessage) setMsgs(m => [...m, { id: uid(), role: 'user', text: trimmed, time: new Date() }]);
      setBusy(true);
      const typingId = uid();
      setMsgs(m => [...m, { id: typingId, role: 'ai', text: '__typing__', steps: ['Convening next round…'], time: new Date() }]);
      try {
        const result = await api.councilC6Respond(activeCouncilSession.session_id, trimmed);
        setMsgs(m => m.filter(x => x.id !== typingId));
        appendCouncilRound(result);
      } catch (e: unknown) {
        setMsgs(m => m.filter(x => x.id !== typingId).concat({ id: uid(), role: 'ai', text: `Council error: ${e instanceof Error ? e.message : 'Something went wrong.'}`, time: new Date() }));
      } finally {
        setBusy(false);
      }
      return;
    }

    const history = buildHistory(msgs);

    if (!skipUserMessage) {
      setMsgs(m => [...m, { id: uid(), role: 'user', text: trimmed, time: new Date() }]);
    }
    setBusy(true);

    const typingId = uid();
    setMsgs(m => [...m, { id: typingId, role: 'ai', text: '__typing__', steps: [], time: new Date() }]);

    try {
      for await (const event of api.chatStream(trimmed, history, activeBrand?.id ?? null, activeCampaign?.id ?? null)) {
        if (event.type === 'step') {
          setMsgs(m => m.map(msg =>
            msg.id === typingId ? { ...msg, steps: [...(msg.steps ?? []), event.label] } : msg
          ));
        } else if (event.type === 'module_result') {
          setMsgs(m => [...m, { id: uid(), role: 'ai', artifactRef: event.artifact_ref, time: new Date() }]);
          if (event.artifact_ref.status !== 'failed') {
            api.getRun(event.artifact_ref.artifact_id).then(addPendingRun).catch(() => {});
          }
        } else if (event.type === 'reply') {
          const councilData = handleKlarAction(event.klar_action);
          setMsgs(m => {
            const withComplete = m.map(msg =>
              msg.id === typingId ? { ...msg, stepsComplete: true } : msg
            );
            const hasSteps = (m.find(x => x.id === typingId)?.steps ?? []).length > 0;
            const base = hasSteps ? withComplete : m.filter(x => x.id !== typingId);
            if (councilData) {
              const lastRound = councilData.rounds[councilData.rounds.length - 1] ?? [];
              return base.concat([{
                id: uid(),
                role: 'ai' as MsgRole,
                time: new Date(),
                councilRound: { round_num: councilData.rounds_completed, positions: lastRound },
              }]);
            }
            return event.text
              ? base.concat([{ id: uid(), role: 'ai' as MsgRole, text: event.text, time: new Date() }])
              : base;
          });
        } else if (event.type === 'done') {
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

  async function handleOutcomeConfirm(msgId: string, outcomeType: string, value: string, notes: string, objectiveSummary?: string) {
    try {
      await api.evaluateOutcome({
        brand_id: activeBrand?.id,
        objective_id: activeObjective?.id,
        summary: value + (notes ? ` — ${notes}` : ''),
        metrics: { outcome_type: outcomeType },
        confidence_source: 'manually_reported',
      });
      setMsgs(m => m.map(msg =>
        msg.id === msgId
          ? { ...msg, outcomeForm: false, outcomeConfirm: { outcomeType, value, objectiveSummary } }
          : msg
      ));
    } catch (e) {
      setMsgs(m => m.map(msg =>
        msg.id === msgId
          ? { ...msg, outcomeForm: false, text: `Error recording outcome: ${e instanceof Error ? e.message : 'Unknown error'}` }
          : msg
      ));
    }
  }

  function handleOutcomeCancel(msgId: string) {
    setMsgs(m => m.filter(msg => msg.id !== msgId));
  }

  return (
    <CmoChatContext.Provider value={{
      msgs, busy, streamCardCtx, activeObjective, activeCouncilSession,
      send, councilPass, councilFinalize, handleOutcomeConfirm, handleOutcomeCancel,
    }}>
      {children}
    </CmoChatContext.Provider>
  );
}
