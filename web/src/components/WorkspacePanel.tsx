import { useEffect, useState } from 'react';
import { ApprovalBundle } from './blocks/ApprovalBundle';
import { useUI } from '../context/UIContext';
import type { RunResponse } from '../api/types';
import type { WorkspaceTab } from '../context/UIContext';

interface Props {
  open: boolean;
  tab: WorkspaceTab;
  onTabChange: (tab: WorkspaceTab) => void;
  onClose: () => void;
  selectedRun: RunResponse | null;
  onCloseRun: () => void;
}

function artifactLabel(run: RunResponse): string {
  if (!run?.module_id) return 'Artifact';
  const raw = run.result?.platform || run.module_id.split('.').pop() || 'asset';
  const label = raw.replace(/[_-]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  if (run.module_id.toLowerCase().includes('marketing.plan')) return 'Marketing plan';
  if (run.module_id.toLowerCase().includes('email')) return 'Email draft';
  if (run.module_id.toLowerCase().includes('plan')) return 'Campaign plan';
  return `${label} artifact`;
}

function CampaignsTab() {
  const { pendingRunItems, openRun, activeCampaign } = useUI();

  return (
    <div>
      <div className="bos-ws-folder">
        <div className="bos-ws-folder-title">Needs Attention</div>
        {pendingRunItems.length > 0 ? (
          <div className="bos-ws-folder-list">
            {pendingRunItems.map(run => (
              <button key={run.run_id} className="bos-ws-folder-item" onClick={() => openRun(run)}>
                <span>
                  <strong>{artifactLabel(run)}</strong>
                  <small>{run.result?.self_check === 'pass' ? 'Ready for review' : 'Review recommended'}</small>
                </span>
                <span>Review →</span>
              </button>
            ))}
          </div>
        ) : (
          <div className="bos-ws-empty">Nothing needs your attention right now.</div>
        )}
      </div>

      <div className="bos-ws-folder" style={{ marginTop: 18 }}>
        <div className="bos-ws-folder-title">Campaigns</div>
        {activeCampaign ? (
          <div className="bos-ws-folder-item static">
            <span>
              <strong>{activeCampaign.name}</strong>
              <small>Active campaign context</small>
            </span>
          </div>
        ) : (
          <div className="bos-ws-empty">
            No active campaign yet.<br />
            <span className="block-link">Ask CMO to start a campaign →</span>
          </div>
        )}
      </div>

      <div className="bos-ws-folder" style={{ marginTop: 18 }}>
        <div className="bos-ws-folder-title">Drafts & Saved Assets</div>
        <div className="bos-ws-empty">Saved campaign artifacts will appear here when the campaigns API lands.</div>
      </div>

      <div className="bos-ws-folder" style={{ marginTop: 18 }}>
        <div className="bos-ws-folder-title">Archive</div>
        <div className="bos-ws-empty">Past campaign folders will appear here.</div>
      </div>
    </div>
  );
}

function RunDetailView({ run, onBack }: { run: RunResponse; onBack: () => void }) {
  const [copied, setCopied] = useState(false);
  const [currentRun, setCurrentRun] = useState(run);

  useEffect(() => {
    setCurrentRun(run);
  }, [run]);

  const checkOk = currentRun.result?.self_check === 'pass';
  const isPlanArtifact = currentRun.module_id.toLowerCase().includes('plan');

  function handleCopy() {
    if (currentRun.result?.content) {
      navigator.clipboard.writeText(currentRun.result.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <div>
      <button
        onClick={onBack}
        style={{ background: 'none', border: 'none', color: 'var(--ink-muted)', fontSize: 12, cursor: 'pointer', padding: '0 0 12px', display: 'flex', alignItems: 'center', gap: 4 }}
      >
        ← Back
      </button>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontWeight: 700, fontSize: 13, textTransform: 'capitalize', color: 'var(--brand)' }}>{artifactLabel(currentRun)}</span>
        <span style={{ fontSize: 11, color: checkOk ? 'var(--active-green)' : 'var(--warning-amber)' }}>
          {checkOk ? 'Ready for review' : 'Review recommended'}
        </span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--ink-muted)', marginBottom: 12 }}>
        Artifact review · technical details are inside System details
      </div>
      {currentRun.result?.content && (
        <>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 6 }}>
            <button
              onClick={handleCopy}
              className="btn btn-secondary"
              style={{ fontSize: 11, padding: '3px 10px' }}
            >
              {copied ? '✓ Copied' : isPlanArtifact ? 'Copy plan' : 'Copy'}
            </button>
          </div>
          <ApprovalBundle
            key={currentRun.run_id}
            run={currentRun}
            surfaceContext="panel"
            revisionHistory={[
              { role: 'ai', text: `Approval task: ${currentRun.result?.content || ''}` },
            ]}
            onRevision={(_, revised) => setCurrentRun(revised)}
            onApproved={onBack}
          />
        </>
      )}
    </div>
  );
}

export function WorkspacePanel({ open, tab, onTabChange, onClose, selectedRun, onCloseRun }: Props) {
  return (
    <>
      {open && <div className="bos-ws-backdrop" onClick={onClose} />}
      <div className={`bos-ws-panel ${open ? 'bos-ws-panel-open' : ''}`}>
        <div className="bos-ws-header">
          <span className="bos-ws-title">Workspace</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <a href="/admin/onboarding" style={{ fontSize: 11, color: 'var(--text2, #9ca3af)', textDecoration: 'none' }}>Admin →</a>
            <button className="bos-ws-close" onClick={onClose}>✕ Close</button>
          </div>
        </div>

        {selectedRun ? (
          <div className="bos-ws-body">
            <RunDetailView run={selectedRun} onBack={onCloseRun} />
          </div>
        ) : (
          <>
            <div className="bos-ws-tabs">
              {(['campaigns'] as WorkspaceTab[]).map(t => (
                <button
                  key={t}
                  className={`bos-ws-tab ${tab === t ? 'active' : ''}`}
                  onClick={() => onTabChange(t)}
                >
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>
            <div className="bos-ws-body">
              <CampaignsTab />
            </div>
          </>
        )}
      </div>
    </>
  );
}
