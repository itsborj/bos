import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { BillingSummary, RunListItem } from '../../api/types';

function artifactLabel(run: RunListItem): string {
  const id = run.module_id.toLowerCase();
  if (id.includes('plan') || id.includes('strategy')) return 'Plan artifact';
  if (id.includes('analytics') || id.includes('tracking') || id.includes('seo') || id.includes('receive')) return 'Optimization signal';
  if (id.includes('email') || id.includes('copy') || id.includes('draft')) return 'Execution artifact';
  return 'Specialist output';
}

export function AdminReports() {
  const [summary, setSummary] = useState<BillingSummary | null>(null);
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.getBillingSummary().catch(() => null),
      api.getRuns({ limit: 12 }).catch(() => ({ runs: [] as RunListItem[], total: 0, limit: 12, offset: 0 })),
    ]).then(([s, r]) => {
      setSummary(s);
      setRuns(r.runs);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div className="admin-page"><div className="loading-full"><span className="spinner" /></div></div>;
  }

  const approved = runs.filter(run => run.approval_status === 'approved').length;
  const pending = runs.filter(run => run.approval_status === 'pending').length;

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">Outcomes</div>
          <div className="admin-page-subtitle">Monthly reviews, campaign reports, approved learnings, and optimization history will live here.</div>
        </div>
      </div>

      <div className="admin-stat-grid">
        <div className="admin-stat-card"><div className="admin-stat-label">Specialist Outputs</div><div className="admin-stat-value">{summary?.total_runs ?? 0}</div></div>
        <div className="admin-stat-card"><div className="admin-stat-label">Approved Learnings</div><div className="admin-stat-value">{approved}</div></div>
        <div className="admin-stat-card"><div className="admin-stat-label">Needs Review</div><div className="admin-stat-value">{pending}</div></div>
        <div className="admin-stat-card"><div className="admin-stat-label">Optimization Readiness</div><div className="admin-stat-value"><span className="badge badge-warning">Pending analytics</span></div></div>
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Recent Outcome Inputs</div>
        {runs.length === 0 ? (
          <div className="empty-state" style={{ padding: '48px 0' }}>
            <div className="empty-state-icon">📊</div>
            <div className="empty-state-title">No outcomes yet</div>
            <div className="empty-state-text">Use the CMO to plan, execute, and optimize. Approved artifacts and monthly reviews will become durable outcomes here.</div>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Type</th><th>Status</th><th>When</th><th>System ID</th></tr></thead>
              <tbody>
                {runs.map(run => (
                  <tr key={run.run_id}>
                    <td style={{ fontWeight: 700 }}>{artifactLabel(run)}</td>
                    <td><span className="badge badge-muted">{run.approval_status || run.status}</span></td>
                    <td style={{ color: 'var(--text2)', fontSize: 12 }}>{new Date(run.created_at).toLocaleString()}</td>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text2)' }}>{run.module_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
