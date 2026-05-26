import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import { ApprovalBundle } from '../components/blocks/ApprovalBundle';
import type { ObjectiveOut, RunListItem, RunResponse, StreamUpdateOut } from '../api/types';

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
  if (id.includes('creative.post')) return 'Facebook Post Creative';
  if (id.includes('meta.pages.read')) return 'Facebook Pages';
  if (id.includes('meta.posts.draft')) return 'Facebook Post Draft';
  if (id.includes('meta.posts.publish')) return 'Facebook Post';
  if (id.includes('meta.posts.read')) return 'Facebook Posts';
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

function runFromListItem(item: RunListItem): RunResponse {
  return {
    run_id: item.run_id,
    module_id: item.module_id,
    vertical: item.vertical,
    status: item.status,
    approval_status: item.approval_status,
    campaign_id: item.campaign_id,
    brand_id: item.brand_id,
    result: item.result || undefined,
    execution: item.provider ? {
      provider: item.provider,
      model: item.model || '',
      mode: 'preview',
      attempts: 1,
      latency_ms: item.latency_ms || 0,
      tokens_used: item.tokens || undefined,
      provider_cost: item.cost || undefined,
    } : undefined,
    created_at: item.created_at,
  };
}

let artifactHydrationQueue: Promise<void> = Promise.resolve();

function enqueueArtifactHydration(task: () => Promise<void>): Promise<void> {
  artifactHydrationQueue = artifactHydrationQueue.then(task).catch(() => undefined);
  return artifactHydrationQueue;
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
    return <GoogleDisplayPreview dimensions={result.dimensions || '300x250'} headline={result.headline || 'Headline Missing'} description={result.description || 'Description Missing'} ctaText={result.cta || 'Learn More'} />;
  }
  if (result.block?.type === 'creative_post_asset' && result.block?.status === 'succeeded') {
    const b = result.block as any;
    const imageUrl = b.image_data_b64 ? `data:${b.mime_type || 'image/png'};base64,${b.image_data_b64}` : undefined;
    return <FacebookFeedPreview pageName={brandName} adCopy={b.caption || b.message || 'Caption pending — review to add copy'} imageUrl={imageUrl} ctaText="" />;
  }
  if (result.block?.type === 'fb_page_post_draft') {
    return <FacebookFeedPreview pageName={result.block.page_name || brandName} adCopy={result.block.message || result.content || 'Post text missing'} ctaText="" />;
  }
  if (result.block?.type === 'fb_page_post_result') {
    const b = result.block as any;
    const succeeded = b.status === 'succeeded';
    return (
      <div style={{ padding: '14px 16px', fontSize: 13, color: '#1f2937', border: `1px solid ${succeeded ? '#bbf7d0' : '#fca5a5'}`, borderRadius: 8, background: succeeded ? '#f0fdf4' : '#fef2f2' }}>
        <div style={{ fontWeight: 700, marginBottom: 4 }}>{succeeded ? 'Published to Facebook' : 'Facebook publish failed'}</div>
        {b.message_preview && <div style={{ color: '#4b5563', marginBottom: 6, lineHeight: 1.4 }}>{b.message_preview.slice(0, 120)}{b.message_preview.length > 120 ? '…' : ''}</div>}
        {b.post_id && <div style={{ color: '#6b7280', fontSize: 11, marginBottom: 4 }}>Post ID: {b.post_id}</div>}
        {b.permalink && <a href={b.permalink} target="_blank" rel="noreferrer" style={{ color: '#2563eb', fontSize: 12, fontWeight: 600 }}>View on Facebook →</a>}
      </div>
    );
  }
  if (result.block?.type === 'fb_page_video_result') {
    const b = result.block as any;
    const succeeded = b.status === 'succeeded';
    return (
      <div style={{ padding: '14px 16px', fontSize: 13, color: '#1f2937', border: `1px solid ${succeeded ? '#bbf7d0' : '#fca5a5'}`, borderRadius: 8, background: succeeded ? '#f0fdf4' : '#fef2f2' }}>
        <div style={{ fontWeight: 700, marginBottom: 4 }}>{succeeded ? 'Facebook video published' : 'Facebook video publish failed'}</div>
        {b.description_preview && <div style={{ color: '#4b5563', marginBottom: 6, lineHeight: 1.4 }}>{b.description_preview.slice(0, 120)}{b.description_preview.length > 120 ? '…' : ''}</div>}
        {b.video_id && <div style={{ color: '#6b7280', fontSize: 11, marginBottom: 4 }}>Video ID: {b.video_id}</div>}
        {b.permalink && <a href={b.permalink} target="_blank" rel="noreferrer" style={{ color: '#2563eb', fontSize: 12, fontWeight: 600 }}>View on Facebook →</a>}
      </div>
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
  if (result.block?.type === 'meta_page_posts') {
    const b = result.block as any;
    if (b.status === 'failed') {
      return (
        <div style={{ padding: 24, textAlign: 'center', color: '#6b7280', fontSize: 13 }}>
          <div style={{ color: '#ef4444', fontWeight: 600, marginBottom: 6 }}>Facebook not connected</div>
          <div>{b.message || result.content}</div>
        </div>
      );
    }
    const posts: any[] = b.posts || [];
    return (
      <div style={{ padding: '16px 20px', fontSize: 13, color: '#1f2937', maxWidth: 520 }}>
        <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 12 }}>Recent Posts · {b.page_name || brandName}</div>
        {posts.length === 0
          ? <div style={{ color: '#6b7280' }}>No posts found on this page.</div>
          : posts.slice(0, 5).map((p: any, i: number) => (
            <div key={p.post_id || i} style={{ padding: '8px 0', borderTop: i ? '1px solid #f3f4f6' : 'none' }}>
              <div style={{ color: '#6b7280', fontSize: 11, marginBottom: 2 }}>{(p.created_time || '').slice(0, 10)}</div>
              <div style={{ lineHeight: 1.4, marginBottom: 4 }}>{p.message ? (p.message.length > 120 ? p.message.slice(0, 120) + '…' : p.message) : '(no text)'}</div>
              <div style={{ color: '#6b7280', fontSize: 11 }}>❤️ {p.likes ?? 0} · 💬 {p.comments ?? 0} · ↗ {p.shares ?? 0}</div>
            </div>
          ))}
      </div>
    );
  }
  if (result.block?.type === 'meta_page_inventory') {
    const pages: any[] = (result.block as any).pages || [];
    return (
      <div style={{ padding: '16px 20px', fontSize: 13, color: '#1f2937', maxWidth: 520 }}>
        <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 12 }}>Facebook Pages</div>
        {pages.length === 0 ? <div style={{ color: '#6b7280' }}>No pages found.</div> : pages.map((p: any, i: number) => (
          <div key={p.page_id || i} style={{ padding: '8px 0', borderTop: i ? '1px solid #f3f4f6' : 'none' }}>
            <div style={{ fontWeight: 600 }}>{p.name}</div>
            <div style={{ color: '#6b7280', fontSize: 12 }}>{p.category}{p.followers != null ? ` · ${p.followers.toLocaleString()} followers` : ''}</div>
          </div>
        ))}
      </div>
    );
  }
  if (result.block?.type === 'marketing_plan' || moduleId.includes('marketing.plan')) {
    const block = result.block || {};
    const channels: any[] = Array.isArray((block as any).recommended_channels) ? (block as any).recommended_channels : [];
    const focus: any[] = Array.isArray((block as any).focus) ? (block as any).focus : [];
    const title = (block as any).title || artifactTitle(run);
    return (
      <div style={{ padding: '16px 20px', fontSize: 13, color: '#1f2937', border: '1px solid #e5e7eb', borderRadius: 12, maxWidth: 520, background: '#fff' }}>
        <div style={{ color: '#6b7280', fontSize: 11, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 6 }}>Marketing plan</div>
        <div style={{ fontWeight: 800, fontSize: 16, marginBottom: 4 }}>{title}</div>
        {(block as any).campaign_theme && <div style={{ color: '#4b5563', marginBottom: 8 }}>{(block as any).campaign_theme}</div>}
        {focus.length > 0 && (
          <ol style={{ margin: '0 0 10px', paddingLeft: 18 }}>
            {focus.slice(0, 3).map((item: string, idx: number) => <li key={idx}>{item}</li>)}
          </ol>
        )}
        {channels.length > 0 && channels.slice(0, 3).map((ch: any, idx: number) => (
          <div key={idx} style={{ padding: '6px 0', borderTop: idx ? '1px solid #f3f4f6' : 'none' }}>
            <strong>{ch.channel || ch.name}</strong>{ch.status ? ` · ${ch.status}` : ''}
            {ch.role && <div style={{ color: '#4b5563' }}>{ch.role}</div>}
          </div>
        ))}
      </div>
    );
  }
  if (result.block?.type === 'image_asset' && (result.block as any).image_data_b64) {
    const b = result.block as any;
    const src = `data:${b.mime_type || 'image/png'};base64,${b.image_data_b64}`;
    return (
      <div style={{ textAlign: 'center', padding: '12px 0' }}>
        <img src={src} alt={b.prompt || 'Generated image'} style={{ maxWidth: '100%', borderRadius: 10, display: 'block', margin: '0 auto' }} />
        {b.prompt && <div style={{ color: '#888', fontSize: 11, marginTop: 6, fontStyle: 'italic' }}>{b.width && b.height ? `${b.width}×${b.height} · ` : ''}{b.prompt}</div>}
      </div>
    );
  }
  if (result.block?.type === 'image_asset' && (result.block as any).asset_omitted) {
    const b = result.block as any;
    return (
      <div style={{ padding: 16, textAlign: 'center', color: '#6b7280', fontSize: 13, border: '1px dashed #d1d5db', borderRadius: 10 }}>
        <div style={{ fontWeight: 700, color: '#374151', marginBottom: 4 }}>Image asset</div>
        {b.width && b.height && <div style={{ fontSize: 12, marginBottom: 4 }}>{b.width}×{b.height} · {b.mime_type || 'image/png'}</div>}
        {b.prompt && <div style={{ fontSize: 12, fontStyle: 'italic' }}>{b.prompt}</div>}
      </div>
    );
  }
  if (result.block?.type === 'image_asset' && (result.block as any).status === 'failed') {
    return (
      <div style={{ padding: 20, textAlign: 'center', color: '#ef4444', fontSize: 13 }}>
        <div style={{ fontSize: 20, marginBottom: 6 }}>⚠</div>
        <div>{(result.block as any).message || result.content}</div>
      </div>
    );
  }
  if (result.block?.type === 'clickup_task_status') {
    const b = result.block as any;
    const buckets = [
      { label: 'Blocked', count: (b.blocked || []).length, color: '#ef4444', bg: '#fef2f2' },
      { label: 'Overdue', count: (b.overdue || []).length, color: '#f97316', bg: '#fff7ed' },
      { label: 'In Progress', count: (b.in_progress || []).length, color: '#3b82f6', bg: '#eff6ff' },
      { label: 'To Do', count: b.todo_count || 0, color: '#6b7280', bg: '#f9fafb' },
      { label: 'Done', count: b.done_count || 0, color: '#16a34a', bg: '#f0fdf4' },
    ];
    return (
      <div style={{ padding: '14px 18px', fontSize: 13, color: '#1f2937', maxWidth: 520 }}>
        <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 10 }}>ClickUp · {b.space_count} space{b.space_count !== 1 ? 's' : ''} · {b.task_count} tasks</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {buckets.map(bk => (
            <div key={bk.label} style={{ background: bk.bg, border: `1px solid ${bk.color}22`, borderRadius: 6, padding: '4px 10px', display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ fontWeight: 700, color: bk.color }}>{bk.count}</span>
              <span style={{ color: '#374151', fontSize: 11 }}>{bk.label}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }
  if (result.block?.type === 'creative_shortform_video' || result.block?.type === 'video_asset') {
    const b = result.block as any;
    if (b.status !== 'succeeded') {
      return (
        <div style={{ padding: 16, textAlign: 'center', color: '#ef4444', fontSize: 13 }}>
          {b.message || result.content}
        </div>
      );
    }
    const filename = (b.video_path || '').split('/').pop();
    const videoSrc = filename ? `/api/media/video/${filename}` : b.video_url;
    return <FacebookFeedPreview pageName={brandName} adCopy={b.hook_text || ''} videoSrc={videoSrc} ctaText={b.cta_text || 'Learn More'} />;
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

function StreamDataCard({ update, brandName, objectiveTitle, onDismiss, onAskCMO, onInvestigate, onConfigure }: {
  update: StreamUpdateOut;
  brandName: string;
  objectiveTitle: string;
  onDismiss: (update: StreamUpdateOut) => void;
  onAskCMO: (update: StreamUpdateOut) => void;
  onInvestigate: (update: StreamUpdateOut) => void;
  onConfigure: (update: StreamUpdateOut) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [bodyOpen, setBodyOpen] = useState(false);
  const data = update.data_json || {};
  const evidence = asStringArray(data.primary_evidence || data.evidence);
  const hypotheses: any[] = Array.isArray(data.hypothesis_ranking) ? data.hypothesis_ranking : [];
  const doNot = asStringArray(data.do_not_list);
  const confidence = data.confidence || update.priority || 'Directional';
  const sourceState = data.source_state || update.source_key || timeAgo(update.created_at);
  const title = streamCardTitle(update);
  const cardObjective = String(data.objective_ref || data.objective || objectiveTitle || 'Active objective');
  const cardBrand = String(data.brand_name || data.brand || brandName);

  async function dismiss() {
    setBusy(true);
    onDismiss(update);
    try { await api.dismissStreamUpdate(update.id); } catch { } finally { setBusy(false); }
  }

  return (
    <article className={`g2card ${update.type === 'decision_brief' ? 'featured' : ''}`}>
      <div className="g2top">
        <span className={`g2type ${update.type}`}>{title}</span>
        <span className={`g2conf ${confidenceColor(confidence)}`}>{String(confidence)}</span>
      </div>
      <div className="g2obj">{cardObjective}</div>
      <div className="g2brand">{cardBrand}</div>
      <div className="g2src-row"><span className="g2src">{String(sourceState)}</span></div>
      <div className="g2why">{String(data.why_now || data.summary || 'BOS surfaced this for review.')}</div>
      {(evidence.length > 0 || hypotheses.length > 0 || doNot.length > 0 || data.recommended_next || data.approval_boundary) && (
        <>
          <button className="g2toggle" onClick={() => setBodyOpen(o => !o)}>
            {bodyOpen ? '▲ Hide details' : '▼ More details'}
          </button>
          {bodyOpen && (
            <div className="g2body">
              {evidence.length > 0 && <div className="g2ev">{evidence.map((item, idx) => <div className="g2ev-item" key={idx}>{item}</div>)}</div>}
              {hypotheses.length > 0 && <div className="g2ev">{hypotheses.slice(0, 3).map((h, idx) => <div className="g2ev-item" key={idx}>{h.hypothesis || JSON.stringify(h)}</div>)}</div>}
              {doNot.length > 0 && <div className="g2ev">{doNot.map((item, idx) => <div className="g2ev-item" key={idx}>Do not: {item}</div>)}</div>}
              {data.recommended_next && <div className="g2rec"><b>Next —</b>{String(data.recommended_next)}</div>}
              {data.approval_boundary && <div className="g2boundary">{String(data.approval_boundary)}</div>}
            </div>
          )}
        </>
      )}
      <div className="g2actions">
        {update.type === 'decision_brief' && (
          <button className="btn btn-accent" onClick={() => onInvestigate(update)}>Investigate</button>
        )}
        {update.type === 'setup_blocker' && (
          <button className="btn btn-accent" onClick={() => onConfigure(update)}>Configure</button>
        )}
        {update.type !== 'outcome' && (
          <button className="btn btn-ghost" onClick={() => onAskCMO(update)}>Ask CMO</button>
        )}
        <button className="btn btn-ghost" onClick={dismiss} disabled={busy}>{busy ? '…' : 'Dismiss'}</button>
      </div>
    </article>
  );
}

function StreamArtifactCard({ run, brandName, objectiveTitle, focused = false, registerCard, onApproved, onDismissed, onRevised }: {
  run: RunResponse;
  brandName: string;
  objectiveTitle: string;
  focused?: boolean;
  registerCard?: (runId: string, node: HTMLElement | null) => void;
  onApproved: (run: RunResponse) => void;
  onDismissed: (run: RunResponse) => void;
  onRevised: (original: RunResponse) => void;
}) {
  const [hydratedRun, setHydratedRun] = useState<RunResponse | null>(null);
  const [hydrating, setHydrating] = useState(false);
  const [hasEnteredView, setHasEnteredView] = useState(false);
  const cardRef = useRef<HTMLElement | null>(null);
  const status = artifactStatus(run);
  const displayRun = hydratedRun || run;
  const createdAt = new Date(run.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  const source = artifactPlatform(run) + ' · ' + createdAt + ' · ' + timeAgo(run.created_at);

  const setCardNode = useCallback((node: HTMLElement | null) => {
    cardRef.current = node;
    registerCard?.(run.run_id, node);
  }, [registerCard, run.run_id]);

  useEffect(() => {
    return () => registerCard?.(run.run_id, null);
  }, [registerCard, run.run_id]);

  useEffect(() => {
    const node = cardRef.current;
    if (!node || hasEnteredView) return;
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) {
        setHasEnteredView(true);
        observer.disconnect();
      }
    }, { rootMargin: '240px 0px' });
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasEnteredView]);

  useEffect(() => {
    if (!hasEnteredView || hydratedRun || hydrating) return;
    setHydrating(true);
    enqueueArtifactHydration(async () => {
      const fullRun = await api.getRun(run.run_id, { includeAssets: true }).catch(() => null);
      if (fullRun) {
        setHydratedRun({ ...fullRun, approval_status: run.approval_status, brand_id: fullRun.brand_id || run.brand_id } as RunResponse);
      }
      setHydrating(false);
    });
  }, [hasEnteredView, hydratedRun, hydrating, run]);

  return (
    <article className={`g2card${focused ? ' stream-focused-artifact' : ''}`} ref={setCardNode}>
      <div className="g2top">
        <span className="g2type pending_artifact">{artifactTitle(run)}</span>
        <span className={`g2conf ${status === 'approved' ? 'green' : 'amber'}`}>{statusText(status)}</span>
      </div>
      <div className="g2obj">{objectiveTitle || 'Active objective'}</div>
      <div className="g2brand">{brandName}</div>
      <div className="g2src-row"><span className="g2src">{source}</span></div>
      {hydrating && !hydratedRun ? (
        <div className="stream-artifact-fallback" style={{ marginTop: 10 }}><span className="spinner" /> Loading artifact…</div>
      ) : status === 'pending' ? (
        <ApprovalBundle
          run={displayRun}
          surfaceContext="panel"
          revisionHistory={[{ role: 'ai', text: displayRun.result?.content || '' }]}
          onApproved={onApproved}
          onDismissed={onDismissed}
          onRevision={(_, _revised) => onRevised(displayRun)}
        />
      ) : (
        <div className="stream-artifact-preview" style={{ marginTop: 10 }}>{renderNativePreview(displayRun)}</div>
      )}
    </article>
  );
}

function StreamUpdatePanel({ update, onClose }: { update: StreamUpdateOut; onClose: () => void }) {
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

const RUN_PAGE_SIZE = 20;

export function Stream({ embedded = false }: { embedded?: boolean } = {}) {
  const navigate = useNavigate();
  const { pendingRunItems, removePendingRun, activeBrand } = useUI();
  const [artifacts, setArtifacts] = useState<RunResponse[]>([]);
  const [streamUpdates, setStreamUpdates] = useState<StreamUpdateOut[]>([]);
  const [activeObjective, setActiveObjective] = useState<ObjectiveOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [panelItem, setPanelItem] = useState<StreamUpdateOut | null>(null);
  const [runOffset, setRunOffset] = useState(0);
  const [hasMoreRuns, setHasMoreRuns] = useState(true);
  const [loadingMoreRuns, setLoadingMoreRuns] = useState(false);
  const [focusedRunId, setFocusedRunId] = useState<string | null>(null);
  const knownRunIds = useRef(new Set<string>());
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const artifactCardRefs = useRef(new Map<string, HTMLElement>());

  const registerArtifactCard = useCallback((runId: string, node: HTMLElement | null) => {
    if (node) artifactCardRefs.current.set(runId, node);
    else artifactCardRefs.current.delete(runId);
  }, []);

  // When CMO chat references an artifact, focus the exact matching Stream card.
  // If it is outside the currently loaded page, fetch a lightweight preview and inject it.
  useEffect(() => {
    const upsertFocusedRun = (focusedRun: RunResponse) => {
      knownRunIds.current.add(focusedRun.run_id);
      setArtifacts(prev => {
        const exists = prev.some(r => r.run_id === focusedRun.run_id);
        if (!exists) return [focusedRun, ...prev];
        return prev.map(r => r.run_id === focusedRun.run_id ? ({ ...r, ...focusedRun } as RunResponse) : r);
      });
    };

    const handleFocusArtifact = (e: Event) => {
      const detail = (e as CustomEvent<Partial<RunResponse> & { artifact_id?: string }>).detail;
      const runId = detail?.run_id || detail?.artifact_id;
      if (!runId) return;
      setFocusedRunId(runId);
      if (detail.module_id) {
        upsertFocusedRun(detail as RunResponse);
        return;
      }
      api.getRun(runId, { includeAssets: false })
        .then(run => upsertFocusedRun(run))
        .catch(() => {});
    };
    window.addEventListener('bos:focus-artifact', handleFocusArtifact);
    return () => window.removeEventListener('bos:focus-artifact', handleFocusArtifact);
  }, []);

  useEffect(() => {
    if (!focusedRunId) return;
    const timer = window.setTimeout(() => {
      const node = artifactCardRefs.current.get(focusedRunId);
      if (node) {
        node.scrollIntoView({ behavior: 'smooth', block: 'center' });
        window.setTimeout(() => setFocusedRunId(current => current === focusedRunId ? null : current), 1800);
      }
    }, 80);
    return () => window.clearTimeout(timer);
  }, [focusedRunId, artifacts.length]);

  useEffect(() => {
    let cancelled = false;
    const brandId = activeBrand?.id;
    setLoading(true);
    Promise.all([
      api.getRuns({ limit: RUN_PAGE_SIZE, offset: 0, brand_id: brandId, include_preview: true }).then(r => {
        setRunOffset(r.runs.length);
        setHasMoreRuns(r.runs.length >= RUN_PAGE_SIZE && r.runs.length < r.total);
        const byId = new Map<string, RunResponse>();
        r.runs
          .filter(run => run.status !== 'failed' && run.approval_status !== 'rejected' && (!brandId || run.brand_id === brandId))
          .forEach(run => { if (!byId.has(run.run_id)) byId.set(run.run_id, runFromListItem(run)); });
        return Array.from(byId.values());
      }),
      api.refreshStream().catch(() => null).then(() => api.getStream(false).catch(() => ({ updates: [], total: 0 }))),
      api.getActiveObjective(brandId).catch(() => null),
    ])
      .then(([fullRuns, stream, objective]) => {
        if (!cancelled) {
          knownRunIds.current = new Set(fullRuns.map(r => r.run_id));
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

  const loadMoreRuns = useCallback(async () => {
    if (loadingMoreRuns || !hasMoreRuns) return;
    const brandId = activeBrand?.id;
    setLoadingMoreRuns(true);
    try {
      const r = await api.getRuns({ limit: RUN_PAGE_SIZE, offset: runOffset, brand_id: brandId, include_preview: true });
      setRunOffset(prev => prev + r.runs.length);
      setHasMoreRuns(r.runs.length >= RUN_PAGE_SIZE && runOffset + r.runs.length < r.total);
      const next = r.runs
        .filter(run =>
          run.status !== 'failed' &&
          run.approval_status !== 'rejected' &&
          (!brandId || run.brand_id === brandId) &&
          !knownRunIds.current.has(run.run_id)
        )
        .map(runFromListItem);
      if (next.length > 0) {
        next.forEach(run => knownRunIds.current.add(run.run_id));
        setArtifacts(prev => [...prev, ...next]);
      }
    } finally {
      setLoadingMoreRuns(false);
    }
  }, [activeBrand?.id, hasMoreRuns, loadingMoreRuns, runOffset]);

  useEffect(() => {
    const node = loadMoreRef.current;
    if (!node || !hasMoreRuns) return;
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) loadMoreRuns();
    }, { rootMargin: '600px 0px' });
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasMoreRuns, loadMoreRuns]);

  // Poll every 15 s for new runs — makes Stream a live TikTok-style feed.
  useEffect(() => {
    if (loading) return;
    const brandId = activeBrand?.id;

    const poll = async () => {
      try {
        const r = await api.getRuns({ limit: 10, brand_id: brandId, include_preview: true });
        const newCandidates = r.runs.filter(run =>
          run.status !== 'failed' &&
          run.approval_status !== 'rejected' &&
          (!brandId || run.brand_id === brandId) &&
          !knownRunIds.current.has(run.run_id)
        );
        if (newCandidates.length === 0) return;
        const byId = new Map<string, RunResponse>();
        newCandidates.map(runFromListItem).forEach(run => { if (!byId.has(run.run_id)) byId.set(run.run_id, run); });
        const valid = Array.from(byId.values()).filter((r): r is RunResponse => !!r && (!brandId || r.brand_id === brandId));
        if (valid.length > 0) {
          valid.forEach(r => knownRunIds.current.add(r.run_id));
          setArtifacts(prev => {
            const ids = new Set(prev.map(a => a.run_id));
            const fresh = valid.filter(r => !ids.has(r.run_id));
            return fresh.length > 0 ? [...fresh, ...prev] : prev;
          });
        }
      } catch {}
    };

    const timer = setInterval(poll, 15_000);
    return () => clearInterval(timer);
  }, [activeBrand?.id, loading]);

  const streamArtifacts = useMemo(() => {
    const brandId = activeBrand?.id;
    const apiIds = new Set(artifacts.map(r => r.run_id));
    const oneHourAgo = Date.now() - 60 * 60 * 1000;
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

  function configureFromCard(update: StreamUpdateOut) {
    const target = String(update.data_json?.config_target || 'objective-loop');
    if (target.includes('connector')) navigate('/admin/modules');
    else if (target.includes('gmail')) navigate('/admin/brands');
    else navigate('/admin/objective-loop');
  }

  if (loading) {
    return <div className="loading-full"><span className="spinner" /></div>;
  }

  const attentionCount = streamArtifacts.filter(run => artifactStatus(run) === 'pending').length + streamUpdates.length;
  const dateLabel = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
  const brandLabel = activeBrand?.name || 'All brands';
  const objectiveTitle = activeObjective?.summary || 'Active objective';

  return (
    <div className={`stream-fullscreen${embedded ? ' stream-embedded' : ''}`}>
      <div className={`stream-feed-col${panelItem ? ' stream-panel-open' : ''}`}>
        <div className="stream-content-inner">
          <div className="stream-header-zone">
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
              <div className="g2why">BOS is watching the active objective, Gmail replies, pending outcomes, and setup readiness.</div>
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
                  onAskCMO={() => navigate('/cmo')}
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
                  focused={focusedRunId === run.run_id}
                  registerCard={registerArtifactCard}
                  onApproved={r => updateLocalStatus(r, 'approved')}
                  onDismissed={r => updateLocalStatus(r, 'rejected')}
                  onRevised={original => setArtifacts(prev => prev.filter(r => r.run_id !== original.run_id))}
                />
              ))}
              {hasMoreRuns && <div ref={loadMoreRef} className="stream-load-more">{loadingMoreRuns ? 'Loading more…' : 'Scroll for more'}</div>}
            </div>
          )}
        </div>
      </div>

      {panelItem && <div className="stream-panel-backdrop" onClick={() => setPanelItem(null)} />}

      <div className={`stream-side-panel${panelItem ? ' stream-side-panel-open' : ''}`}>
        {panelItem && (
          <StreamUpdatePanel
            key={panelItem.id}
            update={panelItem}
            onClose={() => setPanelItem(null)}
          />
        )}
      </div>
    </div>
  );
}
