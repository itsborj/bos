import { useEffect, useState, useCallback } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { api, clearApiKey } from '../api/client';
import { UIContext } from '../context/UIContext';
import { CmoChatProvider } from '../context/CmoChatContext';
import { CmoChat } from '../pages/CmoChat';
import { WorkspacePanel } from './WorkspacePanel';
import { SettingsModal } from './SettingsModal';
import type { ActiveBrand, ActiveCampaign, SettingsTab, WorkspaceTab } from '../context/UIContext';
import type { BrandResponse, RunResponse } from '../api/types';

const PROTOTYPE_NAV = [
  { to: '/stream', label: 'Stream', icon: '▶' },
  { to: '/cmo', label: 'CMO', icon: '◎' },
  { to: '/admin/objective-loop', label: 'Admin', icon: '⚙' },
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
  const [mobileStreamActive, setMobileStreamActive] = useState(false);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [workspaceTab, setWorkspaceTab]   = useState<WorkspaceTab>('campaigns');
  const [selectedRun, setSelectedRun]     = useState<RunResponse | null>(null);
  const [settingsOpen, setSettingsOpen]   = useState(false);
  const [settingsTab, setSettingsTab]     = useState<SettingsTab>('byok');
  const [pendingRunItems, setPendingRunItems] = useState<Record<string, RunResponse>>(() => readPendingRuns());
  const [conversations, setConversations] = useState<SavedConversation[]>([]);
  const [activeBrand, setActiveBrand] = useState<ActiveBrand | null>(() => readActiveBrand());
  const [brands, setBrands] = useState<BrandResponse[]>([]);
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

  // When returning to /cmo, scroll chat to bottom in case messages arrived while hidden.
  useEffect(() => {
    if (onCmo) window.dispatchEvent(new CustomEvent('bos:chat-scroll-bottom'));
  }, [onCmo]);

  useEffect(() => {
    writePendingRuns(pendingRunItems);
  }, [pendingRunItems]);

  useEffect(() => {
    if (activeBrand) {
      localStorage.setItem(ACTIVE_BRAND_KEY, JSON.stringify(activeBrand));
    } else {
      localStorage.removeItem(ACTIVE_BRAND_KEY);
    }
  }, [activeBrand]);

  useEffect(() => {
    let cancelled = false;
    api.getBrands()
      .then(res => { if (!cancelled) setBrands(res.brands || []); })
      .catch(() => { if (!cancelled) setBrands([]); });
    return () => { cancelled = true; };
  }, []);

  // Evict stale localStorage brand_id after brands load (e.g. after a staging DB reset that changes UUIDs).
  useEffect(() => {
    if (brands.length > 0 && activeBrand && !brands.some(b => b.id === activeBrand.id)) {
      setActiveBrand(null);
    }
  }, [brands, activeBrand]);

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
          <NavLink to="/stream" className="bos-proto-logo" aria-label="Klaroha Stream">
            <span>Klaroha</span>
            <em>Marketing, Engineered for Clarity.</em>
          </NavLink>
          <label className="bos-proto-brand-chip bos-proto-brand-select" title="Filter CMO and Stream by brand">
            <span>Brand</span>
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
          <div className="bos-proto-topbar-right">
            <span className="bos-proto-date">May 20</span>
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

        <div className="bos-proto-bottom-tabs">
          <div className="bos-proto-tab-group">
            {PROTOTYPE_NAV.map(({ to, label, icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) => `bos-proto-tab${isActive ? ' active' : ''}`}
              >
                <span>{icon}</span>
                <span>{label}</span>
                {label === 'Stream' && pendingRunList.length > 0 && <span className="bos-proto-tab-badge">{pendingRunList.length}</span>}
              </NavLink>
            ))}
          </div>
        </div>

      </div>
      </CmoChatProvider>
    </UIContext.Provider>
  );
}
