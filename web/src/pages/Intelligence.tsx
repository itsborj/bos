import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { BillingSummary, RunListItem, WorkspaceResponse } from '../api/types';

export function Intelligence() {
  const [summary, setSummary]       = useState<BillingSummary | null>(null);
  const [runs, setRuns]             = useState<RunListItem[]>([]);
  const [workspace, setWorkspace]   = useState<WorkspaceResponse | null>(null);
  const [loading, setLoading]       = useState(true);

  useEffect(() => {
    Promise.all([
      api.getBillingSummary().catch(() => null),
      api.getRuns({ limit: 100 }).catch(() => ({ runs: [] as RunListItem[], total: 0, limit: 100, offset: 0 })),
      api.getWorkspace().catch(() => null),
    ]).then(([s, r, ws]) => {
      setSummary(s);
      setRuns(r.runs);
      setWorkspace(ws);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="loading-full">
        <span className="spinner" />
        Loading…
      </div>
    );
  }

  const totalRuns    = summary?.total_runs ?? 0;
  const totalCost    = summary?.total_provider_cost ?? 0;
  const avgCost      = totalRuns > 0 ? totalCost / totalRuns : 0;
  const successRate  = totalRuns > 0
    ? Math.round(((summary?.successful_runs ?? 0) / totalRuns) * 100)
    : 0;

  // Synthesize per-module data from runs
  const byModule = runs.reduce<Record<string, { count: number; pass: number }>>((acc, r) => {
    if (!acc[r.module_id]) acc[r.module_id] = { count: 0, pass: 0 };
    acc[r.module_id].count++;
    if (r.status === 'success') acc[r.module_id].pass++;
    return acc;
  }, {});

  const moduleRows = Object.entries(byModule)
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 8);

  return (
    <>
      {/* Bento tiles */}
      <div className="bento-grid">
        <div className="bento-tile">
          <div className="bento-label">Total Runs</div>
          <div className="bento-value">{totalRuns}</div>
          <div className="bento-delta">all time</div>
        </div>
        <div className="bento-tile">
          <div className="bento-label">Success Rate</div>
          <div className="bento-value">{successRate}%</div>
          <div className="bento-delta">
            <span className={successRate >= 80 ? 'pos' : ''}>{summary?.successful_runs ?? 0} passed</span>
          </div>
        </div>
        <div className="bento-tile">
          <div className="bento-label">Provider Cost</div>
          <div className="bento-value">${totalCost.toFixed(2)}</div>
          <div className="bento-delta">all time</div>
        </div>
        <div className="bento-tile">
          <div className="bento-label">Avg Cost / Run</div>
          <div className="bento-value sm">${avgCost.toFixed(3)}</div>
          <div className="bento-delta">{totalRuns} runs</div>
        </div>
      </div>

      {/* Module performance */}
      <div className="section-header">
        <span className="section-title">Module Performance</span>
      </div>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Module</th>
              <th>Runs</th>
              <th>Passed</th>
              <th>Pass Rate</th>
            </tr>
          </thead>
          <tbody>
            {moduleRows.length === 0 ? (
              <tr>
                <td colSpan={4} style={{ textAlign: 'center', color: '#999', padding: '24px 12px' }}>
                  No run data yet.
                </td>
              </tr>
            ) : (
              moduleRows.map(([moduleId, stats]) => (
                <tr key={moduleId}>
                  <td className="td-primary td-mono">{moduleId}</td>
                  <td>{stats.count}</td>
                  <td>{stats.pass}</td>
                  <td className={stats.count > 0 && stats.pass / stats.count >= 0.8 ? 'td-good' : ''}>
                    {stats.count > 0 ? Math.round((stats.pass / stats.count) * 100) : 0}%
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Products — from workspace */}
      {workspace && workspace.products.length > 0 && (
        <>
          <div className="section-header">
            <span className="section-title">
              Products
              <span className="section-sub">{workspace.products.length} configured</span>
            </span>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Tagline</th>
                  <th>Benefits</th>
                </tr>
              </thead>
              <tbody>
                {workspace.products.map(p => (
                  <tr key={p.id}>
                    <td className="td-primary">{p.name}</td>
                    <td>{p.tagline ?? <span className="td-dim">—</span>}</td>
                    <td>{p.benefits.join(' · ') || <span className="td-dim">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Audiences */}
      {workspace && workspace.audiences.length > 0 && (
        <>
          <div className="section-header">
            <span className="section-title">
              Audiences
              <span className="section-sub">{workspace.audiences.length} segments</span>
            </span>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Segment</th>
                  <th>Demographics</th>
                  <th>Pain Points</th>
                </tr>
              </thead>
              <tbody>
                {workspace.audiences.map(a => (
                  <tr key={a.id}>
                    <td className="td-primary">{a.name}</td>
                    <td>{a.demographics ?? <span className="td-dim">—</span>}</td>
                    <td>{a.pain_points.join(' · ') || <span className="td-dim">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {(!workspace || (workspace.products.length === 0 && workspace.audiences.length === 0)) && (
        <div style={{ textAlign: 'center', color: '#999', padding: '24px 0', fontSize: 13 }}>
          Configure products and audiences in Workspace to see them here.
        </div>
      )}
    </>
  );
}
