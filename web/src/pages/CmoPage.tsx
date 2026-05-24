import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CmoChat } from './CmoChat';
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
import { ApprovalBundle } from '../components/blocks/ApprovalBundle';
import type { ObjectiveOut, RunResponse, StreamUpdateOut } from '../api/types';

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
  if (!run?.module_id) return 'Artifact';
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

function runTimestamp(run: Partial<RunResponse>): number {
  const ts = Date.parse(String(run.created_at || ''));
  return Number.isFinite(ts) ? ts : 0;
}

function updateBrandRef(update: StreamUpdateOut): string | null {
  const ref = update.data_json?.brand_ref ?? update.data_json?.brand_id;
  return typeof ref === 'string' && ref ? ref : null;
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

function streamCardTitle(update: StreamUpdateOut): string {
  if (update.type === 'decision_brief') return 'Decision Brief';
  if (update.type === 'outcome') return 'Outcome · Memory Updated';
  if (update.type === 'setup_blocker') return 'Setup Blocker';
  if (update.type === 'pending_artifact') return 'Pending Artifact';
  return titleCase(update.type || 'Stream Card');
}

function confidenceColor(value: unknown): 'amber' | 'green' | 'blue' {
  const text = String(value || '').toLowerCase();
  if (text.includes('known') || text.includes('high')) return 'green';
  if (text.includes('watch')) return 'blue';
  return 'amber';
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map(item => String(item)).filter(Boolean) : [];
}

function ObjectiveAnchor({ objective, onSetup }: { objective: ObjectiveOut | null; onSetup: () => void }) {
  if (!objective) {
    return (
      <div className="obj-anchor obj-anchor-setup">
        <span className="obj-dot" />
        <div>
          <div className="obj-label">Setup blocker</div>
          <div className="obj-text">No active objective — BOS cannot run the loop without one.</div>
        </div>
        <button className="stream-link" onClick={onSetup}>Set up →</button>
      </div>
    );
  }
  return (
    <div className="obj-anchor">
      <span className="obj-dot" />
      <div>
        <div className="obj-label">Active Objective</div>
        <div className="obj-text">{objective.summary}</div>
      </div>
      <button className="obj-meta" onClick={onSetup}>{objective.status}</button>
    </div>
  );
}

function StreamDataCard({ update, brandName, objectiveTitle, onDismiss, onAskCMO, onRecordOutcome, onRevise, onInvestigate, onConfigure }: {
  update: StreamUpdateOut;
  brandName: string;
  objectiveTitle: string;
  onDismiss: (update: StreamUpdateOut) => void;
  onAskCMO: (update: StreamUpdateOut) => void;
  onRecordOutcome: (update: StreamUpdateOut) => void;
  onRevise: (update: StreamUpdateOut) => void;
  onInvestigate: (update: StreamUpdateOut) => void;
  onConfigure: (update: StreamUpdateOut) => void;
}) {
  const [busy, setBusy] = useState(false);
  const data = update.data_json || {};
  const evidence = asStringArray(data.primary_evidence || data.evidence);
  const actions = asStringArray(data.allowed_actions);
  const hypotheses: any[] = Array.isArray(data.hypothesis_ranking) ? data.hypothesis_ranking : [];
  const doNot = asStringArray(data.do_not_list);
  const confidence = data.confidence || update.priority || 'Directional';
  const sourceState = data.source_state || update.source_key || timeAgo(update.created_at);
  const title = streamCardTitle(update);
  const cardObjective = String(data.objective_ref || data.objective || objectiveTitle || 'Active objective');
  const cardBrand = String(data.brand_name || data.brand || brandName);

  async function dismiss() {
    setBusy(true);
    try {
      await api.dismissStreamUpdate(update.id);
      onDismiss(update);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className={`g2card ${update.type === 'decision_brief' ? 'featured' : ''}`}>
      <div className="g2top">
        <span className={`g2type ${update.type}`}>{title}</span>
        <span className={`g2conf ${confidenceColor(confidence)}`}>{String(confidence)}</span>
      </div>
      <div className="g2obj">{cardObjective}</div>
      <div className="g2brand">{cardBrand}</div>
      <div className="g2why">{String(data.why_now || data.summary || 'BOS surfaced this for review.')}</div>
      {evidence.length > 0 && <div className="g2ev">{evidence.map((item, idx) => <div className="g2ev-item" key={idx}>{item}</div>)}</div>}
      {hypotheses.length > 0 && <div className="g2ev">{hypotheses.slice(0, 3).map((h, idx) => <div className="g2ev-item" key={idx}>{h.hypothesis || JSON.stringify(h)}</div>)}</div>}
      {doNot.length > 0 && <div className="g2ev">{doNot.map((item, idx) => <div className="g2ev-item" key={idx}>Do not: {item}</div>)}</div>}
      {data.recommended_next && <div className="g2rec"><b>Next —</b>{String(data.recommended_next)}</div>}
      {data.approval_boundary && <div className="g2boundary">{String(data.approval_boundary)}</div>}
      <div className="g2src-row"><span className="g2src">{String(sourceState)}</span></div>
      <div className="g2actions">
        {actions.includes('approve') && <button className="btn btn-primary" onClick={dismiss} disabled={busy}>{busy ? '…' : 'Approve'}</button>}
        {actions.includes('revise') && <button className="btn btn-ghost" onClick={() => onRevise(update)}>Revise</button>}
        {actions.includes('investigate') && <button className="btn btn-accent" onClick={() => onInvestigate(update)}>Investigate</button>}
        {actions.includes('ask CMO') && <button className="btn btn-ghost" onClick={() => onAskCMO(update)}>Ask CMO</button>}
        {actions.includes('record outcome') && <button className="btn btn-accent" onClick={() => onRecordOutcome(update)}>Record outcome</button>}
        {actions.includes('configure') && <button className="btn btn-accent" onClick={() => onConfigure(update)}>Configure</button>}
        {actions.includes('dismiss') && <button className="btn btn-ghost" onClick={dismiss} disabled={busy}>{busy ? '…' : 'Dismiss'}</button>}
      </div>
    </article>
  );
}

function StreamArtifactCard({ run, brandName, objectiveTitle, onApprove, onDismiss, onRevise }: {
  run: RunResponse;
  brandName: string;
  objectiveTitle: string;
  onApprove: (run: RunResponse) => void;
  onDismiss: (run: RunResponse) => void;
  onRevise: (run: RunResponse) => void;
}) {
  const [busy, setBusy] = useState(false);
  const status = artifactStatus(run);
  const createdAt = new Date(run.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  const result = run.result as any;
  const evidence = asStringArray(result?.primary_evidence || result?.evidence);
  const source = artifactPlatform(run) + ' · ' + createdAt + ' · ' + timeAgo(run.created_at);

  async function approve() {
    setBusy(true);
    try {
      const publishModule = run.result?.block?.action_modules?.publish;
      if (publishModule) {
        const resp = await api.executeRunAction(run.run_id, 'publish', { confirm: true });
        window.dispatchEvent(new CustomEvent('bos:focus-artifact', { detail: resp.action_run }));
      } else {
        await api.approveRun(run.run_id);
      }
      onApprove(run);
    } finally {
      setBusy(false);
    }
  }

  async function dismiss() {
    setBusy(true);
    onDismiss(run);
    try {
      await api.rejectRun(run.run_id, 'Dismissed from Stream.');
    } catch {
      // optimistic — already removed from UI
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className={`g2card ${status === 'pending' ? '' : ''}`}>
      <div className="g2top">
        <span className="g2type pending_artifact">{artifactTitle(run)}</span>
        <span className={`g2conf ${status === 'approved' ? 'green' : 'amber'}`}>{statusText(status)}</span>
      </div>
      <div className="g2obj">{objectiveTitle || 'Active objective'}</div>
      <div className="g2brand">{brandName}</div>
      <div className="g2why">{String(result?.why_now || result?.summary || result?.content || 'Artifact generated for operator review.').slice(0, 260)}</div>
      {evidence.length > 0 && <div className="g2ev">{evidence.map((item, idx) => <div className="g2ev-item" key={idx}>{item}</div>)}</div>}
      {result?.recommended_next && <div className="g2rec"><b>Next —</b>{String(result.recommended_next)}</div>}
      {result?.approval_boundary && <div className="g2boundary">{String(result.approval_boundary)}</div>}
      <details className="artifact-preview">
        <summary>Platform preview</summary>
        <div className="stream-artifact-preview">{renderNativePreview(run)}</div>
      </details>
      <div className="g2src-row"><span className="g2src">{source}</span></div>
      <div className="g2actions">
        <button className="btn btn-ghost" onClick={() => onRevise(run)} disabled={busy}>Revise</button>
        {status !== 'approved' && status !== 'dismissed' && (
          <>
            <button className="btn btn-ghost" onClick={dismiss} disabled={busy}>Dismiss</button>
            <button className="btn btn-primary" onClick={approve} disabled={busy}>{busy ? '…' : 'Approve'}</button>
          </>
        )}
      </div>
    </article>
  );
}

function StreamRunPanel({ run, onClose, onApproved, onDismissed }: {
  run: RunResponse;
  onClose: () => void;
  onApproved: (run: RunResponse) => void;
  onDismissed: (run: RunResponse) => void;
}) {
  const [currentRun, setCurrentRun] = useState(run);
  return (
    <>
      <div className="stream-panel-header">
        <span className="stream-panel-title">{artifactTitle(run)}</span>
        <button className="stream-panel-close" onClick={onClose}>✕</button>
      </div>
      <div className="stream-panel-body">
        <ApprovalBundle
          key={currentRun.run_id}
          run={currentRun}
          surfaceContext="panel"
          revisionHistory={[{ role: 'ai', text: currentRun.result?.content || '' }]}
          onRevision={(_, revised) => setCurrentRun(revised)}
          onApproved={onApproved}
          onDismissed={onDismissed}
        />
      </div>
    </>
  );
}

function StreamUpdatePanel({ update, onClose }: {
  update: StreamUpdateOut;
  onClose: () => void;
}) {
  const data = update.data_json || {};
  const evidence = asStringArray(data.primary_evidence || data.evidence);
  const hypotheses: any[] = Array.isArray(data.hypothesis_ranking) ? data.hypothesis_ranking : [];
  const doNot = asStringArray(data.do_not_list);
  const confidence = data.confidence || update.priority || 'Directional';
  return (
    <>
      <div className="stream-panel-header">
        <span className="stream-panel-title">{streamCardTitle(update)}</span>
        <button className="stream-panel-close" onClick={onClose}>✕</button>
      </div>
      <div className="stream-panel-body">
        <div className="spd-meta">
          <span className={`g2conf ${confidenceColor(confidence)}`}>{String(confidence)}</span>
          {update.source_key && <span className="spd-source">{update.source_key}</span>}
        </div>
        {data.why_now && <div className="spd-section"><div className="spd-label">Why now</div><div className="spd-body">{String(data.why_now)}</div></div>}
        {evidence.length > 0 && (
          <div className="spd-section">
            <div className="spd-label">Evidence</div>
            {evidence.map((item, i) => <div className="spd-ev-item" key={i}>{item}</div>)}
          </div>
        )}
        {hypotheses.length > 0 && (
          <div className="spd-section">
            <div className="spd-label">Hypotheses</div>
            {hypotheses.map((h, i) => <div className="spd-ev-item" key={i}>{h.hypothesis || JSON.stringify(h)}</div>)}
          </div>
        )}
        {doNot.length > 0 && (
          <div className="spd-section">
            <div className="spd-label">Do not</div>
            {doNot.map((item, i) => <div className="spd-ev-item spd-ev-donot" key={i}>{item}</div>)}
          </div>
        )}
        {data.recommended_next && (
          <div className="spd-section">
            <div className="spd-label">Recommended next</div>
            <div className="spd-rec">{String(data.recommended_next)}</div>
          </div>
        )}
        {data.summary && !data.why_now && (
          <div className="spd-section"><div className="spd-body">{String(data.summary)}</div></div>
        )}
        {data.approval_boundary && <div className="spd-boundary">{String(data.approval_boundary)}</div>}
      </div>
    </>
  );
}

export function CmoPage() {
  const navigate = useNavigate();
  const { pendingRunItems, removePendingRun, activeBrand } = useUI();
  const [artifacts, setArtifacts] = useState<RunResponse[]>([]);
  const [streamUpdates, setStreamUpdates] = useState<StreamUpdateOut[]>([]);
  const [activeObjective, setActiveObjective] = useState<ObjectiveOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [panelItem, setPanelItem] = useState<StreamUpdateOut | RunResponse | null>(null);
  const [mobileView, setMobileView] = useState<'chat' | 'stream'>('chat');

  useEffect(() => {
    const handleFocusArtifact = (e: Event) => {
      setPanelItem((e as CustomEvent<RunResponse>).detail);
      setMobileView('stream');
    };
    window.addEventListener('bos:focus-artifact', handleFocusArtifact);
    return () => window.removeEventListener('bos:focus-artifact', handleFocusArtifact);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const brandId = activeBrand?.id;
    setLoading(true);
    Promise.all([
      api.getRuns({ limit: 40, brand_id: brandId }).then(async r => {
        const candidates = r.runs.filter(run =>
          run.status !== 'failed' &&
          run.approval_status !== 'rejected' &&
          (!brandId || run.brand_id === brandId)
        );
        const full = await Promise.all(
          candidates.map(async run => {
            const fullRun = await api.getRun(run.run_id).catch(() => null);
            return fullRun ? ({ ...fullRun, approval_status: run.approval_status, brand_id: fullRun.brand_id || run.brand_id } as RunResponse) : null;
          })
        );
        return full.filter((run): run is RunResponse => !!run && (!brandId || run.brand_id === brandId));
      }),
      api.refreshStream().catch(() => null).then(() => api.getStream(false).catch(() => ({ updates: [], total: 0 }))),
      api.getActiveObjective(brandId).catch(() => null),
    ])
      .then(([fullRuns, stream, objective]) => {
        if (!cancelled) {
          setArtifacts(fullRuns);
          setStreamUpdates((stream.updates || []).filter(update =>
            ['outcome', 'decision_brief', 'setup_blocker', 'pending_artifact'].includes(update.type) &&
            (!brandId || updateBrandRef(update) === brandId)
          ));
          setActiveObjective(objective);
        }
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [activeBrand?.id]);

  const streamArtifacts = useMemo(() => {
    const brandId = activeBrand?.id;
    const apiIds = new Set(artifacts.map(r => r.run_id));
    const oneHourAgo = Date.now() - 60 * 60 * 1000;
    // Only show localStorage items that (1) aren't in the API yet and (2) are recent enough
    // to be legitimately new — older items are stale rejected/failed runs. Guard every field
    // because older browsers/staging may have partial cached run objects.
    const freshPending = pendingRunItems.filter(r =>
      r?.run_id &&
      !apiIds.has(r.run_id) &&
      runTimestamp(r) > oneHourAgo &&
      (!brandId || r.brand_id === brandId)
    );
    return [...artifacts, ...freshPending]
      .filter(r => !!r?.run_id && runTimestamp(r) > 0 && (!brandId || r.brand_id === brandId))
      .sort((a, b) => runTimestamp(b) - runTimestamp(a));
  }, [activeBrand?.id, artifacts, pendingRunItems]);

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

  function navigateToCMO(source: StreamUpdateOut | RunResponse, actionLabel: string) {
    const isRun = 'run_id' in source;
    window.dispatchEvent(new CustomEvent('bos:stream-card-context', {
      detail: {
        sourceType: isRun ? 'artifact' : 'update',
        id: isRun ? (source as RunResponse).run_id : (source as StreamUpdateOut).id,
        type: isRun ? 'pending_artifact' : (source as StreamUpdateOut).type,
        actionLabel,
        data_json: isRun ? (source as RunResponse).result : (source as StreamUpdateOut).data_json,
        priority: isRun ? undefined : (source as StreamUpdateOut).priority,
        source_key: isRun ? undefined : (source as StreamUpdateOut).source_key,
      },
    }));
    // CmoChat is mounted in the right panel — event is sufficient, no navigation needed
  }

  function configureFromCard(update: StreamUpdateOut) {
    const target = String(update.data_json?.config_target || 'objective-loop');
    if (target.includes('connector') || target.includes('gmail')) navigate('/admin/connectors');
    else navigate('/admin/objective-loop');
  }

  if (loading) {
    return <div className="loading-full"><span className="spinner" /></div>;
  }

  const attentionCount = streamArtifacts.filter(run => artifactStatus(run) === 'pending').length + streamUpdates.length;
  const dateLabel = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
  const brandLabel = activeBrand?.name || 'All brands';
  const objectiveTitle = activeObjective?.summary || 'Active objective';

  const panelIsRun = panelItem && 'run_id' in panelItem;

  return (
    <div className={`stream-cmo-shell${mobileView === 'stream' ? ' mobile-stream-active' : ''}`}>
      {/* ── Left: CMO chat ── */}
      <div className="stream-cmo-chat-col">
        <CmoChat />
      </div>

      {/* ── Right: decision feed ── */}
      <div className="stream-cmo-feed">
      <div className={`stream-feed-col${panelItem ? ' stream-panel-open' : ''}`}>
        <div className="stream-content-inner">
          <div className="stream-header-zone">
            <button className="mobile-back-btn" onClick={() => setMobileView('chat')}>← Chat</button>
            <div className="stream-kicker">{dateLabel} · {brandLabel}</div>
            {attentionCount > 0
              ? <h2 className="stream-title">{attentionCount} item{attentionCount !== 1 ? 's' : ''} need your judgment</h2>
              : <h2 className="stream-title">Objective loop quiet</h2>
            }
            <div className="stream-sub">Ranked by urgency. Act on what matters, dismiss what does not.</div>
            <ObjectiveAnchor objective={activeObjective} onSetup={() => navigate('/admin/objective-loop')} />
          </div>

          {streamArtifacts.length === 0 && streamUpdates.length === 0 ? (
            <div className="g2card">
              <span className="g2type outcome">Objective loop quiet</span>
              <div className="g2why" style={{ marginTop: 10, fontWeight: 700 }}>No decisions need attention right now.</div>
              <div className="g2why">BOS is watching the active objective, Gmail replies, pending outcomes, and setup readiness. If Gmail, list, brand context, or objective setup blocks the loop, Stream will surface a setup_blocker here.</div>
              <div className="g2rec"><b>Next —</b>Leave Stream alone until a decision, outcome, or setup blocker appears.</div>
              <button className="btn btn-accent" onClick={() => navigate('/admin/objective-loop')}>Set up the objective loop →</button>
            </div>
          ) : (
            <div className="stream-artifact-feed">
              {streamUpdates.map(update => (
                <StreamDataCard
                  key={update.id}
                  update={update}
                  brandName={brandLabel}
                  objectiveTitle={objectiveTitle}
                  onDismiss={dismissed => setStreamUpdates(prev => prev.filter(item => item.id !== dismissed.id))}
                  onAskCMO={card => navigateToCMO(card, 'ask CMO')}
                  onRecordOutcome={card => navigateToCMO(card, 'record outcome')}
                  onRevise={card => navigateToCMO(card, 'revise')}
                  onInvestigate={card => setPanelItem(card)}
                  onConfigure={configureFromCard}
                />
              ))}
              {streamArtifacts.map(run => (
                <StreamArtifactCard
                  key={run.run_id}
                  run={run}
                  brandName={brandLabel}
                  objectiveTitle={objectiveTitle}
                  onApprove={run => { updateLocalStatus(run, 'approved'); if (panelItem && 'run_id' in panelItem && panelItem.run_id === run.run_id) setPanelItem(null); }}
                  onDismiss={run => { updateLocalStatus(run, 'rejected'); if (panelItem && 'run_id' in panelItem && panelItem.run_id === run.run_id) setPanelItem(null); }}
                  onRevise={run => setPanelItem(run)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {panelItem && <div className="stream-panel-backdrop" onClick={() => setPanelItem(null)} />}

      <div className={`stream-side-panel${panelItem ? ' stream-side-panel-open' : ''}`}>
        {panelItem && (panelIsRun ? (
          <StreamRunPanel
            key={(panelItem as RunResponse).run_id}
            run={panelItem as RunResponse}
            onClose={() => setPanelItem(null)}
            onApproved={run => { updateLocalStatus(run, 'approved'); setPanelItem(null); }}
            onDismissed={run => { updateLocalStatus(run, 'rejected'); setPanelItem(null); }}
          />
        ) : (
          <StreamUpdatePanel
            key={(panelItem as StreamUpdateOut).id}
            update={panelItem as StreamUpdateOut}
            onClose={() => setPanelItem(null)}
          />
        ))}
      </div>
      </div>{/* /stream-cmo-feed */}
    </div>
  );
}
