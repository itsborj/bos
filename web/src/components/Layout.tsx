import { useEffect, useState, useCallback } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { clearApiKey } from '../api/client';
import { UIContext } from '../context/UIContext';
import { useActiveContext } from '../context/ActiveContext';
import { CmoChatProvider } from '../context/CmoChatContext';
import { CmoChat } from '../pages/CmoChat';
import { WorkspacePanel } from './WorkspacePanel';
import { SettingsModal } from './SettingsModal';
import { FooterNav } from './FooterNav';
import type { SettingsTab, WorkspaceTab } from '../context/UIContext';
import type { RunResponse } from '../api/types';

type PipelineStatus = {
  id: string;
  label: string;
  detail?: string;
  status: 'running' | 'done' | 'failed';
  startedAt: number;
};

const CHAT_MESSAGES_KEY = 'bos_chat_messages';
const CHAT_CONVERSATIONS_KEY = 'bos_chat_conversations';
const CHAT_ARCHIVE_KEY = 'bos_chat_archive_7d';
const CHAT_ARCHIVE_DAYS = 7;
const PENDING_RUNS_KEY = 'bos_pending_run_decisions';

type SavedConversation = {
  id: string;
  label: string;
  date: string;
  messages: unknown[];
};

function readJsonArray(key: string): unknown[] {
  try {
    const raw = localStorage.getItem(key);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function conversationLabel(messages: any[]): string {
  const firstUser = messages.find((m: any) => m.role === 'user' && m.text);
  return firstUser ? String(firstUser.text).slice(0, 50) : 'Current Chat';
}

function isRunResponse(value: unknown): value is RunResponse {
  return !!value && typeof value === 'object' && typeof (value as RunResponse).run_id === 'string' && typeof (value as RunResponse).module_id === 'string';
}

function stripLargeFields(block: unknown): unknown {
  if (!block || typeof block !== 'object' || Array.isArray(block)) return block;
  const { image_data_b64: _dropped, ...rest } = block as Record<string, unknown>;
  return rest;
}

function sanitizeRunForStorage(run: RunResponse): RunResponse {
  if (!run.result?.block) return run;
  return { ...run, result: { ...run.result, block: stripLargeFields(run.result.block) } };
}

function writePendingRuns(items: Record<string, RunResponse>): void {
  const sanitized = Object.fromEntries(
    Object.entries(items)
      .sort(([, a], [, b]) => +new Date(b.created_at) - +new Date(a.created_at))
      .slice(0, 50)
      .map(([k, v]) => [k, sanitizeRunForStorage(v)])
  );
  try {
    localStorage.setItem(PENDING_RUNS_KEY, JSON.stringify(sanitized));
  } catch {
    // Still over quota after stripping — clear rather than crash
    localStorage.removeItem(PENDING_RUNS_KEY);
  }
}

function readPendingRuns(): Record<string, RunResponse> {
  try {
    const raw = localStorage.getItem(PENDING_RUNS_KEY);
    if (raw !== null) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        const valid: Record<string, RunResponse> = {};
        for (const [k, v] of Object.entries(parsed)) {
          const createdAt = typeof (v as any)?.created_at === 'string' ? Date.parse((v as any).created_at) : NaN;
          if (
            v &&
            typeof (v as any).module_id === 'string' &&
            typeof (v as any).run_id === 'string' &&
            Number.isFinite(createdAt)
          ) {
            valid[k] = v as RunResponse;
          }
        }
        return valid;
      }
      return {};
    }
  } catch {
    return {};
  }

  // Backfill for browsers that generated approvals before pending decisions were persisted.
  const pending: Record<string, RunResponse> = {};
  const collect = (messages: unknown[]) => {
    messages.forEach((m: any) => {
      if (isRunResponse(m?.runResult)) pending[m.runResult.run_id] = m.runResult;
    });
  };
  collect(readJsonArray(CHAT_MESSAGES_KEY));
  (readJsonArray(CHAT_CONVERSATIONS_KEY) as SavedConversation[]).forEach(c => collect(c.messages || []));
  return pending;
}

export function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const onCmo = location.pathname === '/cmo';
  const { activeBrand, setActiveBrand, activeCampaign, setActiveCampaign, brands } = useActiveContext();
  const [mobileStreamActive, setMobileStreamActive] = useState(false);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [workspaceTab, setWorkspaceTab]   = useState<WorkspaceTab>('campaigns');
  const [selectedRun, setSelectedRun]     = useState<RunResponse | null>(null);
  const [settingsOpen, setSettingsOpen]   = useState(false);
  const [settingsTab, setSettingsTab]     = useState<SettingsTab>('byok');
  const [pendingRunItems, setPendingRunItems] = useState<Record<string, RunResponse>>(() => readPendingRuns());
  const [conversations, setConversations] = useState<SavedConversation[]>([]);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null);

  const refreshConversations = useCallback(() => {
    const cutoff = Date.now() - CHAT_ARCHIVE_DAYS * 24 * 60 * 60 * 1000;
    const runningArchive = (readJsonArray(CHAT_ARCHIVE_KEY) as any[])
      .filter(item => item?.updated_at && Date.parse(item.updated_at) >= cutoff)
      .map(item => ({
        id: String(item.id || `archive_${Date.parse(item.updated_at)}`),
        label: String(item.label || conversationLabel(item.messages || [])),
        date: new Date(item.updated_at).toLocaleDateString([], { month: 'short', day: 'numeric' }),
        messages: Array.isArray(item.messages) ? item.messages : [],
      })) as SavedConversation[];
    const legacyArchived = (readJsonArray(CHAT_CONVERSATIONS_KEY) as SavedConversation[])
      .filter(item => item?.messages?.length);
    const current = readJsonArray(CHAT_MESSAGES_KEY);
    const currentConvo: SavedConversation[] = current.length > 0 ? [{
      id: 'current',
      label: conversationLabel(current as any[]),
      date: 'Today',
      messages: current,
    }] : [];
    const seen = new Set<string>();
    const combined = [...currentConvo, ...runningArchive, ...legacyArchived].filter(item => {
      if (seen.has(item.id)) return false;
      seen.add(item.id);
      return true;
    });
    setConversations(combined);
  }, []);

  useEffect(() => {
    refreshConversations();
    window.addEventListener('bos:chat-updated', refreshConversations);
    return () => window.removeEventListener('bos:chat-updated', refreshConversations);
  }, [refreshConversations]);

  useEffect(() => {
    const handle = (e: Event) => {
      const run = (e as CustomEvent).detail;
      if (!run?.run_id) return;
      setPendingRunItems(prev => ({ ...prev, [run.run_id]: run }));
      setMobileStreamActive(true);
      // Stream's own side panel handles bos:focus-artifact. Do not open the
      // WorkspacePanel slide-over here — that surface was retired.
    };
    window.addEventListener('bos:focus-artifact', handle);
    return () => window.removeEventListener('bos:focus-artifact', handle);
  }, []);

  useEffect(() => {
    const handle = (e: Event) => {
      const detail = (e as CustomEvent).detail || {};
      if (!detail.id || !detail.label || !detail.status) return;
      const next: PipelineStatus = {
        id: String(detail.id),
        label: String(detail.label),
        detail: detail.detail ? String(detail.detail) : undefined,
        status: detail.status,
        startedAt: Number(detail.startedAt || Date.now()),
      };
      setPipelineStatus(next);
      if (next.status !== 'running') {
        window.setTimeout(() => {
          setPipelineStatus(current => current?.id === next.id ? null : current);
        }, 12_000);
      }
    };
    window.addEventListener('bos:pipeline-status', handle);
    return () => window.removeEventListener('bos:pipeline-status', handle);
  }, []);

  // When returning to /cmo, scroll chat to bottom in case messages arrived while hidden.
  useEffect(() => {
    if (onCmo) window.dispatchEvent(new CustomEvent('bos:chat-scroll-bottom'));
  }, [onCmo]);

  useEffect(() => {
    writePendingRuns(pendingRunItems);
  }, [pendingRunItems]);

  const addPendingRun = useCallback((run: RunResponse) => {
    setPendingRunItems(prev => ({ ...prev, [run.run_id]: run }));
  }, []);

  const removePendingRun = useCallback((runId: string) => {
    setPendingRunItems(prev => {
      const next = { ...prev };
      delete next[runId];
      return next;
    });
  }, []);



  const openWorkspace = (tab?: WorkspaceTab) => {
    if (tab) setWorkspaceTab(tab);
    setSelectedRun(null);
    setWorkspaceOpen(true);
  };

  const openRun = (run: RunResponse) => {
    setSelectedRun(run);
    setWorkspaceOpen(true);
  };

  const openSettings = (tab?: SettingsTab) => {
    if (tab) setSettingsTab(tab);
    setSettingsOpen(true);
  };

  const pendingRunList = Object.values(pendingRunItems).sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at));
  const pendingRuns = new Set(Object.keys(pendingRunItems));
  const startNewChat = () => {
    const current = readJsonArray(CHAT_MESSAGES_KEY);
    if (current.length > 0) {
      const archived = readJsonArray(CHAT_CONVERSATIONS_KEY) as SavedConversation[];
      const convo: SavedConversation = {
        id: `chat_${Date.now()}`,
        label: conversationLabel(current as any[]),
        date: new Date().toLocaleDateString([], { month: 'short', day: 'numeric' }),
        messages: current,
      };
      localStorage.setItem(CHAT_CONVERSATIONS_KEY, JSON.stringify([convo, ...archived].slice(0, 30)));
    }
    localStorage.removeItem(CHAT_MESSAGES_KEY);
    refreshConversations();
    window.dispatchEvent(new CustomEvent('bos:new-chat'));
  };

  const loadConversation = (convo: SavedConversation) => {
    localStorage.setItem(CHAT_MESSAGES_KEY, JSON.stringify(convo.messages));
    refreshConversations();
    window.dispatchEvent(new CustomEvent('bos:load-chat', { detail: { id: convo.id, messages: convo.messages } }));
  };

  void conversations;
  void startNewChat;
  void loadConversation;

  return (
    <UIContext.Provider value={{
      workspaceOpen, workspaceTab, openWorkspace, closeWorkspace: () => { setWorkspaceOpen(false); setSelectedRun(null); },
      selectedRun, openRun, closeRun: () => setSelectedRun(null),
      settingsOpen,  settingsTab,  openSettings,  closeSettings:  () => setSettingsOpen(false),
      pendingRuns, pendingRunItems: pendingRunList, addPendingRun, removePendingRun,
      activeBrand, setActiveBrand,
      activeCampaign, setActiveCampaign,
    }}>
      <CmoChatProvider>
      <div className="bos-proto-shell">
        <div className="bos-proto-topbar">
          <div className="bos-proto-topbar-left">
            <NavLink to="/stream" className="bos-proto-logo" aria-label="Klaroha Stream">
              <span>Klaroha</span>
            </NavLink>
            <label className="bos-proto-brand-chip bos-proto-brand-select" title="Filter CMO and Stream by brand">
              <span>{activeBrand ? 'Brand' : 'All Brands'}</span>
              <select
                aria-label="Filter by brand"
                value={activeBrand?.id ?? ''}
                onChange={e => {
                  const selected = brands.find(brand => brand.id === e.target.value);
                  setActiveBrand(selected ? { id: selected.id, name: selected.name } : null);
                }}
              >
                <option value="">All brands</option>
                {brands.map(brand => <option key={brand.id} value={brand.id}>{brand.name}</option>)}
              </select>
            </label>
          </div>

          <div className="bos-proto-topbar-center">
            {pipelineStatus && (
              <div className={`bos-background-task bos-background-task--topbar ${pipelineStatus.status}`} role="status" aria-live="polite">
                <div className="bos-background-task-icon" aria-hidden="true">
                  {pipelineStatus.status === 'running' ? <span className="bos-cmo-work-glyph">✦</span> : <span>{pipelineStatus.status === 'done' ? '✓' : '!'}</span>}
                </div>
                <div className="bos-background-task-copy">
                  <div className="bos-background-task-title">{pipelineStatus.status === 'running' ? 'CMO at work' : pipelineStatus.label}</div>
                  <div className="bos-background-task-detail">
                    {pipelineStatus.status === 'running'
                      ? (pipelineStatus.detail || 'Working in the background — you can keep browsing.')
                      : (pipelineStatus.detail || 'Background task updated.')}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="bos-proto-topbar-right">
            <NavLink to="/about" className="bos-proto-about-link">
              About
            </NavLink>
            <button
              className="bos-proto-signout"
              title="Sign out"
              onClick={() => { clearApiKey(); navigate('/auth'); }}
            >
              Sign out
            </button>
          </div>
        </div>

        <div className={`bos-proto-page-area ${workspaceOpen ? 'bos-proto-page-area-ws-open' : ''}`}>
          {/* CmoChat is always mounted so in-flight streams survive navigation.
              display:none hides it without unmounting — React state and async loops continue. */}
          <div
            className={`stream-cmo-shell${mobileStreamActive ? ' mobile-stream-active' : ''}`}
            style={onCmo ? undefined : { display: 'none' }}
          >
            <div className="stream-cmo-chat-col">
              <CmoChat />
            </div>
            <div className="stream-cmo-feed">
              <button className="mobile-back-btn" onClick={() => setMobileStreamActive(false)}>← Chat</button>
              {onCmo && <Outlet />}
            </div>
          </div>
          {!onCmo && <Outlet />}
        </div>

        <WorkspacePanel
          open={workspaceOpen}
          tab={workspaceTab}
          onTabChange={t => { setSelectedRun(null); setWorkspaceTab(t); }}
          onClose={() => { setWorkspaceOpen(false); setSelectedRun(null); }}
          selectedRun={selectedRun}
          onCloseRun={() => setSelectedRun(null)}
        />

        <SettingsModal
          open={settingsOpen}
          tab={settingsTab}
          onTabChange={setSettingsTab}
          onClose={() => setSettingsOpen(false)}
        />

        <FooterNav />

      </div>
      </CmoChatProvider>
    </UIContext.Provider>
  );
}
