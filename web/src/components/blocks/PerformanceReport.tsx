import React from 'react';
import type { BriefingBlock } from '../../types/stream';
import { useSurface } from '../../surfaces/SurfaceContext';

interface PerformanceReportProps {
  block: BriefingBlock;
}

type Metric = { label: string; value: string };
type Row = Record<string, string | number | null | undefined>;

function asMetrics(content: any): Metric[] {
  return Array.isArray(content?.metrics) ? content.metrics : [];
}

function asRows(content: any): Row[] {
  return Array.isArray(content?.rows) ? content.rows : [];
}

function columnLabel(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export const PerformanceReport: React.FC<PerformanceReportProps> = ({ block }) => {
  const { type } = useSurface();
  const content = block.content || {};
  const metrics = asMetrics(content);
  const rows = asRows(content);
  const visibleMetrics = type === 'mobile-card' ? metrics.slice(0, 3) : type === 'full-screen' ? metrics : metrics.slice(0, 6);
  const rowKeys = rows[0]
    ? ['campaign', 'status', 'spend', 'clicks', 'conversions', 'cpa', 'recommendation'].filter(k => k in rows[0])
    : [];
  const visibleRowKeys = type === 'chat-inline' || type === 'panel'
    ? rowKeys.filter(k => !['status'].includes(k))
    : rowKeys;

  return (
    <div className="performance-report-card">
      <div className="performance-report-header">
        <div>
          <div className="performance-report-kicker">Google Ads</div>
          <div className="performance-report-title">{content.title || 'Performance Report'}</div>
        </div>
        {content.source?.mode && <div className="performance-report-source">{content.source.mode}</div>}
      </div>

      {content.summary && <div className="performance-report-summary">{content.summary}</div>}
      
      <div className={`performance-metric-grid ${type === 'full-screen' ? 'full' : type === 'mobile-card' ? 'mobile' : ''}`}>
        {visibleMetrics.map((metric, idx) => (
          <div className="performance-metric" key={`${metric.label}-${idx}`}>
            <div className="performance-metric-label">{metric.label}</div>
            <div className="performance-metric-value">{metric.value}</div>
          </div>
        ))}
      </div>

      {type === 'full-screen' && (
        <div className="performance-chart-shell">
          <div className="performance-chart-bars">
            {rows.map((row, idx) => {
              const spend = Number(String(row.spend || '0').replace(/[^0-9.]/g, '')) || 0;
              const maxSpend = Math.max(...rows.map(r => Number(String(r.spend || '0').replace(/[^0-9.]/g, '')) || 0), 1);
              return <div key={idx} className="performance-chart-bar" style={{ height: `${Math.max(14, (spend / maxSpend) * 100)}%` }} title={`${row.campaign}: ${row.spend}`} />;
            })}
          </div>
          <div className="performance-chart-caption">Spend distribution by campaign</div>
        </div>
      )}

      {rows.length > 0 && (
        <div className="performance-table-wrap">
          <table className="performance-table">
            <thead>
              <tr>
                {visibleRowKeys.map(key => <th key={key} className={key === 'campaign' || key === 'recommendation' ? '' : 'numeric'}>{columnLabel(key)}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => (
                <tr key={idx}>
                  {visibleRowKeys.map(key => <td key={key} className={key === 'campaign' || key === 'recommendation' ? '' : 'numeric'}>{row[key]}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {content.source && (
        <div className="performance-report-footnote">
          Source: {content.source.customer_name || 'Connector'} · {content.source.connector || 'reporting connector'}
        </div>
      )}
    </div>
  );
};
