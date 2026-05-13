import { useEffect, useState } from 'react';
import { BlockRenderer } from '../components/blocks/BlockRenderer';
import { buildBriefingStream } from '../utils/streamBuilder';
import { api } from '../api/client';
import type { BillingSummary, RunListItem } from '../api/types';

export function ReportsView() {
  const [summary, setSummary] = useState<BillingSummary | null>(null);
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getBillingSummary().catch(() => null),
      api.getRuns({ limit: 50 }).catch(() => ({ runs: [] as RunListItem[], total: 0, limit: 50, offset: 0 })),
    ]).then(([s, r]) => {
      setSummary(s);
      setRuns(r.runs);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="loading-full">
        <span className="spinner" />
      </div>
    );
  }

  const stream = buildBriefingStream(summary, runs);

  return (
    <div className="reports-view" style={{ padding: '24px', maxWidth: '1000px', margin: '0 auto' }}>
      <div style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 800, color: '#111', marginBottom: '8px' }}>Business Performance</h1>
        <p style={{ color: '#666', fontSize: '14px' }}>Aggregated insights across all active campaigns and channels.</p>
      </div>

      {stream.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {stream.map(block => (
            <div key={block.id}>
              <BlockRenderer block={block} />
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state" style={{ textAlign: 'center', padding: '48px 0' }}>
          <div className="empty-state-icon" style={{ fontSize: '48px', marginBottom: '16px' }}>📊</div>
          <div className="empty-state-title" style={{ fontSize: '18px', fontWeight: 700, color: '#111' }}>No data available</div>
          <div className="empty-state-text" style={{ color: '#666', marginTop: '8px' }}>
            Run some modules to generate performance reports.
          </div>
        </div>
      )}
    </div>
  );
}
