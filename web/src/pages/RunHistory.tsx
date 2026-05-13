import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { RunListItem } from '../api/types';
import { StatusBadge } from '../components/StatusBadge';

const PAGE_SIZE = 20;

export function RunHistory() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [moduleFilter, setModuleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  useEffect(() => {
    setLoading(true);
    api.getRuns({
      module_id: moduleFilter || undefined,
      status: statusFilter || undefined,
      limit: PAGE_SIZE,
      offset,
    }).then(res => {
      setRuns(res.runs);
      setTotal(res.total);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [offset, moduleFilter, statusFilter]);

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  function clearFilters() {
    setModuleFilter('');
    setStatusFilter('');
    setOffset(0);
  }

  return (
    <div>
      <div className="subpage-header">
        <button className="subpage-back" onClick={() => navigate('/settings')}>‹ Settings</button>
        <span className="subpage-title">Run History</span>
        <Link to="/settings/run" className="btn btn-dark btn-sm" style={{ marginLeft: 'auto' }}>▶ New</Link>
      </div>

      <div className="subpage-body">
        <div className="card">
          <div className="flex gap-2 mb-4" style={{ flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 160 }}>
              <label className="label">Module</label>
              <input
                className="input"
                placeholder="Filter by module ID…"
                value={moduleFilter}
                onChange={e => { setModuleFilter(e.target.value); setOffset(0); }}
              />
            </div>
            <div style={{ minWidth: 140 }}>
              <label className="label">Status</label>
              <select
                className="select"
                value={statusFilter}
                onChange={e => { setStatusFilter(e.target.value); setOffset(0); }}
              >
                <option value="">All statuses</option>
                <option value="success">success</option>
                <option value="partial">partial</option>
                <option value="failed">failed</option>
                <option value="running">running</option>
              </select>
            </div>
            {(moduleFilter || statusFilter) && (
              <button className="btn btn-ghost btn-sm" onClick={clearFilters} style={{ alignSelf: 'flex-end' }}>
                Clear
              </button>
            )}
          </div>

          <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 12 }}>
            {total} run{total !== 1 ? 's' : ''}
          </div>

          {loading ? (
            <div className="flex" style={{ justifyContent: 'center', padding: 40 }}>
              <span className="spinner" style={{ width: 24, height: 24 }} />
            </div>
          ) : runs.length === 0 ? (
            <div className="empty-state" style={{ padding: '32px 0' }}>
              <div className="empty-state-icon">≡</div>
              <div className="empty-state-title">No runs found</div>
              <div className="empty-state-text">
                {moduleFilter || statusFilter
                  ? 'Try clearing the filters.'
                  : <><Link to="/settings/run">Run a module</Link> to see results here.</>}
              </div>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Module</th>
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
                      onClick={() => navigate(`/settings/history/${run.run_id}`)}
                    >
                      <td>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--accent)' }}>
                          {run.module_id}
                        </span>
                      </td>
                      <td><StatusBadge status={run.status} /></td>
                      <td style={{ color: 'var(--text2)', fontSize: 12 }}>
                        {new Date(run.created_at).toLocaleString()}
                      </td>
                      <td>
                        <Link
                          to={`/settings/history/${run.run_id}`}
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
    </div>
  );
}
