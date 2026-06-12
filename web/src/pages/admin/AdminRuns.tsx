import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import type { RunListItem } from '../../api/types';
import { StatusBadge } from '../../components/StatusBadge';

const PAGE_SIZE = 25;

export function AdminRuns() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [moduleFilter, setModuleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [afterFilter, setAfterFilter] = useState('');
  const [beforeFilter, setBeforeFilter] = useState('');

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.getRuns({
      module_id: moduleFilter || undefined,
      status: statusFilter || undefined,
      created_after: afterFilter || undefined,
      created_before: beforeFilter || undefined,
      limit: PAGE_SIZE,
      offset,
    }).then(res => {
      setRuns(res.runs);
      setTotal(res.total);
    }).catch((e: unknown) => {
      setError((e as Error).message || 'Failed to load runs — check your connection and try again');
    }).finally(() => setLoading(false));
  }, [offset, moduleFilter, statusFilter, afterFilter, beforeFilter]);

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;
  const hasFilters = moduleFilter || statusFilter || afterFilter || beforeFilter;

  function clearFilters() {
    setModuleFilter('');
    setStatusFilter('');
    setAfterFilter('');
    setBeforeFilter('');
    // Reset offset last — all filters are already cleared so the
    // subsequent useEffect fires with a fully-reset filter state.
    setOffset(0);
  }

  function handleFilterChange(fn: (v: string) => void) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      fn(e.target.value);
      setOffset(0);
    };
  }

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">Run Logs</div>
          <div className="admin-page-subtitle">System/debug history for specialist executions · {total} total</div>
        </div>
        <Link to="/admin/billing" className="btn btn-secondary btn-sm">Billing →</Link>
      </div>

      <div className="admin-card">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, marginBottom: 16 }}>
          <div>
            <label className="label">System ID</label>
            <input
              className="input"
              placeholder="Filter by specialist/system ID…"
              value={moduleFilter}
              onChange={handleFilterChange(setModuleFilter)}
            />
          </div>
          <div>
            <label className="label">Status</label>
            <select className="select" value={statusFilter} onChange={handleFilterChange(setStatusFilter)}>
              <option value="">All statuses</option>
              <option value="success">success</option>
              <option value="partial">partial</option>
              <option value="failed">failed</option>
              <option value="running">running</option>
            </select>
          </div>
          <div>
            <label className="label">From</label>
            <input
              className="input"
              type="date"
              value={afterFilter}
              onChange={handleFilterChange(setAfterFilter)}
            />
          </div>
          <div>
            <label className="label">To</label>
            <input
              className="input"
              type="date"
              value={beforeFilter}
              onChange={handleFilterChange(setBeforeFilter)}
            />
          </div>
        </div>

        {hasFilters && (
          <button className="btn btn-ghost btn-sm" onClick={clearFilters} style={{ marginBottom: 12 }}>
            Clear filters
          </button>
        )}

        {loading ? (
          <div className="flex" style={{ justifyContent: 'center', padding: 48 }}>
            <span className="spinner" style={{ width: 28, height: 28 }} />
          </div>
        ) : error ? (
          <div className="alert alert-error">{error}</div>
        ) : runs.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">≡</div>
            <div className="empty-state-title">No runs found</div>
            <div className="empty-state-text">
              {hasFilters ? 'Try clearing the filters.' : 'Specialist executions from CMO work will appear here for debugging.'}
            </div>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>System ID</th>
                  <th>Vertical</th>
                  <th>Status</th>
                  <th>When</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {runs.map(run => (
                  <tr
                    key={run.run_id}
                    className="clickable"
                    onClick={() => navigate(`/admin/runs/${run.run_id}`)}
                  >
                    <td>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--accent)' }}>
                        {run.module_id}
                      </span>
                    </td>
                    <td style={{ color: 'var(--text2)', fontSize: 12 }}>{run.vertical}</td>
                    <td><StatusBadge status={run.status} /></td>
                    <td style={{ color: 'var(--text2)', fontSize: 12 }}>
                      {new Date(run.created_at).toLocaleString()}
                    </td>
                    <td>
                      <Link
                        to={`/admin/runs/${run.run_id}`}
                        className="btn btn-ghost btn-sm"
                        onClick={(e: React.MouseEvent) => e.stopPropagation()}
                      >
                        View →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="pagination">
            <span className="pagination-info">Page {currentPage} of {totalPages}</span>
            <button
              className="btn btn-secondary btn-sm"
              disabled={offset === 0}
              onClick={() => setOffset(o => Math.max(0, o - PAGE_SIZE))}
            >
              ←
            </button>
            <button
              className="btn btn-secondary btn-sm"
              disabled={currentPage >= totalPages}
              onClick={() => setOffset(o => o + PAGE_SIZE)}
            >
              →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
