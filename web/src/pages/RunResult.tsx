import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import type { RunResponse } from '../api/types';

export function RunResult() {
  const { runId }   = useParams<{ runId: string }>();
  const navigate    = useNavigate();
  const [run, setRun]             = useState<RunResponse | null>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [copied, setCopied]       = useState(false);
  const [traceOpen, setTraceOpen] = useState(false);

  useEffect(() => {
    if (!runId) return;
    api.getRun(runId)
      .then(setRun)
      .catch((e: unknown) => setError((e as Error).message ?? 'Run not found'))
      .finally(() => setLoading(false));
  }, [runId]);

  if (loading) {
    return <div className="loading-full"><span className="spinner" /></div>;
  }

  if (error || !run) {
    return (
      <div style={{ padding: 20 }}>
        <button className="btn btn-sm" style={{ marginBottom: 12 }} onClick={() => navigate(-1)}>‹ History</button>
        <div style={{ padding: '10px 12px', background: '#f8d7da', border: '1px solid #f5c6cb', borderRadius: 6, fontSize: 13, color: '#721c24' }}>
          {error ?? 'Run not found'}
        </div>
      </div>
    );
  }

  function handleCopy() {
    if (run?.result?.content) {
      navigator.clipboard.writeText(run.result.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  const selfCheck = run.result?.self_check;

  return (
    <div style={{ maxWidth: 720 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <button className="btn btn-sm" onClick={() => navigate(-1)}>‹ History</button>
        <span style={{ fontWeight: 700 }}>Run Result</span>
        {run.status === 'success'
          ? <span className="status-pill sp-live"><span className="sp-dot" />Passed</span>
          : run.status === 'failed'
            ? <span className="status-pill sp-error"><span className="sp-dot" />Failed</span>
            : <span className="status-pill sp-idle"><span className="sp-dot" />Mock</span>}
      </div>

      <div style={{ fontSize: 11, color: '#999', fontFamily: 'monospace', marginBottom: 14 }}>
        {run.module_id} · {new Date(run.created_at).toLocaleString()}
      </div>

      {run.result ? (
        <div className="card" style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontWeight: 700 }}>Output</span>
              {selfCheck === 'pass' && <span className="check-pass">✓ pass</span>}
              {selfCheck === 'fail' && <span className="check-fail">✗ fail</span>}
              {run.result.platform && <span style={{ fontSize: 11, color: '#999' }}>{run.result.platform}</span>}
            </div>
            <button className="btn btn-sm" onClick={handleCopy}>{copied ? '✓ Copied' : 'Copy'}</button>
          </div>
          <div style={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.6, color: '#333' }}>
            {run.result.content}
          </div>
        </div>
      ) : (
        <div style={{ padding: '10px 12px', background: '#f8d7da', border: '1px solid #f5c6cb', borderRadius: 6, fontSize: 13, color: '#721c24', marginBottom: 14 }}>
          No output — run may have failed.
        </div>
      )}

      {run.execution && (
        <div className="card" style={{ marginBottom: 14 }}>
          <div style={{ fontWeight: 700, marginBottom: 10 }}>Execution</div>
          {([
            ['Mode',    run.execution.mode ?? '—'],
            ['Provider', run.execution.provider],
            ['Model',    run.execution.model],
            ['Latency',  `${run.execution.latency_ms.toLocaleString()} ms`],
            run.execution.tokens_used  != null ? ['Tokens',        run.execution.tokens_used.toLocaleString()]      : null,
            run.execution.provider_cost != null ? ['Provider cost', `$${run.execution.provider_cost.toFixed(6)}`]  : null,
            run.execution.sell_price    != null ? ['Sell price',    `$${run.execution.sell_price.toFixed(6)}`]      : null,
          ] as ([string, string] | null)[]).filter((x): x is [string, string] => x !== null).map(([label, value]) => (
            <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: '1px solid #f0f0f0', fontSize: 13 }}>
              <span style={{ color: '#666' }}>{label}</span>
              <span style={{ color: '#111', fontWeight: 500 }}>{value}</span>
            </div>
          ))}
        </div>
      )}

      {run.trace && (
        <div className="card" style={{ marginBottom: 14 }}>
          <div
            style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
            onClick={() => setTraceOpen(o => !o)}
          >
            <span style={{ fontWeight: 700 }}>Routing Trace</span>
            <span style={{ fontSize: 12, color: '#999' }}>{traceOpen ? '▲' : '▼'}</span>
          </div>
          {traceOpen && (
            <div style={{ marginTop: 12 }}>
              {([
                ['Capability', run.trace.capability],
                ['Policy',     run.trace.policy],
                ['Considered', String(run.trace.candidates_considered)],
                ['Filtered',   String(run.trace.candidates_filtered)],
                ['Winner',     run.trace.winner ?? 'none'],
              ] as [string, string][]).map(([label, value]) => (
                <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: '1px solid #f0f0f0', fontSize: 13 }}>
                  <span style={{ color: '#666' }}>{label}</span>
                  <span style={{ color: '#111' }}>{value}</span>
                </div>
              ))}
              <div style={{ fontSize: 12, color: '#666', paddingTop: 8 }}>{run.trace.routing_reason}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
