import { useEffect, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { api } from '../api/client';
import { useActiveContext } from '../context/ActiveContext';

const PENDING_RUNS_KEY = 'bos_pending_run_decisions';

const FOOTER_NAV = [
  { to: '/stream', label: 'Stream', icon: '▶' },
  { to: '/cmo', label: 'CMO', icon: '◎' },
  { to: '/admin', label: 'Admin', icon: '⚙' },
];

type FooterNavProps = {
  pendingCount?: number;
};

function readStoredPendingCount(brandId?: string | null): number {
  try {
    const raw = localStorage.getItem(PENDING_RUNS_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return 0;
    return Object.values(parsed).filter((run: any) => {
      const createdAt = typeof run?.created_at === 'string' ? Date.parse(run.created_at) : NaN;
      const matchesBrand = !brandId || run?.brand_id === brandId;
      return matchesBrand && typeof run?.run_id === 'string' && Number.isFinite(createdAt);
    }).length;
  } catch {
    return 0;
  }
}

export function FooterNav({ pendingCount }: FooterNavProps) {
  const location = useLocation();
  const { activeBrand } = useActiveContext();
  const activeBrandId = activeBrand?.id ?? null;
  const [storedPendingCount, setStoredPendingCount] = useState(() => readStoredPendingCount(activeBrandId));
  const [streamCount, setStreamCount] = useState(0);

  useEffect(() => {
    if (pendingCount !== undefined) return;

    let cancelled = false;
    let inFlight = false;
    const refresh = () => {
      const localPending = readStoredPendingCount(activeBrandId);
      setStoredPendingCount(localPending);
      if (inFlight) return;
      inFlight = true;
      api.getRuns({
        limit: 1,
        offset: 0,
        brand_id: activeBrandId || undefined,
        exclude_approval_status: 'dismissed',
        include_preview: false,
      })
        .then(r => { if (!cancelled) setStreamCount(Math.max(r.total || 0, localPending)); })
        .catch(() => { if (!cancelled) setStreamCount(localPending); })
        .finally(() => { inFlight = false; });
    };
    const applyStreamCount = (event: Event) => {
      const count = Number((event as CustomEvent).detail?.count);
      if (Number.isFinite(count)) setStreamCount(count);
    };
    window.addEventListener('storage', refresh);
    window.addEventListener('focus', refresh);
    window.addEventListener('bos:focus-artifact', refresh);
    window.addEventListener('bos:stream-count', applyStreamCount);
    refresh();

    return () => {
      cancelled = true;
      window.removeEventListener('storage', refresh);
      window.removeEventListener('focus', refresh);
      window.removeEventListener('bos:focus-artifact', refresh);
      window.removeEventListener('bos:stream-count', applyStreamCount);
    };
  }, [activeBrandId, pendingCount]);

  const streamPendingCount = pendingCount ?? Math.max(streamCount, storedPendingCount);

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
            <span className="bos-proto-tab-ic">{icon}</span>
            <span>{label === 'Stream' && streamPendingCount > 0 ? `Stream(${streamPendingCount})` : label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
