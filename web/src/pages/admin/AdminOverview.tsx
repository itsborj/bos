import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import type { BillingSummary, ModuleInfo, ProviderInfo, RunListItem } from '../../api/types';
import { StatusBadge } from '../../components/StatusBadge';

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function AdminOverview() {
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [recentRuns, setRecentRuns] = useState<RunListItem[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getBillingSummary().catch(() => null),
      api.getRuns({ limit: 5 }).catch(() => null),
      api.getProviders().catch(() => ({ providers: [] as ProviderInfo[] })),
      api.getVerticals()
        .then(({ verticals }) =>
          Promise.all(verticals.map(v => api.getModules(v.vertical).then(r => r.modules)))
        )
        .then(groups => groups.flat())
        .catch(() => [] as ModuleInfo[]),
    ]).then(([bill, runs, provs, mods]) => {
      setBilling(bill);
      setRecentRuns(runs?.runs ?? []);
      setProviders(provs?.providers ?? []);
      setModules(mods);
      setLoading(false);
    });
  }, []);

  const connectedProviders = providers.filter(p => p.has_platform_key || p.connected);
  const systemHealthy = connectedProviders.length > 0;

  if (loading) {
    return (
      <div className="admin-page">
        <div className="loading-full"><span className="spinner" /></div>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">System Overview</div>
          <div className="admin-page-subtitle">Operational health for AI providers, specialists, billing, and debug logs</div>
        </div>
        <Link to="/admin/getting-started" className="btn btn-dark btn-sm">Open setup guide</Link>
      </div>

      <div className="admin-stat-grid">
        <div className="admin-stat-card">
          <div className="admin-stat-label">Total Runs</div>
          <div className="admin-stat-value">{billing?.total_runs ?? '—'}</div>
        </div>
        <div className="admin-stat-card">
          <div className="admin-stat-label">Provider Cost</div>
          <div className="admin-stat-value">
            {billing ? `$${billing.total_provider_cost.toFixed(2)}` : '—'}
          </div>
          {billing && (
            <div className="admin-stat-sub">{billing.total_tokens?.toLocaleString()} tokens</div>
          )}
        </div>
        <div className="admin-stat-card">
          <div className="admin-stat-label">Sell Price</div>
          <div className="admin-stat-value">
            {billing ? `$${billing.total_sell_price.toFixed(2)}` : '—'}
          </div>
        </div>
        <div className="admin-stat-card">
          <div className="admin-stat-label">System Health</div>
          <div className="admin-stat-value" style={{ marginTop: 4 }}>
            {systemHealthy
              ? <span className="badge badge-success">Healthy</span>
              : <span className="badge badge-warning">No keys</span>
            }
          </div>
        </div>
      </div>

      <div className="admin-two-col">
        <div className="admin-card">
          <div className="admin-card-title">
            Recent Runs
            <Link to="/admin/runs" className="btn btn-ghost btn-sm">View all →</Link>
          </div>
          {recentRuns.length === 0 ? (
            <div className="empty-state" style={{ padding: '24px 0' }}>
              <div className="empty-state-text">No runs yet.</div>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>Module</th><th>Status</th><th>When</th></tr>
                </thead>
                <tbody>
                  {recentRuns.map(run => (
                    <tr key={run.run_id} className="clickable">
                      <td>
                        <Link
                          to={`/admin/runs/${run.run_id}`}
                          style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--accent)' }}
                        >
                          {run.module_id}
                        </Link>
                      </td>
                      <td><StatusBadge status={run.status} /></td>
                      <td style={{ color: 'var(--text2)', fontSize: 12 }}>
                        {timeAgo(run.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="admin-card">
          <div className="admin-card-title">
            Specialist Readiness
            <Link to="/admin/modules" className="btn btn-ghost btn-sm">Browse →</Link>
          </div>
          {modules.length === 0 ? (
            <div style={{ color: 'var(--text2)', fontSize: 13 }}>No specialists installed.</div>
          ) : (
            <div>
              {modules.slice(0, 6).map((mod, i) => (
                <div
                  key={mod.id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '10px 0',
                    borderBottom: i < Math.min(modules.length, 6) - 1 ? '1px solid var(--border)' : 'none',
                  }}
                >
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text2)' }}>
                    {mod.id}
                  </span>
                  <span className="badge badge-success">Registered</span>
                </div>
              ))}
              {modules.length > 6 && (
                <div style={{ fontSize: 12, color: 'var(--text2)', paddingTop: 10 }}>
                  +{modules.length - 6} more
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
