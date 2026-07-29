import { useState, useEffect } from 'react';
import { Navigate, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { api, getApiKey, clearApiKey } from '../../api/client';
import { FooterNav } from '../../components/FooterNav';

type AdminNavItem = { to?: string; label: string; icon: string; parked?: boolean };
type AdminNavSection = { label: string; parked?: boolean; items: AdminNavItem[] };

const NAV_SECTIONS: AdminNavSection[] = [
  {
    label: 'Command',
    items: [
      { to: '/admin/overview',       label: 'Command Centre', icon: '⊟' },
      { to: '/admin/agent-activity', label: 'Approvals',      icon: '✓' },
      { to: '/admin/campaigns',      label: 'Campaign Board', icon: '◷' },
      { to: '/admin/reports',        label: 'Client Reports', icon: '◆' },
    ],
  },
  {
    label: 'Clients',
    items: [
      { to: '/admin/brands',   label: 'Brands / Clients', icon: '⊞' },
      { to: '/admin/calendar', label: 'Booking Pages',    icon: '▷' },
    ],
  },
  {
    label: 'Setup',
    items: [
      { to: '/admin/setup', label: 'Setup & Readiness', icon: '◌' },
      { to: '/admin/modules',         label: 'Capabilities',      icon: '⊡' },
      { to: '/admin/providers',       label: 'AI Providers',      icon: '⚡' },
      { to: '/admin/billing',         label: 'Billing',           icon: '$' },
    ],
  },
  {
    label: 'Advanced',
    items: [
      { to: '/admin/runs',           label: 'Run Logs',       icon: '≡' },
      { to: '/admin/watchpoints',    label: 'Watchpoints',    icon: '◈' },
      { to: '/admin/memory-audit',   label: 'Memory & Audit', icon: '◉' },
      { to: '/admin/stream-setup',   label: 'Stream Setup',   icon: '◎' },
      { to: '/admin/loop-flow',      label: 'Stream Flow',    icon: '→' },
    ],
  },
];

const GS_KEY = 'bos_gs_dismissed';

function GettingStartedBanner() {
  const [show, setShow] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (localStorage.getItem(GS_KEY) === '1') return;
    api.getOnboardingStatus()
      .then(s => {
        // Use the three core setup fields — all_ready also checks module routing
        // which may fail even when the user has completed all visible onboarding steps.
        // In multi-brand workspaces ws.brand_json may be empty while Brand rows have
        // full brand data. Use campaign_brand_kit_approved as the gate — approving a
        // kit requires brand context, so it implies profile is done.
        const coreSetupDone = s.workspace_configured && s.campaign_brand_kit_approved;
        if (!coreSetupDone) setShow(true);
      })
      .catch(() => {});
  }, []);

  if (!show) return null;

  return (
    <div className="gs-banner">
      <span className="gs-banner-text">Setup incomplete — finish setup and readiness before running campaigns.</span>
      <button
        className="btn btn-dark"
        style={{ fontSize: 12, padding: '3px 10px' }}
        onClick={() => navigate('/admin/setup')}
      >
        Open setup →
      </button>
      <button
        className="gs-banner-dismiss"
        title="Close"
        onClick={() => { localStorage.setItem(GS_KEY, '1'); setShow(false); }}
      >
        ✕
      </button>
    </div>
  );
}

export function AdminLayout() {
  const navigate = useNavigate();

  if (!getApiKey()) return <Navigate to="/auth" replace />;

  return (
    <div className="admin-app-frame">
      <div className="admin-shell">
      <aside className="admin-sidebar">
        <div className="admin-logo-block">
          <div className="admin-logo">Klaroha</div>
        </div>
        <nav className="admin-nav">
          {NAV_SECTIONS.map(section => (
            <div key={section.label}>
              {section.label && <div className="admin-nav-section">{section.label}</div>}
              {section.items.map(({ to, label, icon }) => (
                <NavLink
                  key={to}
                  to={to!}
                  className={({ isActive }: { isActive: boolean }) => `admin-nav-item${isActive ? ' active' : ''}`}
                >
                  <span className="admin-nav-icon">{icon}</span>
                  <span>{label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="admin-sidebar-footer">
          <NavLink to="/cmo" className="admin-nav-item">
            <span className="admin-nav-icon">←</span>
            <span>CMO Chat</span>
          </NavLink>
          <button
            className="admin-nav-item admin-signout-btn"
            onClick={() => { clearApiKey(); navigate('/auth'); }}
          >
            <span className="admin-nav-icon">⊘</span>
            <span>Sign out</span>
          </button>
        </div>
      </aside>
      <main className="admin-content">
        <GettingStartedBanner />
        <div className="admin-page-wrap">
          <Outlet />
        </div>
      </main>
      </div>
      <FooterNav />
    </div>
  );
}
