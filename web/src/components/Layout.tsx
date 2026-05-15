import { useEffect, useState, useCallback } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { UIContext } from '../context/UIContext';
import { WorkspacePanel } from './WorkspacePanel';
import { SettingsModal } from './SettingsModal';
import type { ActiveBrand, ActiveCampaign, SettingsTab, WorkspaceTab } from '../context/UIContext';
import type { RunResponse } from '../api/types';

const MOBILE_NAV = [
  { to: '/stream',    label: 'Stream',    icon: '◈' },
  { to: '/cmo',       label: 'CMO',       icon: '◎' },
  { to: '/workspace', label: 'Workspace', icon: '⊞' },
];

const CHAT_MESSAGES_KEY = 'bos_chat_messages';
const CHAT_CONVERSATIONS_KEY = 'bos_chat_conversations';
const PENDING_RUNS_KEY = 'bos_pending_run_decisions';
const ACTIVE_BRAND_KEY = 'bos_active_brand';

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

function readActiveBrand(): ActiveBrand | null {
  try {
    const raw = localStorage.getItem(ACTIVE_BRAND_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    if (parsed && typeof parsed.id === 'string' && typeof parsed.name === 'string') {
      return { id: parsed.id, name: parsed.name };
    }
  } catch {
    return null;
  }
  return null;
}

function readPendingRuns(): Record<string, RunResponse> {
  try {
    const raw = localStorage.getItem(PENDING_RUNS_KEY);
    if (raw !== null) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed as Record<string, RunResponse>;
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
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [workspaceTab, setWorkspaceTab]   = useState<WorkspaceTab>('campaigns');
  const [selectedRun, setSelectedRun]     = useState<RunResponse | null>(null);
  const [settingsOpen, setSettingsOpen]   = useState(false);
  const [settingsTab, setSettingsTab]     = useState<SettingsTab>('byok');
  const [pendingRunItems, setPendingRunItems] = useState<Record<string, RunResponse>>(() => readPendingRuns());
  const [conversations, setConversations] = useState<SavedConversation[]>([]);
  const [activeBrand, setActiveBrand] = useState<ActiveBrand | null>(() => readActiveBrand());
  const [activeCampaign, setActiveCampaign] = useState<ActiveCampaign | null>(null);

  const refreshConversations = useCallback(() => {
    const archived = readJsonArray(CHAT_CONVERSATIONS_KEY) as SavedConversation[];
    const current = readJsonArray(CHAT_MESSAGES_KEY);
    const currentConvo: SavedConversation[] = current.length > 0 ? [{
      id: 'current',
      label: conversationLabel(current as any[]),
      date: 'Today',
      messages: current,
    }] : [];
    setConversations([...currentConvo, ...archived]);
  }, []);

  useEffect(() => {
    refreshConversations();
    window.addEventListener('bos:chat-updated', refreshConversations);
    return () => window.removeEventListener('bos:chat-updated', refreshConversations);
  }, [refreshConversations]);

  useEffect(() => {
    localStorage.setItem(PENDING_RUNS_KEY, JSON.stringify(pendingRunItems));
  }, [pendingRunItems]);

  useEffect(() => {
    if (activeBrand) {
      localStorage.setItem(ACTIVE_BRAND_KEY, JSON.stringify(activeBrand));
    } else {
      localStorage.removeItem(ACTIVE_BRAND_KEY);
    }
  }, [activeBrand]);

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
    window.dispatchEvent(new CustomEvent('bos:load-chat', { detail: convo.messages }));
  };

  const deleteConversation = (convo: SavedConversation) => {
    if (convo.id === 'current') {
      localStorage.removeItem(CHAT_MESSAGES_KEY);
      window.dispatchEvent(new CustomEvent('bos:new-chat'));
    } else {
      const archived = (readJsonArray(CHAT_CONVERSATIONS_KEY) as SavedConversation[])
        .filter(item => item.id !== convo.id);
      localStorage.setItem(CHAT_CONVERSATIONS_KEY, JSON.stringify(archived));
    }
    refreshConversations();
  };

  return (
    <UIContext.Provider value={{
      workspaceOpen, workspaceTab, openWorkspace, closeWorkspace: () => { setWorkspaceOpen(false); setSelectedRun(null); },
      selectedRun, openRun, closeRun: () => setSelectedRun(null),
      settingsOpen,  settingsTab,  openSettings,  closeSettings:  () => setSettingsOpen(false),
      pendingRuns, pendingRunItems: pendingRunList, addPendingRun, removePendingRun,
      activeBrand, setActiveBrand,
      activeCampaign, setActiveCampaign,
    }}>
      <div className="bos-shell">

        {/* ── Sidebar (desktop) ── */}
        <aside className="bos-sidebar">
          <div className="bos-sidebar-top">
            <NavLink to="/cmo" className="bos-logo-link"><span className="bos-logo">Klaroha</span></NavLink>
            <button className="bos-new-btn" onClick={startNewChat}>New Chat</button>
          </div>

          {activeBrand && (
            <div className="bos-brand-indicator">
              <span className="bos-brand-dot" />
              <span className="bos-brand-name">{activeBrand.name}</span>
              <button className="bos-brand-clear" onClick={() => setActiveBrand(null)} title="Clear brand context">✕</button>
            </div>
          )}
          {activeCampaign && (
            <div className="bos-brand-indicator" style={{ background: 'var(--surface2)', borderColor: 'var(--border)' }}>
              <span className="bos-brand-dot" style={{ background: '#6366f1' }} />
              <span className="bos-brand-name" style={{ fontSize: 11 }}>{activeCampaign.name}</span>
              <button className="bos-brand-clear" onClick={() => setActiveCampaign(null)} title="Clear campaign context">✕</button>
            </div>
          )}


          <div className="bos-sidebar-history">
            <div className="bos-section-label">This Week</div>
            {conversations.length === 0 ? (
              <div className="bos-convo-empty">No saved chats yet.</div>
            ) : conversations.map(convo => (
              <div key={convo.id} className={`bos-convo-row ${convo.id === 'current' ? 'active' : ''}`}>
                <button className="bos-convo-item" onClick={() => loadConversation(convo)} title={convo.label}>
                  <span className="bos-convo-label">{convo.label}</span>
                  <span className="bos-convo-date">{convo.date}</span>
                </button>
                <button
                  className="bos-convo-delete"
                  onClick={() => deleteConversation(convo)}
                  title="Delete chat"
                  aria-label={`Delete chat: ${convo.label}`}
                >
                  ×
                </button>
              </div>
            ))}
          </div>

          <NavLink to="/cmo" className={({ isActive }) => `bos-sidebar-link bos-sidebar-chat-link ${isActive ? 'active' : ''}`}>💬 Chat</NavLink>

          <div className="bos-sidebar-bottom">
            <button className="bos-sidebar-link" onClick={() => openSettings()}>⚙ Settings</button>
            <button className="bos-sidebar-link" onClick={() => openWorkspace()}>Workspace</button>
          </div>
        </aside>

        {/* ── CMO Center ── */}
        <div className={`bos-center ${workspaceOpen ? 'bos-center-ws-open' : ''}`}>
          <Outlet />
        </div>

        {/* ── Workspace Panel (fixed right) ── */}
        <WorkspacePanel
          open={workspaceOpen}
          tab={workspaceTab}
          onTabChange={t => { setSelectedRun(null); setWorkspaceTab(t); }}
          onClose={() => { setWorkspaceOpen(false); setSelectedRun(null); }}
          selectedRun={selectedRun}
          onCloseRun={() => setSelectedRun(null)}
        />

        {/* ── Settings Modal ── */}
        <SettingsModal
          open={settingsOpen}
          tab={settingsTab}
          onTabChange={setSettingsTab}
          onClose={() => setSettingsOpen(false)}
        />

        {/* ── Bottom Nav (mobile) ── */}
        <nav className="bottom-nav">
          {MOBILE_NAV.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `nav-tab${isActive ? ' active' : ''}`}
            >
              <span className="nav-tab-icon">{icon}</span>
              <span className="nav-tab-label">{label}</span>
            </NavLink>
          ))}
        </nav>
      </div>
    </UIContext.Provider>
  );
}
