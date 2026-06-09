import { useState, useEffect } from 'react';
import { Navigate, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { api, getApiKey } from '../../api/client';
import { FooterNav } from '../../components/FooterNav';

type AdminNavItem = { to?: string; label: string; icon: string; parked?: boolean };
type AdminNavSection = { label: string; parked?: boolean; items: AdminNavItem[] };

const NAV_SECTIONS: AdminNavSection[] = [
  {
    label: '',
    items: [
      { to: '/admin/overview', label: 'Dashboard', icon: '⊟' },
    ],
  },
  {
    label: 'Operate',
    items: [
      { to: '/admin/campaigns', label: 'Campaign Board', icon: '◷' },
      { to: '/admin/calendar',  label: 'Scheduling',     icon: '📅' },
      { to: '/admin/reports',   label: 'Outcomes',       icon: '📊' },
    ],
  },
  {
    label: 'Manage',
    items: [
      { to: '/admin/brands',   label: 'Brands / Clients', icon: '⊞' },
      { to: '/admin/modules',  label: 'Specialists',      icon: '⊡' },
    ],
  },
  {
    label: 'Settings',
    items: [
      { to: '/admin/providers',      label: 'AI Providers',   icon: '⚡' },
      { to: '/admin/objective-loop', label: 'Loop Setup',     icon: '◎' },
      { to: '/admin/watchpoints',    label: 'Watchpoints',    icon: '◈' },
      { to: '/admin/memory-audit',   label: 'Memory & Audit', icon: '◉' },
    ],
  },
  {
    label: 'Debug',
    items: [
      { to: '/admin/runs',      label: 'Run Logs',  icon: '≡' },
      { to: '/admin/loop-flow', label: 'Loop Flow', icon: '→' },
    ],
  },
  {
    label: 'Post-Gate 2',
    parked: true,
    items: [
      { to: '/admin/council-seats', label: 'Council Seats', icon: '◇' },
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
        // brand_profile_configured can be false in multi-brand workspaces where
        // ws.brand_json is empty but Brand rows have brand_json. Use campaign_brand_kit_approved
        // as the gate — approving a kit requires brand context, so it implies profile is done.
        const coreSetupDone = s.workspace_configured && s.campaign_brand_kit_approved;
        if (!coreSetupDone) setShow(true);
      })
      .catch(() => {});
  }, []);

  if (!show) return null;

  return (
    <div className="gs-banner">
      <span className="gs-banner-text">Setup incomplete — complete getting started before running campaigns.</span>
      <button
        className="btn btn-dark"
        style={{ fontSize: 12, padding: '3px 10px' }}
        onClick={() => navigate('/admin/getting-started')}
      >
        View checklist →
      </button>
      <button
        className="gs-banner-dismiss"
        title="Dismiss"
        onClick={() => { localStorage.setItem(GS_KEY, '1'); setShow(false); }}
      >
        ✕
      </button>
    </div>
  );
}

export function AdminLayout() {
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
              {section.label && <div className={`admin-nav-section${section.parked ? ' parked' : ''}`}>{section.label}</div>}
              {section.items.map(({ to, label, icon, parked }) => (
                parked || !to ? (
                  <span
                    key={label}
                    className="admin-nav-item parked"
                    title="Post-Gate 2 — not active in current build"
                  >
                    <span className="admin-nav-icon">{icon}</span>
                    <span>{label}</span>
                  </span>
                ) : (
                  <NavLink
                    key={to}
                    to={to}
                    className={({ isActive }: { isActive: boolean }) => `admin-nav-item${isActive ? ' active' : ''}`}
                  >
                    <span className="admin-nav-icon">{icon}</span>
                    <span>{label}</span>
                  </NavLink>
                )
              ))}
            </div>
          ))}
        </nav>
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
