import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { BillingSummary, ProviderInfo, RunListItem } from '../api/types';
import { timeAgo } from '../utils/runs';

function statusPill(status: string) {
  if (status === 'success') return <span className="status-pill sp-live"><span className="sp-dot" />Idle</span>;
  if (status === 'failed')  return <span className="status-pill sp-error"><span className="sp-dot" />Error</span>;
  return                           <span className="status-pill sp-idle"><span className="sp-dot" />Idle</span>;
}

export function Ops() {
  const navigate = useNavigate();
  const [summary, setSummary]     = useState<BillingSummary | null>(null);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [runs, setRuns]           = useState<RunListItem[]>([]);
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    Promise.all([
      api.getBillingSummary().catch(() => null),
      api.getProviders().catch(() => ({ providers: [] as ProviderInfo[] })),
      api.getRuns({ limit: 20 }).catch(() => ({ runs: [] as RunListItem[], total: 0, limit: 20, offset: 0 })),
    ]).then(([s, p, r]) => {
      setSummary(s);
      setProviders(p.providers);
      setRuns(r.runs);
      setLoading(false);
    });
  }, []);

  // One row per module: last run wins
  const moduleHealth = [...new Map(runs.map(r => [r.module_id, r])).values()];

  const recentRuns = runs.slice(0, 10);
  const errorCount = moduleHealth.filter(r => r.status === 'failed').length;

  if (loading) {
    return (
      <div className="loading-full">
        <span className="spinner" />
        Loading…
      </div>
    );
  }

  return (
    <>
      {/* Live bar */}
      <div className="live-bar">
        <div className="live-bar-dot" />
        <span className="live-bar-text">
          <strong>{summary?.total_runs ?? 0} runs</strong> · {summary?.successful_runs ?? 0} successful
        </span>
        <div className="live-bar-sep" />
        <span className="live-bar-text">
          <strong style={{ color: errorCount > 0 ? '#721c24' : '#155724' }}>{errorCount} errors</strong>
        </span>
        <div className="live-bar-sep" />
        <span className="live-bar-text">
          ${(summary?.total_provider_cost ?? 0).toFixed(2)} provider cost
        </span>
        {providers.length > 0 && (
          <>
            <div className="live-bar-sep" />
            <span className="live-bar-text">
              <strong>{providers.length}</strong> provider{providers.length !== 1 ? 's' : ''} configured
            </span>
          </>
        )}
      </div>

      {/* Module Health */}
      <div className="section-header">
        <span className="section-title">
          Module Health
          <span className="section-sub">{moduleHealth.length} module{moduleHealth.length !== 1 ? 's' : ''}</span>
        </span>
        <span className="section-action" onClick={() => navigate('/history')}>View history →</span>
      </div>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Module</th>
              <th>Status</th>
              <th>Provider·Model</th>
              <th>Latency</th>
              <th>Last Run</th>
              <th>Self-Check</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {moduleHealth.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', color: '#999', padding: '24px 12px' }}>
                  No runs yet — trigger a module to see health here.
                </td>
              </tr>
            ) : (
              moduleHealth.map(run => (
                <tr key={run.run_id}>
                  <td>
                    <div className="module-id">{run.module_id}</div>
                    <div className="module-vert">{run.vertical}</div>
                  </td>
                  <td>{statusPill(run.status)}</td>
                  <td className="td-mono">
                    {run.provider ? `${run.provider} · ${run.model}` : '—'}
                  </td>
                  <td className="td-mono">
                    {run.latency_ms ? `${run.latency_ms}ms` : '—'}
                  </td>
                  <td>{timeAgo(run.created_at)}</td>
                  <td>
                    {run.status === 'success'
                      ? <span className="check-pass">✓ pass</span>
                      : run.status === 'failed'
                        ? <span className="check-fail">✗ fail</span>
                        : <span className="td-dim">—</span>}
                  </td>
                  <td>
                    <span
                      className="trace-link"
                      onClick={() => navigate(`/history`)}
                    >
                      trace ↗
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Recent Runs */}
      <div className="section-header">
        <span className="section-title">Recent Runs</span>
        <span className="section-action" onClick={() => navigate('/history')}>View all →</span>
      </div>

      <div className="table-wrap" style={{ padding: '4px 0' }}>
        {recentRuns.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#999', padding: '24px 12px', fontSize: 13 }}>
            No runs yet.
          </div>
        ) : (
          recentRuns.map(run => (
            <div
              key={run.run_id}
              className="run-row"
              onClick={() => navigate('/history')}
            >
              <div className={`run-dot ${run.status === 'success' ? 'pass' : run.status === 'failed' ? 'fail' : 'live'}`} />
              <span className="run-module">{run.module_id}</span>
              <span className="run-meta">{run.vertical}</span>
              <span className="run-time">{timeAgo(run.created_at)}</span>
            </div>
          ))
        )}
      </div>
    </>
  );
}
