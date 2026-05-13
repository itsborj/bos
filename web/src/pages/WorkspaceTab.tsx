import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { RunListItem, RunResponse } from '../api/types';
import { moduleLabel, timeAgo, wsBadgeProps } from '../utils/runs';

interface AssetViewerProps {
  run: RunResponse;
  total: number;
  idx: number;
  onClose: () => void;
  onPrev: () => void;
  onNext: () => void;
}

function AssetViewer({ run, total, idx, onClose, onPrev, onNext }: AssetViewerProps) {
  const [copied, setCopied] = useState(false);
  const m = moduleLabel(run.module_id);
  const content = run.result?.content ?? '';
  const checkPass = run.result?.self_check === 'pass';

  function copy() {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="asset-viewer">
      <div className="asset-header">
        <button className="asset-back" onClick={onClose}>
          ‹ Workspace
        </button>
        <div className="asset-title-col">
          <div className="asset-title">{m.short}</div>
          <div className="asset-counter">{idx + 1} of {total}</div>
        </div>
      </div>

      <div className="asset-body">
        <div className="asset-card">
          <div className="asset-platform-bar">
            <span className="asset-platform-dot" style={{ background: m.color }} />
            <span className="asset-platform-name">{m.platform}</span>
            <span className="asset-platform-type">Ad Copy</span>
          </div>

          <div className="asset-content">
            {content ? (
              <div className="asset-content-text">{content}</div>
            ) : (
              <div style={{ color: 'var(--text3)', fontStyle: 'italic', fontSize: 14 }}>
                No content — run failed or produced empty output.
              </div>
            )}

            <div className="asset-check-row">
              <span className={`asset-check-badge ${checkPass ? 'check-pass' : 'check-fail'}`}>
                {checkPass ? '✓ pass' : '✗ fail'}
              </span>
              <span style={{ fontSize: 12, color: 'var(--text2)' }}>self-check</span>
            </div>

            <div className="asset-meta-row">
              {run.execution?.provider && (
                <span className="asset-meta-item">
                  <strong>{run.execution.provider}</strong>
                </span>
              )}
              {run.execution?.model && (
                <span className="asset-meta-item">
                  <strong>{run.execution.model}</strong>
                </span>
              )}
              {run.execution?.mode && (
                <span className="asset-meta-item">{run.execution.mode}</span>
              )}
              {run.execution?.latency_ms != null && (
                <span className="asset-meta-item">{run.execution.latency_ms}ms</span>
              )}
              {run.execution?.provider_cost != null && (
                <span className="asset-meta-item">${run.execution.provider_cost.toFixed(5)}</span>
              )}
            </div>

            <button
              className={`asset-copy-btn ${copied ? 'copied' : ''}`}
              onClick={copy}
              disabled={!content}
            >
              {copied ? '✓ Copied!' : 'Copy to clipboard'}
            </button>
          </div>
        </div>

        {total > 1 && (
          <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
            <button
              className="btn btn-secondary btn-sm"
              style={{ flex: 1 }}
              onClick={onPrev}
              disabled={idx === 0}
            >
              ← Previous
            </button>
            <button
              className="btn btn-secondary btn-sm"
              style={{ flex: 1 }}
              onClick={onNext}
              disabled={idx === total - 1}
            >
              Next →
            </button>
          </div>
        )}

        <div className="asset-nav-dots" style={{ marginTop: total > 1 ? 8 : 14 }}>
          {Array.from({ length: total }).map((_, i) => (
            <div key={i} className={`asset-dot ${i === idx ? 'active' : ''}`} />
          ))}
        </div>
      </div>
    </div>
  );
}

export function WorkspaceTab() {
  const navigate = useNavigate();
  const [runs, setRuns]                   = useState<RunListItem[]>([]);
  const [loading, setLoading]             = useState(true);
  const [activeTab, setActiveTab]         = useState<'active' | 'past'>('active');
  const [assetListItems, setAssetListItems] = useState<RunListItem[]>([]);
  const [assetFull, setAssetFull]         = useState<RunResponse | null>(null);
  const [assetIdx, setAssetIdx]           = useState(0);

  useEffect(() => {
    api.getRuns({ limit: 50 }).then(r => {
      setRuns(r.runs);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  async function fetchAndShow(items: RunListItem[], idx: number) {
    setAssetIdx(idx);
    const full = await api.getRun(items[idx].run_id).catch(() => null);
    if (full) setAssetFull(full);
  }

  async function openAsset(run: RunListItem, list: RunListItem[]) {
    const idx = list.findIndex(r => r.run_id === run.run_id);
    setAssetListItems(list);
    setAssetFull(null);
    await fetchAndShow(list, idx >= 0 ? idx : 0);
  }

  function closeAsset() {
    setAssetListItems([]);
    setAssetFull(null);
    setAssetIdx(0);
  }

  function prevAsset() {
    void fetchAndShow(assetListItems, Math.max(0, assetIdx - 1));
  }

  function nextAsset() {
    void fetchAndShow(assetListItems, Math.min(assetListItems.length - 1, assetIdx + 1));
  }

  const activeRuns = runs.filter(r => r.status === 'success');
  const pastRuns   = runs.filter(r => r.status !== 'success');

  const displayRuns = activeTab === 'active' ? activeRuns : pastRuns;

  return (
    <div className="workspace-tab" style={{ position: 'relative' }}>
      <div className="ws-header">
        <div className="ws-header-title">Workspace</div>
        <div className="ws-tabs">
          <button
            className={`ws-tab ${activeTab === 'active' ? 'active' : ''}`}
            onClick={() => setActiveTab('active')}
          >
            Active ({activeRuns.length})
          </button>
          <button
            className={`ws-tab ${activeTab === 'past' ? 'active' : ''}`}
            onClick={() => setActiveTab('past')}
          >
            Past ({pastRuns.length})
          </button>
          <button
            className="ws-tab"
            onClick={() => navigate('/settings/workspace')}
          >
            Setup ›
          </button>
        </div>
      </div>

      <div className="ws-body">
        {loading ? (
          <div className="loading-full" style={{ minHeight: 200 }}>
            <span className="spinner" />
          </div>
        ) : displayRuns.length === 0 ? (
          <div className="empty-state" style={{ paddingTop: 40 }}>
            <div className="empty-state-icon">{activeTab === 'active' ? '✦' : '◎'}</div>
            <div className="empty-state-title">
              {activeTab === 'active' ? 'No live assets yet' : 'No past runs'}
            </div>
            <div className="empty-state-text">
              {activeTab === 'active'
                ? 'Run a module from Settings to generate campaign assets.'
                : 'Past and failed runs will appear here.'}
            </div>
          </div>
        ) : (
          <>
            <div className="ws-section-label">
              {activeTab === 'active' ? 'Campaign Assets' : 'Past Runs'}
            </div>
            {displayRuns.map(run => {
              const m = moduleLabel(run.module_id);
              const b = wsBadgeProps(run.status);
              return (
                <div
                  key={run.run_id}
                  className="ws-campaign-card"
                  onClick={() => openAsset(run, displayRuns)}
                >
                  <div className="ws-campaign-row">
                    <div>
                      <div className="ws-campaign-name">{m.short}</div>
                      <div className="ws-campaign-meta">{timeAgo(run.created_at)}</div>
                    </div>
                    <span className={`ws-badge ${b.cls}`}>{b.label}</span>
                  </div>
                  <div className="ws-ch-pills">
                    <span className="ws-ch-pill">
                      <span className="ws-ch-dot" style={{ background: m.color }} />
                      {m.platform}
                    </span>
                    <span className="ws-ch-pill">{run.module_id}</span>
                  </div>
                </div>
              );
            })}
          </>
        )}
      </div>

      {assetFull && (
        <AssetViewer
          run={assetFull}
          total={assetListItems.length}
          idx={assetIdx}
          onClose={closeAsset}
          onPrev={prevAsset}
          onNext={nextAsset}
        />
      )}
    </div>
  );
}
