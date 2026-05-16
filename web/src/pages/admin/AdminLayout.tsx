import { Navigate, NavLink, Outlet } from 'react-router-dom';
import { getApiKey } from '../../api/client';

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
        <Outlet />
      </main>
    </div>
  );
}
