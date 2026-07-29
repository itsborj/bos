import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { buildArtifactRef } from '../utils/artifacts';
import type { ArtifactRef } from '../utils/artifacts';
import type { ChatHistoryItem, ChatReference, CouncilFinalizeResult, CouncilSessionState, HandoffBriefOut, KlarAction, ReferencePatch, RunResponse } from '../api/types';
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
  references?: ChatReference[];
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
const CONVERSATION_ID_KEY = 'bos_chat_conversation_id';
const CAMPAIGN_CONTEXT_KEY = 'bos_chat_campaign_context';
const CHAT_ARCHIVE_KEY = 'bos_chat_archive_7d';
const CHAT_ARCHIVE_DAYS = 7;
const CHAT_ARCHIVE_MAX = 100;

type ArchivedChat = {
  id: string;
  brand_id: string | null;
  label: string;
  started_at: string;
  updated_at: string;
  messages: unknown[];
};

function uid() { return Math.random().toString(36).slice(2); }

function chatStorageKey(brandId?: string | null): string {
  return brandId ? `${STORAGE_KEY}:${brandId}` : STORAGE_KEY;
}

function chatConversationIdKey(brandId?: string | null): string {
  return brandId ? `${CONVERSATION_ID_KEY}:${brandId}` : CONVERSATION_ID_KEY;
}

function chatCampaignContextKey(brandId?: string | null): string {
  return brandId ? `${CAMPAIGN_CONTEXT_KEY}:${brandId}` : CAMPAIGN_CONTEXT_KEY;
}

function readStoredCampaignContext(brandId?: string | null): string | null {
  try {
    return localStorage.getItem(chatCampaignContextKey(brandId)) || null;
  } catch {
    return null;
  }
}

function writeStoredCampaignContext(brandId: string | null | undefined, campaignId: string | null): void {
  try {
    const key = chatCampaignContextKey(brandId);
    if (campaignId) localStorage.setItem(key, campaignId);
    else localStorage.removeItem(key);
  } catch {
    // Browser storage is best-effort; the live ref still carries this turn's context.
  }
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

function conversationLabel(messages: Array<{ role?: string; text?: string }>): string {
  const firstUser = messages.find(m => m.role === 'user' && m.text);
  return firstUser?.text ? firstUser.text.slice(0, 60) : 'CMO chat';
}

function readArchive(): ArchivedChat[] {
  try {
    const raw = localStorage.getItem(CHAT_ARCHIVE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function pruneArchive(items: ArchivedChat[]): ArchivedChat[] {
  const cutoff = Date.now() - CHAT_ARCHIVE_DAYS * 24 * 60 * 60 * 1000;
  return items
    .filter(item => Number.isFinite(Date.parse(item.updated_at)) && Date.parse(item.updated_at) >= cutoff)
    .sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at))
    .slice(0, CHAT_ARCHIVE_MAX);
}

function writeArchive(items: ArchivedChat[]): void {
  try {
    localStorage.setItem(CHAT_ARCHIVE_KEY, JSON.stringify(pruneArchive(items)));
  } catch {
    try {
      localStorage.setItem(CHAT_ARCHIVE_KEY, JSON.stringify(pruneArchive(items).slice(0, 25)));
    } catch {
      localStorage.removeItem(CHAT_ARCHIVE_KEY);
    }
  }
}

function removeArchivedChat(conversationId: string): void {
  if (!conversationId) return;
  writeArchive(readArchive().filter(item => item.id !== conversationId));
}

function newConversationId(): string {
  return globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);
}

function readStoredConversationId(brandId?: string | null): string {
  try {
    return localStorage.getItem(chatConversationIdKey(brandId)) || newConversationId();
  } catch {
    return newConversationId();
  }
}

function writeRunningArchive(brandId: string | null | undefined, conversationId: string, messages: unknown[]): void {
  const cleanMessages = messages as Array<{ role?: string; text?: string }>;
  if (cleanMessages.length === 0) return;
  const now = new Date().toISOString();
  const existing = readArchive();
  const idx = existing.findIndex(item => item.id === conversationId);
  const next: ArchivedChat = {
    id: conversationId,
    brand_id: brandId ?? null,
    label: conversationLabel(cleanMessages),
    started_at: idx >= 0 ? existing[idx].started_at : now,
    updated_at: now,
    messages,
  };
  if (idx >= 0) existing[idx] = next;
  else existing.unshift(next);
  writeArchive(existing);
}

function buildHistory(msgs: Msg[]): ChatHistoryItem[] {
  return msgs
    .filter(m => m.text && m.text !== '__typing__')
    .map(m => ({ role: m.role, text: m.text! }));
}

function signalPipelineStatus(detail: { id: string; label: string; detail?: string; status: 'running' | 'done' | 'failed' }) {
  window.dispatchEvent(new CustomEvent('bos:pipeline-status', { detail: { startedAt: Date.now(), ...detail } }));
}

function chatToolProgress(label: string): { id: string; label: string; detail: string; status: 'running' } | null {
  const text = label.toLowerCase();
  if (text.includes('previs motion') || text.includes('storyboard.motion') || text.includes('video generation')) {
    return {
      id: 'cmo-previs-motion',
      label: 'Previs Motion video generation in progress',
      detail: 'BOS is generating the video. The revised or generated video will appear as a new Needs review artifact.',
      status: 'running',
    };
  }
  if (text.includes('storyboard') && (text.includes('image') || text.includes('render') || text.includes('generation'))) {
    return {
      id: 'cmo-storyboard-render',
      label: 'Storyboard image generation in progress',
      detail: 'BOS is rendering the storyboard image. The generated image will appear as a new Needs review artifact.',
      status: 'running',
    };
  }
  return null;
}

function chatToolCompletion(run: RunResponse): { id: string; label: string; detail: string; status: 'done' | 'failed' } | null {
  const moduleId = String(run.module_id || '').toLowerCase();
  const block = (run.result?.block || {}) as any;
  const blockType = String(block.type || block.legacy_type || '').toLowerCase();
  const failed = run.status === 'failed' || run.status === 'partial' || String(block.status || '').toLowerCase() === 'failed';

  if (moduleId.includes('storyboard.motion') || blockType.includes('previs') || blockType === 'video_asset') {
    return {
      id: 'cmo-previs-motion',
      label: failed ? 'Previs Motion video generation failed' : 'Previs Motion video ready',
      detail: failed ? (block.message || run.result?.content || 'Video generation failed.') : 'A new Previs Motion video artifact was added for review.',
      status: failed ? 'failed' : 'done',
    };
  }
  if (moduleId === 'storyboard.render' || (moduleId.includes('storyboard.render') && blockType === 'image_asset')) {
    return {
      id: 'cmo-storyboard-render',
      label: failed ? 'Storyboard image generation failed' : 'Storyboard image ready',
      detail: failed ? (block.message || run.result?.content || 'Storyboard image generation failed.') : 'A new Storyboard image artifact was added for review.',
      status: failed ? 'failed' : 'done',
    };
  }
  return null;
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
  activeCouncilSession: ActiveCouncilSession | null;
  pendingReferences: ChatReference[];
  addReference: (ref: ChatReference) => void;
  removeReference: (index: number) => void;
  clearReferences: () => void;
  deleteCurrentChat: () => Promise<void>;
  deleteMessage: (msgId: string) => void;
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
  const [activeCouncilSession, setActiveCouncilSession] = useState<ActiveCouncilSession | null>(null);
  const [pendingReferences, setPendingReferences] = useState<ChatReference[]>([]);
  const [workingReferences, setWorkingReferences] = useState<ChatReference[]>([]);
  const conversationIdRef = useRef<string>(readStoredConversationId(activeBrand?.id));
  const conversationCampaignIdRef = useRef<string | null>(readStoredCampaignContext(activeBrand?.id));
  const skipNextSaveRef = useRef(false);
  const sendInFlightRef = useRef(false);

  useEffect(() => {
    skipNextSaveRef.current = true;
    const storedMessages = readStoredMessages(activeBrand?.id);
    setMsgs(storedMessages);
    setStreamCardCtx(null);
    setActiveCouncilSession(null);
    setPendingReferences([]);
    setWorkingReferences([]);
    conversationIdRef.current = storedMessages.length > 0 ? readStoredConversationId(activeBrand?.id) : newConversationId();
    conversationCampaignIdRef.current = storedMessages.length > 0 ? readStoredCampaignContext(activeBrand?.id) : null;
  }, [activeBrand?.id]);

  useEffect(() => {
    if (skipNextSaveRef.current) {
      skipNextSaveRef.current = false;
      return;
    }
    const key = chatStorageKey(activeBrand?.id);
    const toSave = msgs
      .filter(m => m.text !== '__typing__' && !m.outcomeForm)
      .map(m => ({
        ...m,
        references: m.references?.map(r => {
          // strip base64 blobs from inline images
          if (r.kind === 'image' && r.source === 'inline') return { ...r, text: undefined };
          // cap text refs at 20K chars
          if (r.kind === 'text' && r.text && r.text.length > 20_000) return { ...r, text: r.text.slice(0, 20_000) + '\n[truncated]' };
          return r;
        }),
      }));
    try {
      if (toSave.length > 0) {
        localStorage.setItem(key, JSON.stringify(toSave));
        localStorage.setItem(chatConversationIdKey(activeBrand?.id), conversationIdRef.current);
        writeRunningArchive(activeBrand?.id ?? null, conversationIdRef.current, toSave);
      } else {
        localStorage.removeItem(key);
        localStorage.removeItem(chatConversationIdKey(activeBrand?.id));
        writeArchive(readArchive());
      }
    } catch {
      // quota exceeded — keep the last 10 messages only
      try {
        const trimmed = toSave.slice(-10);
        localStorage.setItem(key, JSON.stringify(trimmed));
        localStorage.setItem(chatConversationIdKey(activeBrand?.id), conversationIdRef.current);
        writeRunningArchive(activeBrand?.id ?? null, conversationIdRef.current, trimmed);
      } catch {
        localStorage.removeItem(key);
        localStorage.removeItem(chatConversationIdKey(activeBrand?.id));
      }
    }
    window.dispatchEvent(new CustomEvent('bos:chat-updated'));
  }, [activeBrand?.id, msgs]);

  useEffect(() => {
    const handleNew = () => {
      conversationIdRef.current = newConversationId();
      conversationCampaignIdRef.current = null;
      writeStoredCampaignContext(activeBrand?.id, null);
      setMsgs([]);
    };
    const handleLoad = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      const messages = Array.isArray(detail) ? detail : detail?.messages;
      if (detail?.id) conversationIdRef.current = String(detail.id);
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
      const d = action.data as { campaign_id: string; campaign_name: string; brand_id?: string | null };
      setActiveCampaign({ id: d.campaign_id, name: d.campaign_name, brand_id: d.brand_id ?? activeBrand?.id ?? null, status: 'active' });
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

  function normalizeReference(ref: ChatReference): ChatReference {
    return { ...ref, id: ref.id || globalThis.crypto?.randomUUID?.() || Math.random().toString(36).slice(2) };
  }

  function refKey(ref: ChatReference): string {
    return ref.id || ref.drive_file_id || `${ref.kind}:${ref.title || ref.drive_file_name || ''}`;
  }

  function mergeReferences(...groups: ChatReference[][]): ChatReference[] {
    const map = new Map<string, ChatReference>();
    for (const group of groups) {
      for (const ref of group) {
        const normalized = normalizeReference(ref);
        map.set(refKey(normalized), { ...(map.get(refKey(normalized)) || {}), ...normalized });
      }
    }
    return Array.from(map.values()).slice(0, 8);
  }

  function parseJsonPath(path: string): Array<string | number> {
    const tokens: Array<string | number> = [];
    let i = path.startsWith('$') ? 1 : 0;
    while (i < path.length) {
      if (path[i] === '.') {
        i += 1;
        const start = i;
        while (i < path.length && /[A-Za-z0-9_-]/.test(path[i])) i += 1;
        if (i > start) tokens.push(path.slice(start, i));
      } else if (path[i] === '[') {
        const end = path.indexOf(']', i);
        if (end < 0) break;
        const raw = path.slice(i + 1, end).trim();
        if (/^\d+$/.test(raw)) tokens.push(Number(raw));
        else tokens.push(raw.replace(/^['"]|['"]$/g, ''));
        i = end + 1;
      } else {
        i += 1;
      }
    }
    return tokens;
  }

  function applyReferencePatch(ref: ChatReference, patch: ReferencePatch): ChatReference {
    if (!ref.extraction_json) return ref;
    const nextJson = JSON.parse(JSON.stringify(ref.extraction_json)) as Record<string, unknown>;
    const tokens = parseJsonPath(patch.path);
    if (tokens.length === 0) return ref;
    let parent: any = nextJson;
    for (const token of tokens.slice(0, -1)) {
      if (parent == null) return ref;
      parent = parent[token as any];
    }
    const last = tokens[tokens.length - 1] as any;
    if (patch.op === 'remove') {
      if (Array.isArray(parent) && typeof last === 'number') parent.splice(last, 1);
      else if (parent && typeof parent === 'object') delete parent[last];
    } else if (parent && typeof parent === 'object') {
      parent[last] = patch.value;
    }
    return { ...ref, extraction_json: nextJson };
  }

  function handleReferencePatch(patch: ReferencePatch) {
    setWorkingReferences(prev => prev.map(ref => ref.id === patch.reference_id ? applyReferencePatch(ref, patch) : ref));
    setPendingReferences(prev => prev.map(ref => ref.id === patch.reference_id ? applyReferencePatch(ref, patch) : ref));
    setMsgs(prev => prev.map(msg => msg.references ? {
      ...msg,
      references: msg.references.map(ref => ref.id === patch.reference_id ? applyReferencePatch(ref, patch) : ref),
    } : msg));
  }

  function addReference(ref: ChatReference) {
    setPendingReferences(prev => mergeReferences(prev, [ref]));
  }

  function removeReference(index: number) {
    setPendingReferences(prev => prev.filter((_, i) => i !== index));
  }

  function clearReferences() {
    setPendingReferences([]);
  }

  async function deleteCurrentChat() {
    const conversationId = conversationIdRef.current;
    try {
      await api.deleteChatConversation(conversationId);
    } catch {
      // Chat transcripts are browser-local; still remove the visible chat even
      // if server-side reference cleanup is unavailable.
    }
    localStorage.removeItem(chatStorageKey(activeBrand?.id));
    localStorage.removeItem(chatConversationIdKey(activeBrand?.id));
    writeStoredCampaignContext(activeBrand?.id, null);
    removeArchivedChat(conversationId);
    conversationIdRef.current = newConversationId();
    conversationCampaignIdRef.current = null;
    setMsgs([]);
    setStreamCardCtx(null);
    setActiveCouncilSession(null);
    setPendingReferences([]);
    setWorkingReferences([]);
    window.dispatchEvent(new CustomEvent('bos:chat-updated'));
  }

  function deleteMessage(msgId: string) {
    setMsgs(prev => {
      const next = prev.filter(msg => msg.id !== msgId);
      const persistedNext = next.filter(msg => msg.text !== '__typing__' && !msg.outcomeForm);
      setWorkingReferences(mergeReferences(...next.map(msg => msg.references ?? [])));
      if (persistedNext.length === 0) {
        const conversationId = conversationIdRef.current;
        localStorage.removeItem(chatStorageKey(activeBrand?.id));
        localStorage.removeItem(chatConversationIdKey(activeBrand?.id));
        writeStoredCampaignContext(activeBrand?.id, null);
        removeArchivedChat(conversationId);
        conversationIdRef.current = newConversationId();
        conversationCampaignIdRef.current = null;
        setStreamCardCtx(null);
        setActiveCouncilSession(null);
      }
      return next;
    });
  }

  async function send(text: string, { skipUserMessage = false } = {}) {
    if (busy || sendInFlightRef.current) return;
    const trimmed = text.trim();
    if (!trimmed) return;
    sendInFlightRef.current = true;
    const referencesForTurn = mergeReferences(workingReferences, pendingReferences);

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
        sendInFlightRef.current = false;
        setBusy(false);
      }
      return;
    }

    const history = buildHistory(msgs);
    const liveCampaignId = activeCampaign?.status === 'active'
      ? activeCampaign.id
      : conversationCampaignIdRef.current;
    if (liveCampaignId) {
      conversationCampaignIdRef.current = liveCampaignId;
      writeStoredCampaignContext(activeBrand?.id, liveCampaignId);
    }

    if (!skipUserMessage) {
      setMsgs(m => [...m, { id: uid(), role: 'user', text: trimmed, references: referencesForTurn, time: new Date() }]);
    }
    setWorkingReferences(referencesForTurn);
    setPendingReferences([]);
    setBusy(true);

    const typingId = uid();
    let specificProgressSeen = false;
    let genericTaskFailed = false;
    signalPipelineStatus({
      id: 'cmo-chat-turn',
      label: 'CMO at work',
      detail: 'Working in the background — you can keep browsing.',
      status: 'running',
    });
    setMsgs(m => [...m, { id: typingId, role: 'ai', text: '__typing__', steps: [], time: new Date() }]);

    try {
      let streamedText = '';
      let sawStreamEvent = false;
      try {
        for await (const event of api.chatStream(trimmed, history, activeBrand?.id ?? null, liveCampaignId, referencesForTurn, conversationIdRef.current)) {
          sawStreamEvent = true;
          if (event.type === 'step') {
            setMsgs(m => m.map(msg =>
              msg.id === typingId ? { ...msg, steps: [...(msg.steps ?? []), event.label] } : msg
            ));
            const progress = chatToolProgress(event.label);
            if (progress) {
              specificProgressSeen = true;
              signalPipelineStatus(progress);
            }
          } else if (event.type === 'text_delta') {
            const delta = event.text || '';
            streamedText += delta;
            // Some providers emit empty/whitespace-only deltas before the first
            // visible token. Keep the thinking indicator in place until there is
            // actual content, otherwise the chat shows a blank AI bubble.
            if (streamedText.trim().length > 0) {
              setMsgs(m => m.map(msg =>
                msg.id === typingId ? { ...msg, text: streamedText, stepsComplete: true } : msg
              ));
            }
          } else if (event.type === 'module_result') {
            setMsgs(m => [...m, { id: uid(), role: 'ai', artifactRef: event.artifact_ref, time: new Date() }]);
            api.getRun(event.artifact_ref.artifact_id).then(run => {
              addPendingRun(run);
              const completion = chatToolCompletion(run);
              if (completion) signalPipelineStatus(completion);
            }).catch(() => {});
          } else if (event.type === 'reference_patch') {
            handleReferencePatch(event.patch);
          } else if (event.type === 'reply') {
            const councilData = handleKlarAction(event.klar_action);
            setMsgs(m => {
              const withComplete = m.map(msg =>
                msg.id === typingId ? { ...msg, stepsComplete: true } : msg
              );
              const hasSteps = (m.find(x => x.id === typingId)?.steps ?? []).length > 0;
              const base = (hasSteps || streamedText) ? withComplete : m.filter(x => x.id !== typingId);
              if (councilData) {
                const lastRound = councilData.rounds[councilData.rounds.length - 1] ?? [];
                return base.concat([{
                  id: uid(),
                  role: 'ai' as MsgRole,
                  time: new Date(),
                  councilRound: { round_num: councilData.rounds_completed, positions: lastRound },
                }]);
              }
              if (streamedText) {
                return base.map(msg =>
                  msg.id === typingId ? { ...msg, text: event.text || streamedText, stepsComplete: true } : msg
                );
              }
              return event.text
                ? base.concat([{ id: uid(), role: 'ai' as MsgRole, text: event.text, time: new Date() }])
                : base;
            });
          } else if (event.type === 'done') {
            if ('campaign_id' in event) {
              conversationCampaignIdRef.current = event.campaign_id || null;
              writeStoredCampaignContext(activeBrand?.id, event.campaign_id || null);
            }
            setMsgs(m => {
              const typing = m.find(x => x.id === typingId);
              if (!typing || (typing.steps ?? []).length > 0 || (typing.text && typing.text !== '__typing__')) return m;
              return m.filter(x => x.id !== typingId);
            });
          } else if (event.type === 'error') {
            if (!specificProgressSeen) {
              genericTaskFailed = true;
              signalPipelineStatus({
                id: 'cmo-chat-turn',
                label: 'CMO task failed',
                detail: event.message || 'Something went wrong.',
                status: 'failed',
              });
            }
            setMsgs(m =>
              m.filter(x => x.id !== typingId).concat({
                id: uid(), role: 'ai', text: event.message, time: new Date(),
              })
            );
          }
        }
      } catch (streamErr: unknown) {
        if (sawStreamEvent) throw streamErr;

        const fallback = await api.chat(trimmed, history, activeBrand?.id ?? null, liveCampaignId, referencesForTurn, conversationIdRef.current);
        const fallbackAny = fallback as typeof fallback & { tool_calls?: Array<Record<string, unknown>>; klar_action?: any };
        if (fallback.campaign_id) {
          conversationCampaignIdRef.current = fallback.campaign_id;
          writeStoredCampaignContext(activeBrand?.id, fallback.campaign_id);
        }

        if (Array.isArray(fallback.reference_patches)) {
          fallback.reference_patches.forEach(handleReferencePatch);
        }

        const councilData = handleKlarAction(fallbackAny.klar_action);
        setMsgs(m => {
          const withComplete = m.map(msg =>
            msg.id === typingId ? { ...msg, stepsComplete: true } : msg
          );
          const hasSteps = (m.find(x => x.id === typingId)?.steps ?? []).length > 0;
          const base = (hasSteps || streamedText) ? withComplete : m.filter(x => x.id !== typingId);
          if (councilData) {
            const lastRound = councilData.rounds[councilData.rounds.length - 1] ?? [];
            return base.concat([{
              id: uid(),
              role: 'ai' as MsgRole,
              time: new Date(),
              councilRound: { round_num: councilData.rounds_completed, positions: lastRound },
            }]);
          }
          return fallback.reply
            ? base.concat([{ id: uid(), role: 'ai' as MsgRole, text: fallback.reply, time: new Date() }])
            : base;
        });

        for (const toolResult of fallbackAny.tool_calls || []) {
          const runId = String(toolResult?.run_id || '');
          if (!runId) continue;
          try {
            const run = await api.getRun(runId);
            addPendingRun(run);
            setMsgs(m => [...m, { id: uid(), role: 'ai', artifactRef: buildArtifactRef(run), time: new Date() }]);
            const completion = chatToolCompletion(run);
            if (completion) signalPipelineStatus(completion);
          } catch {
            // Best-effort fallback only.
          }
        }
      }
    } catch (e: unknown) {
      if (!specificProgressSeen) {
        genericTaskFailed = true;
        signalPipelineStatus({
          id: 'cmo-chat-turn',
          label: 'CMO task failed',
          detail: e instanceof Error ? e.message : 'Something went wrong.',
          status: 'failed',
        });
      }
      setMsgs(m =>
        m.filter(x => x.id !== typingId).concat({
          id: uid(), role: 'ai',
          text: `Error: ${e instanceof Error ? e.message : 'Something went wrong.'}`,
          time: new Date(),
        })
      );
    } finally {
      if (!specificProgressSeen && !genericTaskFailed) {
        signalPipelineStatus({
          id: 'cmo-chat-turn',
          label: 'CMO finished',
          detail: 'Your chat response is ready.',
          status: 'done',
        });
      }
      sendInFlightRef.current = false;
      setBusy(false);
    }
  }

  async function handleOutcomeConfirm(msgId: string, outcomeType: string, value: string, notes: string, objectiveSummary?: string) {
    try {
      await api.evaluateOutcome({
        brand_id: activeBrand?.id,
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
      msgs, busy, streamCardCtx, activeCouncilSession,
      pendingReferences, addReference, removeReference, clearReferences, deleteCurrentChat, deleteMessage,
      send, councilPass, councilFinalize, handleOutcomeConfirm, handleOutcomeCancel,
    }}>
      {children}
    </CmoChatContext.Provider>
  );
}
