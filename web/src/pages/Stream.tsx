import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useUI } from '../context/UIContext';
import { timeAgo } from '../utils/runs';
import { GoogleSearchPreview } from '../components/blocks/previews/GoogleSearchPreview';
import { GoogleDisplayPreview } from '../components/blocks/previews/GoogleDisplayPreview';
import { FacebookFeedPreview } from '../components/blocks/previews/FacebookFeedPreview';
import { InstagramFeedPreview } from '../components/blocks/previews/InstagramFeedPreview';
import { InstagramStoryPreview } from '../components/blocks/previews/InstagramStoryPreview';
import { EmailPreview } from '../components/blocks/previews/EmailPreview';
import { PinterestPreview } from '../components/blocks/previews/PinterestPreview';
import { TwitterFeedPreview } from '../components/blocks/previews/TwitterFeedPreview';
import type { RunResponse } from '../api/types';

type ArtifactStatus = 'pending' | 'approved' | 'dismissed' | 'complete';

function titleCase(value: string): string {
  return value
    .replace(/[_-]/g, ' ')
    .split(' ')
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function artifactTitle(run: RunResponse): string {
  const id = run.module_id.toLowerCase();
  const platform = titleCase(run.result?.platform || run.module_id.split('.').pop() || 'asset');
  if (id.includes('email') && id.includes('plan')) return 'Email Campaign Plan';
  if (id.includes('email')) return 'Email Draft';
  if (id.includes('plan')) return 'Campaign Plan';
  if (id.includes('report') || id.includes('analytics')) return 'Marketing Report';
  if (id.includes('google')) return 'Google Ad Draft';
  if (id.includes('facebook')) return 'Facebook Draft';
  if (id.includes('instagram')) return 'Instagram Draft';
  if (id.includes('twitter') || id.includes('x.')) return 'Social Post Draft';
  if (id.includes('pinterest')) return 'Pinterest Draft';
  return `${platform} Draft`;
}

function artifactPlatform(run: RunResponse): string {
  return titleCase(run.result?.platform || run.module_id.split('.').pop() || 'asset');
}

function artifactStatus(run: RunResponse): ArtifactStatus {
  const status = (run as any).approval_status || (run.result as any)?.approval_status;
  if (status === 'approved') return 'approved';
  if (status === 'rejected') return 'dismissed';
  if (status === 'pending') return 'pending';
  return run.result?.self_check === 'pass' ? 'pending' : 'complete';
}

function statusText(status: ArtifactStatus): string {
  if (status === 'approved') return 'Approved';
  if (status === 'dismissed') return 'Dismissed';
  if (status === 'pending') return 'Needs review';
  return 'Saved';
}

function renderNativePreview(run: RunResponse) {
  const result = run.result;
  if (!result) return <div className="stream-artifact-fallback">No artifact content available.</div>;

  const moduleId = run.module_id.toLowerCase();
  const channel = `${moduleId} ${(result.platform || '').toLowerCase()}`;
  const brandName = result.block?.brand_name || result.brand_name || 'Klaroha';
  const socialHandle = result.block?.brand_handle || result.brand_handle || '@klarohahq';

  if (moduleId.includes('google') && (moduleId.includes('text') || moduleId.includes('search'))) {
    const block = result.block;
    const headline = Array.isArray(block?.headlines)
      ? block.headlines.slice(0, 3).map((h: any) => h.text).filter(Boolean).join(' | ')
      : (block?.headline || result.headline || '');
    const description = Array.isArray(block?.descriptions)
      ? block.descriptions.slice(0, 2).map((d: any) => d.text).filter(Boolean).join(' ')
      : (block?.description || result.description || result.content || '');
    return (
      <GoogleSearchPreview
        headline={headline || 'Headline Missing'}
        description={description || 'Description Missing'}
        displayUrl={block?.display_url || block?.displayUrl || result.display_url || 'example.com'}
      />
    );
  }

  if (channel.includes('google') && channel.includes('display')) {
    return (
      <GoogleDisplayPreview
        dimensions={result.dimensions || '300x250'}
        headline={result.headline || 'Headline Missing'}
        description={result.description || 'Description Missing'}
        ctaText={result.cta || 'Learn More'}
      />
    );
  }

  if (channel.includes('facebook')) {
    return <FacebookFeedPreview pageName={brandName} adCopy={result.content || 'Copy missing'} ctaText={result.cta || 'Learn More'} />;
  }
  if (channel.includes('instagram') && channel.includes('story')) {
    return <InstagramStoryPreview username={socialHandle} adCopy={result.content || 'Copy missing'} ctaText={result.cta || 'Shop Now'} />;
  }
  if (channel.includes('instagram')) {
    return <InstagramFeedPreview username={socialHandle} adCopy={result.content || 'Copy missing'} />;
  }
  if (channel.includes('twitter') || moduleId.includes('twitter')) {
    return <TwitterFeedPreview username={socialHandle} tweetText={result.content || 'Copy missing'} />;
  }
  if (channel.includes('email') && moduleId.includes('plan')) {
    return <div className="stream-artifact-fallback">{result.content || 'Email campaign plan unavailable.'}</div>;
  }
  if (channel.includes('email')) {
    return <EmailPreview senderName={brandName} subject={result.subject || 'Subject Missing'} preheader={result.preheader || 'Preheader missing'} body={result.content || 'Body missing'} />;
  }
  if (channel.includes('pinterest')) {
    return <PinterestPreview title={result.headline || 'Title Missing'} description={result.content || 'Description missing'} />;
  }

  return <div className="stream-artifact-fallback">{result.content || 'Artifact content unavailable.'}</div>;
}

function StreamArtifactCard({ run, onApprove, onDismiss, onRevise }: {
  run: RunResponse;
  onApprove: (run: RunResponse) => void;
  onDismiss: (run: RunResponse) => void;
  onRevise: (run: RunResponse) => void;
}) {
  const [busy, setBusy] = useState(false);
  const status = artifactStatus(run);
  const createdAt = new Date(run.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });

  async function approve() {
    setBusy(true);
    try {
      await api.approveRun(run.run_id);
      onApprove(run);
    } finally {
      setBusy(false);
    }
  }

  async function dismiss() {
    setBusy(true);
    try {
      await api.rejectRun(run.run_id, 'Dismissed from Stream.');
      onDismiss(run);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className={`stream-artifact-card stream-artifact-${status}`}>
      <div className="stream-artifact-chrome">
        <div>
          <div className="stream-artifact-title">{artifactTitle(run)}</div>
          <div className="stream-artifact-meta">{artifactPlatform(run)} · {createdAt} · {timeAgo(run.created_at)}</div>
        </div>
        <span className="stream-artifact-status">{statusText(status)}</span>
      </div>

      <div className="stream-artifact-preview">
        {renderNativePreview(run)}
      </div>

      <div className="stream-artifact-actions">
        <button className="stream-btn stream-btn-revise" onClick={() => onRevise(run)} disabled={busy}>Revise in chat</button>
        {status !== 'approved' && status !== 'dismissed' && (
          <>
            <button className="stream-btn stream-btn-dismiss" onClick={dismiss} disabled={busy}>Dismiss</button>
            <button className="stream-btn stream-btn-approve" onClick={approve} disabled={busy}>{busy ? '…' : 'Approve'}</button>
          </>
        )}
      </div>
    </article>
  );
}

export function Stream() {
  const navigate = useNavigate();
  const { pendingRunItems, removePendingRun } = useUI();
  const [artifacts, setArtifacts] = useState<RunResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api.getRuns({ limit: 40 })
      .then(async r => {
        const candidates = r.runs.filter(run => run.status !== 'failed' && run.approval_status !== 'rejected');
        const full = await Promise.all(
          candidates.map(async run => {
            const fullRun = await api.getRun(run.run_id).catch(() => null);
            return fullRun ? ({ ...fullRun, approval_status: run.approval_status } as RunResponse) : null;
          })
        );
        if (!cancelled) setArtifacts(full.filter((run): run is RunResponse => !!run));
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const streamArtifacts = useMemo(() => {
    const byId = new Map<string, RunResponse>();
    [...artifacts, ...pendingRunItems].forEach(run => byId.set(run.run_id, run));
    return [...byId.values()].sort((a, b) => b.created_at.localeCompare(a.created_at));
  }, [artifacts, pendingRunItems]);

  function updateLocalStatus(run: RunResponse, status: 'approved' | 'rejected') {
    removePendingRun(run.run_id);
    if (status === 'rejected') {
      setArtifacts(prev => prev.filter(item => item.run_id !== run.run_id));
      return;
    }
    setArtifacts(prev => prev.map(item =>
      item.run_id === run.run_id ? ({ ...item, approval_status: status } as RunResponse) : item
    ));
  }

  function handleRevise(run: RunResponse) {
    navigate('/cmo');
    window.dispatchEvent(new CustomEvent('bos:stream-artifact-revise', { detail: { runId: run.run_id } }));
  }

  if (loading) {
    return <div className="loading-full"><span className="spinner" /></div>;
  }

  const pendingCount = streamArtifacts.filter(run => artifactStatus(run) === 'pending').length;
  const dateLabel = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });

  return (
    <div className="stream-screen stream-artifact-screen">
      <div className="stream-header-row">
        <div>
          <div className="stream-kicker">{dateLabel}</div>
          {pendingCount > 0
            ? <h2 className="stream-date">{pendingCount} artifact{pendingCount !== 1 ? 's' : ''} need attention</h2>
            : <h2 className="stream-date">Artifact stream</h2>
          }
        </div>
        <div className="stream-signal-pill">{streamArtifacts.length} saved</div>
      </div>

      {streamArtifacts.length === 0 ? (
        <div className="state-message stream-empty-state">
          Chat artifacts will appear here as timestamped native previews, even if chat history is cleared.<br />
          <button className="stream-link" onClick={() => navigate('/cmo')}>Create an artifact →</button>
        </div>
      ) : (
        <div className="stream-artifact-feed">
          {streamArtifacts.map(run => (
            <StreamArtifactCard
              key={run.run_id}
              run={run}
              onApprove={run => updateLocalStatus(run, 'approved')}
              onDismiss={run => updateLocalStatus(run, 'rejected')}
              onRevise={handleRevise}
            />
          ))}
        </div>
      )}
    </div>
  );
}
