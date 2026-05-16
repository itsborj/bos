import { useState, useEffect } from 'react';
import { Navigate, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { api, getApiKey } from '../../api/client';

const NAV_SECTIONS = [
  {
    label: 'Business',
    items: [
      { to: '/admin/brands',     label: 'Brands / Clients', icon: '⊞' },
      { to: '/admin/onboarding', label: 'Import Brief',     icon: '✦' },
      { to: '/admin/campaigns',  label: 'Campaign Plans',   icon: '◷' },
      { to: '/admin/calendar',   label: 'Scheduling',       icon: '📅' },
    ],
  },
  {
    label: 'Marketing Ops',
    items: [
      { to: '/admin/modules',     label: 'Specialists', icon: '◎' },
      { to: '/admin/connectors',  label: 'Connectors',  icon: '⇄' },
      { to: '/admin/reports',     label: 'Outcomes',    icon: '📊' },
    ],
  },
  {
    label: 'System',
    items: [
      { to: '/admin/providers', label: 'AI Providers', icon: '⚡' },
      { to: '/admin/billing',   label: 'Billing',      icon: '$' },
      { to: '/admin/runs',      label: 'Run Logs',     icon: '≡' },
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
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <div className="admin-logo">Klaroha</div>
        <nav className="admin-nav">
          {NAV_SECTIONS.map(section => (
            <div key={section.label}>
              <div className="admin-nav-section">{section.label}</div>
              {section.items.map(({ to, label, icon }) => (
                <NavLink
                  key={to}
                  to={to}
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
          <NavLink to="/admin/getting-started" className={({ isActive }) => `admin-back-link${isActive ? ' active' : ''}`}>
            → Getting Started
          </NavLink>
          <a href="/" className="admin-back-link">← CMO App</a>
        </div>
      </aside>
      <main className="admin-content">
        <GettingStartedBanner />
        <div className="admin-page-wrap">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
