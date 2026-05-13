import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { RunListItem } from '../api/types';
import { timeAgo } from '../utils/runs';

type Filter = 'all' | 'passed' | 'failed';

export function History() {
  const navigate = useNavigate();
  const [runs, setRuns]       = useState<RunListItem[]>([]);
  const [total, setTotal]     = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter]   = useState<Filter>('all');
  const [offset, setOffset]   = useState(0);
  const LIMIT = 20;

  useEffect(() => {
    setLoading(true);
    const status = filter === 'passed' ? 'success' : filter === 'failed' ? 'failed' : undefined;
    api.getRuns({ status, limit: LIMIT, offset }).then(r => {
      setRuns(r.runs);
      setTotal(r.total);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [filter, offset]);

  function changeFilter(f: Filter) {
    setFilter(f);
    setOffset(0);
  }

  function statusPill(status: string) {
    if (status === 'success') return <span className="status-pill sp-live"><span className="sp-dot" />Passed</span>;
    if (status === 'failed')  return <span className="status-pill sp-error"><span className="sp-dot" />Failed</span>;
    return                           <span className="status-pill sp-idle"><span className="sp-dot" />Mock</span>;
  }

  function selfCheck(status: string) {
    if (status === 'success') return <span className="check-pass">✓ pass</span>;
    if (status === 'failed')  return <span className="check-fail">✗ fail</span>;
    return <span className="td-dim">—</span>;
  }

  const passed = runs.filter(r => r.status === 'success').length;
  const failed = runs.filter(r => r.status === 'failed').length;
  const cost = runs.reduce((sum, r) => sum + (Number(r.cost ?? 0) || 0), 0);

  return (
    <div className="ux-page">
      <div className="ux-hero">
        <div>
          <div className="ux-eyebrow">Execution ledger</div>
          <h1 className="ux-title">Run history</h1>
          <p className="ux-subtitle">Trace every Transform execution, provider route, cost, and self-check result.</p>
        </div>
        <div className="ux-stat-row compact">
          <div className="ux-stat"><span>{total}</span><small>total</small></div>
          <div className="ux-stat"><span>{passed}</span><small>passed here</small></div>
          <div className="ux-stat"><span>{failed}</span><small>failed here</small></div>
          <div className="ux-stat"><span>${cost.toFixed(2)}</span><small>visible cost</small></div>
        </div>
      </div>

      <div className="filter-bar">
        <button className={`filter-chip${filter === 'all'    ? ' active' : ''}`} onClick={() => changeFilter('all')}>All runs</button>
        <button className={`filter-chip${filter === 'passed' ? ' active' : ''}`} onClick={() => changeFilter('passed')}>Passed</button>
        <button className={`filter-chip${filter === 'failed' ? ' active' : ''}`} onClick={() => changeFilter('failed')}>Failed</button>
      </div>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Module</th>
              <th>Vertical</th>
              <th>Status</th>
              <th>Provider·Model</th>
              <th>Tokens</th>
              <th>Cost</th>
              <th>Self-Check</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={9} style={{ textAlign: 'center', padding: '24px 12px' }}>
                  <span className="spinner" style={{ display: 'inline-block' }} />
                </td>
              </tr>
            ) : runs.length === 0 ? (
              <tr>
                <td colSpan={9} style={{ textAlign: 'center', color: '#999', padding: '24px 12px' }}>
                  No runs found.
                </td>
              </tr>
            ) : (
              runs.map(run => (
                <tr key={run.run_id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/history/${run.run_id}`)}>
                  <td className="td-dim" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>{timeAgo(run.created_at)}</td>
                  <td className="td-primary td-mono">{run.module_id}</td>
                  <td>{run.vertical}</td>
                  <td>{statusPill(run.status)}</td>
                  <td className="td-mono">
                    {run.provider ? `${run.provider} · ${run.model}` : '—'}
                  </td>
                  <td className="td-mono">{run.tokens?.toLocaleString() ?? '—'}</td>
                  <td className="td-mono">${run.cost?.toFixed(4) ?? '—'}</td>
                  <td>{selfCheck(run.status)}</td>
                  <td><span className="trace-link">trace ↗</span></td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {total > LIMIT && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12, color: '#999' }}>
          <span>Showing {offset + 1}–{Math.min(offset + LIMIT, total)} of {total} runs</span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-sm" onClick={() => setOffset(o => Math.max(0, o - LIMIT))} disabled={offset === 0}>← Prev</button>
            <button className="btn btn-sm" onClick={() => setOffset(o => o + LIMIT)} disabled={offset + LIMIT >= total}>Next →</button>
          </div>
        </div>
      )}
    </div>
  );
}
