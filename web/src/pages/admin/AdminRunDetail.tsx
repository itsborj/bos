import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { RunResponse } from '../../api/types';
import { StatusBadge } from '../../components/StatusBadge';

function SelfCheckBadge({ verdict }: { verdict: string }) {
  if (verdict === 'pass') return <span className="badge badge-success">✓ pass</span>;
  if (verdict === 'fail') return <span className="badge badge-error">✗ fail</span>;
  return <span className="badge badge-warning">{verdict}</span>;
}

export function AdminRunDetail() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [run, setRun] = useState<RunResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [traceOpen, setTraceOpen] = useState(false);

  useEffect(() => {
    if (!runId) return;
    api.getRun(runId)
      .then(setRun)
      .catch((e: unknown) => setError((e as Error).message ?? 'Run not found'))
      .finally(() => setLoading(false));
  }, [runId]);

  if (loading) {
    return (
      <div className="admin-page">
        <div className="loading-full"><span className="spinner" /></div>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="admin-page">
        <div className="admin-page-header">
          <div>
            <button className="btn btn-secondary btn-sm" onClick={() => navigate('/admin/runs')}>← Runs</button>
          </div>
        </div>
        <div className="alert alert-error">{error ?? 'Run not found'}</div>
      </div>
    );
  }

  function handleCopy() {
    if (!run?.result?.content) return;
    navigator.clipboard.writeText(run.result.content)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      })
      .catch(() => {
        // Clipboard API unavailable (non-HTTPS or permission denied) — fail silently.
      });
  }

  const modeBadge =
    run.execution?.mode === 'byok'     ? <span className="badge badge-info">BYOK</span> :
    run.execution?.mode === 'platform' ? <span className="badge badge-success">Platform</span> :
    <span className="badge badge-muted">Mock</span>;

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <button className="btn btn-secondary btn-sm" onClick={() => navigate('/admin/runs')} style={{ marginBottom: 10 }}>
            ← Runs
          </button>
          <div className="admin-page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            Run Log Detail
            <StatusBadge status={run.status} />
          </div>
          <div className="admin-page-subtitle" style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>
            {run.module_id} · {new Date(run.created_at).toLocaleString()}
          </div>
        </div>
      </div>

      <div className="admin-two-col">
        <div>
          {run.result ? (
            <div className="admin-card">
              <div className="admin-card-title">
                <div className="flex items-center gap-2">
                  Output
                  {run.result.self_check && <SelfCheckBadge verdict={run.result.self_check} />}
                  {run.result.platform && <span className="badge badge-muted">{run.result.platform}</span>}
                </div>
                <button className="btn btn-ghost btn-sm" onClick={handleCopy}>
                  {copied ? '✓ Copied' : 'Copy'}
                </button>
              </div>
              <div className="run-output">{run.result.content}</div>
            </div>
          ) : (
            <div className="alert alert-error">No output — run may have failed.</div>
          )}
        </div>

        <div>
          {run.execution && (
            <div className="admin-card">
              <div className="admin-card-title">Execution</div>
              <div className="detail-row">
                <span className="detail-label">Mode</span>
                <span>{modeBadge}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Provider</span>
                <span className="detail-value">{run.execution.provider}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Model</span>
                <span className="detail-value">{run.execution.model}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Latency</span>
                <span className="detail-value">{run.execution.latency_ms.toLocaleString()} ms</span>
              </div>
              {run.execution.tokens_used != null && (
                <div className="detail-row">
                  <span className="detail-label">Tokens</span>
                  <span className="detail-value">{run.execution.tokens_used.toLocaleString()}</span>
                </div>
              )}
              {run.execution.provider_cost != null && (
                <div className="detail-row">
                  <span className="detail-label">Provider cost</span>
                  <span className="detail-value">${run.execution.provider_cost.toFixed(6)}</span>
                </div>
              )}
              {run.execution.sell_price != null && (
                <div className="detail-row">
                  <span className="detail-label">Sell price</span>
                  <span className="detail-value">${run.execution.sell_price.toFixed(6)}</span>
                </div>
              )}
            </div>
          )}

          {run.trace && (
            <div className="admin-card">
              <div
                className="admin-card-title collapsible-header"
                onClick={() => setTraceOpen(o => !o)}
                style={{ cursor: 'pointer' }}
              >
                Routing Trace
                <span style={{ color: 'var(--text2)', fontSize: 12 }}>{traceOpen ? '▲' : '▼'}</span>
              </div>
              {traceOpen && (
                <div>
                  <div className="detail-row">
                    <span className="detail-label">Capability</span>
                    <span className="detail-value">{run.trace.capability}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Policy</span>
                    <span className="detail-value">{run.trace.policy}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Considered</span>
                    <span className="detail-value">{run.trace.candidates_considered}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Filtered</span>
                    <span className="detail-value">{run.trace.candidates_filtered}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Winner</span>
                    <span className="detail-value">{run.trace.winner ?? 'none'}</span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text2)', paddingTop: 8 }}>
                    {run.trace.routing_reason}
                  </div>
                </div>
              )}
            </div>
          )}


        </div>
      </div>
    </div>
  );
}
