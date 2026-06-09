import { useEffect, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';

const PENDING_RUNS_KEY = 'bos_pending_run_decisions';

const FOOTER_NAV = [
  { to: '/stream', label: 'Stream', icon: '▶' },
  { to: '/cmo', label: 'CMO', icon: '◎' },
  { to: '/admin', label: 'Admin', icon: '⚙' },
];

type FooterNavProps = {
  pendingCount?: number;
};

function readStoredPendingCount(): number {
  try {
    const raw = localStorage.getItem(PENDING_RUNS_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return 0;
    return Object.values(parsed).filter((run: any) => {
      const createdAt = typeof run?.created_at === 'string' ? Date.parse(run.created_at) : NaN;
      return typeof run?.run_id === 'string' && Number.isFinite(createdAt);
    }).length;
  } catch {
    return 0;
  }
}

export function FooterNav({ pendingCount }: FooterNavProps) {
  const location = useLocation();
  const [storedPendingCount, setStoredPendingCount] = useState(() => readStoredPendingCount());

  useEffect(() => {
    if (pendingCount !== undefined) return;

    const refresh = () => setStoredPendingCount(readStoredPendingCount());
    window.addEventListener('storage', refresh);
    window.addEventListener('focus', refresh);
    const timer = window.setInterval(refresh, 5000);
    refresh();

    return () => {
      window.removeEventListener('storage', refresh);
      window.removeEventListener('focus', refresh);
      window.clearInterval(timer);
    };
  }, [pendingCount]);

  const streamPendingCount = pendingCount ?? storedPendingCount;

  return (
    <div className="bos-proto-bottom-tabs">
      <nav className="bos-proto-tab-group" aria-label="Primary">
        {FOOTER_NAV.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => {
              const active = label === 'Admin' ? location.pathname.startsWith('/admin') : isActive;
              return `bos-proto-tab${active ? ' active' : ''}`;
            }}
          >
            <span>{icon}</span>
            <span>{label}</span>
            {label === 'Stream' && streamPendingCount > 0 && <span className="bos-proto-tab-badge">{streamPendingCount}</span>}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
