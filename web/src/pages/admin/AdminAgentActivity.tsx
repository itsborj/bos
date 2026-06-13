import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import type { AgentStateResponse, RunListItem } from '../../api/types';
import { StatusBadge } from '../../components/StatusBadge';

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.max(0, Math.floor(diff / 60000));
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function AdminAgentActivity() {
  const [state, setState] = useState<AgentStateResponse | null>(null);
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyRun, setBusyRun] = useState<string | null>(null);

  function load() {
    setLoading(true);
    Promise.all([
      api.getAgentState().catch(() => null),
      api.getRuns({ approval_status: 'pending', limit: 50 }).catch(() => ({ runs: [], total: 0, limit: 50, offset: 0 })),
    ]).then(([agentState, pending]) => {
      setState(agentState);
      const unique = new Map<string, RunListItem>();
      for (const run of pending.runs || []) unique.set(run.run_id, run);
      setRuns([...unique.values()]);
    }).finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  const brandNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const brand of state?.brands || []) map.set(brand.brand_id, brand.name);
    return map;
  }, [state]);

  async function review(run: RunListItem, action: 'approve' | 'reject') {
    setBusyRun(run.run_id);
    try {
      if (action === 'approve') await api.approveRun(run.run_id);
      else await api.rejectRun(run.run_id, 'Rejected from Agent Activity panel.');
      setRuns(prev => prev.filter(item => item.run_id !== run.run_id));
      setState(prev => prev ? { ...prev, total_pending: Math.max(0, prev.total_pending - 1) } : prev);
    } finally {
      setBusyRun(null);
    }
  }

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">Approvals</div>
          <div className="admin-page-subtitle">Human review queue for generated client work before external action.</div>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={load}>Refresh</button>
      </div>

      {loading ? (
        <div className="loading-full"><span className="spinner" /></div>
      ) : (
        <>
          <div className="admin-stat-grid">
            <div className="admin-stat-card">
              <div className="admin-stat-label">Workspace</div>
              <div className="admin-stat-value" style={{ fontSize: 22 }}>{state?.workspace_name || '—'}</div>
            </div>
            <div className="admin-stat-card">
              <div className="admin-stat-label">Pending Reviews</div>
              <div className="admin-stat-value">{state?.total_pending ?? runs.length}</div>
            </div>
            <div className="admin-stat-card">
              <div className="admin-stat-label">Brands Watched</div>
              <div className="admin-stat-value">{state?.brands.length ?? 0}</div>
            </div>
            <div className="admin-stat-card">
              <div className="admin-stat-label">PM Sync</div>
              <div className="admin-stat-value" style={{ fontSize: 18 }}>
                {(state?.brands || []).some(b => b.pm_sync_enabled) ? 'Enabled' : 'Not enabled'}
              </div>
            </div>
          </div>

          <div className="admin-two-col">
            <div className="admin-card">
              <div className="admin-card-title">Brand Queue</div>
              {(state?.brands || []).length === 0 ? (
                <div className="empty-state" style={{ padding: '24px 0' }}>No brands found.</div>
              ) : (
                <div>
                  {(state?.brands || []).map(brand => (
                    <div key={brand.brand_id} className="settings-row" style={{ padding: '12px 0' }}>
                      <div className="settings-row-info">
                        <div className="settings-row-name">{brand.name}</div>
                        <div className="settings-row-desc">{brand.pm_sync_enabled ? 'PM sync enabled' : 'PM sync not configured'}</div>
                      </div>
                      <span className={brand.pending_approvals ? 'badge badge-warning' : 'badge badge-success'}>
                        {brand.pending_approvals} pending
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="admin-card">
              <div className="admin-card-title">Approval Queue</div>
              {runs.length === 0 ? (
                <div className="empty-state" style={{ padding: '28px 0' }}>
                  <div className="empty-state-title">No pending agent work</div>
                  <div className="empty-state-text">Agent-created artifacts will appear here for approval before external action.</div>
                </div>
              ) : (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr><th>Specialist</th><th>Brand</th><th>Status</th><th>When</th><th></th></tr>
                    </thead>
                    <tbody>
                      {runs.map(run => (
                        <tr key={run.run_id}>
                          <td>
                            <Link to={`/admin/runs/${run.run_id}`} style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--accent)' }}>
                              {run.module_id}
                            </Link>
                          </td>
                          <td style={{ color: 'var(--text2)', fontSize: 12 }}>{run.brand_id ? (brandNameById.get(run.brand_id) || 'Brand') : '—'}</td>
                          <td><StatusBadge status={run.status} /></td>
                          <td style={{ color: 'var(--text2)', fontSize: 12 }}>{timeAgo(run.created_at)}</td>
                          <td style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                            <button className="btn btn-ghost btn-sm" disabled={busyRun === run.run_id} onClick={() => review(run, 'reject')}>Reject</button>
                            <button className="btn btn-dark btn-sm" disabled={busyRun === run.run_id} onClick={() => review(run, 'approve')}>Approve</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
