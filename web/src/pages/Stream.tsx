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
import { sanitizeArtifactPreviewText } from '../utils/artifacts';
import type { RunListItem, RunResponse, StreamUpdateOut } from '../api/types';

type ArtifactStatus = 'pending' | 'approved' | 'dismissed' | 'complete' | 'failed';

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
  const block = (run.result?.block || {}) as any;
  const blockTitle = String(block.display_title || block.title || '').trim();
  if (blockTitle) return blockTitle;
  if (id.includes('strategy_workflow')) return 'Strategy Workflow';
  if (id.includes('gtm_plan') || id.includes('gtm')) return 'GTM Strategy';
  if (id.includes('email') && id.includes('plan')) return 'Email Campaign Plan';
  if (id.includes('email')) return 'Email Draft';
  if (id.includes('gbp') || platform.toLowerCase().includes('google business')) return 'Google Business Profile Audit';
  if (id.includes('plan')) return 'Campaign Plan';
  if (id.includes('meta.pages.insights.report')) return 'Meta Insight Report';
  if (id.includes('report') || id.includes('analytics')) return 'Marketing Report';
  if (id.includes('video.edit')) {
    const b = run.result?.block as any;
    return b?.source_run_id ? 'Video Edit · Revision' : 'Video Edit · Cut 1';
  }
  if (id.includes('shortform.video')) return 'Shortform Video · Cut 1';
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


function artifactStatus(run: RunResponse): ArtifactStatus {
  const block = run.result?.block as any;
  const status = (run as any).approval_status || (run.result as any)?.approval_status;
  if (run.status === 'failed' || block?.status === 'failed') return 'failed';
  // Staged text/draft artifacts are approval-to-render workflow items. Older
  // runs may have been marked approved by the generic approve endpoint without
  // executing their declared render action; keep them actionable in Stream.
  if ((block?.type === 'postcraft_draft' || block?.type === 'storyboard_json') && block?.action_modules?.render) return 'pending';
  if (status === 'approved') return 'approved';
  if (status === 'dismissed') return 'dismissed';
  if (status === 'rejected' || status === 'revised' || status === 'pending') return 'pending';
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
    brand_name: item.brand_name,
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

function streamRunRank(run: RunResponse): number {
  const status = artifactStatus(run);
  if (status === 'pending') return 0;
  if (status === 'failed') return 1;
  if (status === 'complete') return 3;
  if (status === 'approved') return 4;
  return 5;
}

function sortStreamRuns(runs: RunResponse[]): RunResponse[] {
  return [...runs].sort((a, b) => {
    // Stream is a feed: newest generated artifact belongs at the top.
    // Status still breaks exact timestamp ties, but must not push a new
    // generated/failed artifact below older pending work.
    const timeDelta = runTimestamp(b) - runTimestamp(a);
    return timeDelta || (streamRunRank(a) - streamRunRank(b));
  });
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
  if (status === 'dismissed') return 'Deleted';
  if (status === 'failed') return 'Failed';
  if (status === 'pending') return 'Needs approval';
  return 'Saved';
}

function artifactBrandName(run: RunResponse, fallback: string): string {
  return run.result?.block?.brand_name || run.result?.brand_name || run.brand_name || fallback;
}

function localVideoSrcFromBlock(block: any): string | undefined {
  const url = String(block?.video_proxy_url || '').trim();
  return url || undefined;
}

function DriveVideoPreview({ title, webViewLink }: { title?: string; webViewLink?: string }) {
  return (
    <div style={{ width: '100%', maxWidth: 540, border: '1px solid #e5e7eb', borderRadius: 12, overflow: 'hidden', background: '#fff' }}>
      <div style={{ padding: '18px 16px', textAlign: 'center', color: '#4b5563' }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: '#111827', marginBottom: 4 }}>{title || 'Drive video'}</div>
        <div style={{ fontSize: 12 }}>Preview this video from the artifact detail panel or open it in Drive.</div>
      </div>
      {webViewLink && (
        <div style={{ padding: '8px 10px', background: '#fff', textAlign: 'right', borderTop: '1px solid #e5e7eb' }}>
          <a href={webViewLink} target="_blank" rel="noreferrer" style={{ color: '#2563eb', fontSize: 12, fontWeight: 700 }}>Open video in Drive →</a>
        </div>
      )}
    </div>
  );
}

function StrategyWorkflowStreamCard({ block, onOpen }: { block: any; onOpen: () => void }) {
  const archetype = (block.archetype || 'direct_sales').replace(/_/g, ' ');
  const thesis = (block.components || []).find((c: any) => c.type === 'strategic_thesis')?.data || {};
  const wedge = thesis.wedge || block.wedge || '';
  const motion = thesis.primary_motion || block.primary_motion || '';
  const componentCount = (block.components || []).filter((c: any) => c.status === 'complete').length;
  const workOrders = (block.components || []).find((c: any) => c.type === 'work_orders');
  const briefCount = workOrders?.data?.briefs?.length || 0;

  return (
    <div style={{ marginTop: 12, border: '1px solid #e5dccb', borderRadius: 12, overflow: 'hidden', background: '#fffdf8' }}>
      <div style={{ background: '#0B3D2E', color: '#d8c9a8', padding: '10px 14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 11, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.1em' }}>Strategy Workflow · {archetype}</span>
        {motion && <span style={{ fontSize: 11, background: '#1a5c42', borderRadius: 6, padding: '2px 8px', fontWeight: 700 }}>{motion}</span>}
      </div>
      <div style={{ padding: '12px 14px' }}>
        {wedge && <div style={{ fontSize: 13, lineHeight: 1.5, color: '#374151', fontStyle: 'italic', marginBottom: 10 }}>"{wedge}"</div>}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          {componentCount > 0 && <span style={{ fontSize: 11, background: '#dcfce7', color: '#166534', borderRadius: 999, padding: '2px 8px', fontWeight: 700 }}>{componentCount} components active</span>}
          {briefCount > 0 && <span style={{ fontSize: 11, background: '#f0eadc', color: '#826D40', borderRadius: 999, padding: '2px 8px', fontWeight: 700 }}>{briefCount} work orders</span>}
        </div>
        <button
          onClick={onOpen}
          style={{ background: '#0B3D2E', color: '#fff', border: 0, borderRadius: 8, padding: '8px 14px', fontSize: 12, fontWeight: 850, cursor: 'pointer', width: '100%' }}
        >
          Open Strategy Workflow →
        </button>
      </div>
    </div>
  );
}

function renderNativePreview(run: RunResponse) {
  const result = run.result;
  if (!result) return <div className="stream-artifact-fallback">No artifact content available.</div>;

  const moduleId = run.module_id.toLowerCase();
  const channel = `${moduleId} ${(result.platform || '').toLowerCase()}`;
  const brandName = result.block?.brand_name || result.brand_name || run.brand_name || 'Unknown brand';
  const socialHandle = result.block?.brand_handle || result.brand_handle || '@brand';

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
  if (result.block?.type === 'storyboard_json' || moduleId.includes('storyboard.create')) {
    const b = (result.block || {}) as any;
    const raw = b.storyboard_text || b.body_markdown || b.message || result.content || 'Storyboard text unavailable.';
    const text = String(raw).split('\n---\nReview/revise')[0].split('\n---\nRender was held')[0].trim();
    const isBlueprint = b.artifact_kind === 'video_production_blueprint';
    const reviewNote = isBlueprint ? (b.review_note || '15-second hard cap: full story arc + CTA must fit within 15 seconds max.') : '';
    return (
      <div style={{ padding: '14px 16px', fontSize: 13, color: '#1f2937', border: '1px solid #e5e7eb', borderRadius: 12, background: '#fff', maxHeight: 360, overflow: 'auto' }}>
        <div style={{ fontSize: 11, color: '#6b7280', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 8 }}>{isBlueprint ? 'Video production blueprint' : 'Storyboard draft'}</div>
        {reviewNote && <div style={{ marginBottom: 10, padding: '8px 10px', borderRadius: 8, background: '#fff7ed', color: '#9a3412', fontSize: 12, fontWeight: 600 }}>{reviewNote}</div>}
        <pre style={{ margin: 0, whiteSpace: 'pre-wrap', lineHeight: 1.45, fontFamily: 'inherit' }}>{text}</pre>
      </div>
    );
  }
  if (result.block?.type === 'creative_post_asset' && result.block?.status === 'succeeded') {
    const b = result.block as any;
    const imageUrl = b.image_data_b64 ? `data:${b.mime_type || 'image/png'};base64,${b.image_data_b64}` : undefined;
    return <FacebookFeedPreview pageName={brandName} adCopy={b.caption || b.message || 'Caption pending — review to add copy'} imageUrl={imageUrl} ctaText="" />;
  }
  if (result.block?.type === 'imprint_asset' && result.block?.status === 'succeeded') {
    const b = result.block as any;
    const src = b.image_data_b64 ? `data:${b.mime_type || 'image/png'};base64,${b.image_data_b64}` : null;
    return (
      <div style={{ maxWidth: 420, border: '1px solid #e5e7eb', borderRadius: 12, background: '#fff', overflow: 'hidden' }}>
        {src ? (
          <img src={src} alt={b.headline || 'Generated image'} style={{ width: '100%', display: 'block' }} />
        ) : (
          <div style={{ minHeight: 220, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 13 }}>
            {b.asset_omitted ? 'Loading full image…' : 'Image preview unavailable'}
          </div>
        )}
        {(b.headline || b.subheadline || b.body || b.cta_text || b.drive_web_view_link) && (
          <div style={{ padding: '14px 16px', lineHeight: 1.4 }}>
            {b.headline && <div style={{ fontSize: 17, fontWeight: 800, color: '#111827', marginBottom: 4 }}>{b.headline}</div>}
            {b.subheadline && <div style={{ fontSize: 13, color: '#4b5563', marginBottom: 6 }}>{b.subheadline}</div>}
            {b.body && <div style={{ fontSize: 13, color: '#374151', marginBottom: 10 }}>{b.body}</div>}
            {b.cta_text && <div style={{ display: 'inline-block', padding: '6px 14px', background: '#111827', color: '#fff', borderRadius: 6, fontSize: 12, fontWeight: 700 }}>{b.cta_text}</div>}
            {b.drive_web_view_link && <div style={{ marginTop: 10 }}><a href={b.drive_web_view_link} target="_blank" rel="noreferrer" style={{ color: '#2563eb', fontSize: 12, fontWeight: 700 }}>Open in Drive →</a></div>}
          </div>
        )}
      </div>
    );
  }
  if (result.block?.type === 'meta_page_insights_report') {
    const b = result.block as any;
    const page = b.page || {};
    const insights: any[] = b.insights || [];
    const scheduledPosts: any[] = b.scheduled_posts || [];
    const recentPosts: any[] = b.recent_posts || [];
    const warnings: any[] = b.warnings || [];
    const metrics = b.metrics_overview || {};
    const insightBullets: any[] = b.insight_bullets || [];
    const notAvailable: string[] = b.not_available || [];
    const coverageLabel = String(b.coverage_label || (warnings.length ? 'partial' : 'reported'));
    return (
      <div style={{ padding: '16px 20px', fontSize: 13, color: '#1f2937', maxWidth: 680, border: '1px solid #dbeafe', borderRadius: 12, background: '#eff6ff' }}>
        <div style={{ color: '#1d4ed8', fontSize: 11, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 6 }}>Read-only Meta insight artifact · {coverageLabel}</div>
        <div style={{ fontWeight: 800, fontSize: 16, marginBottom: 4 }}>{page.name || brandName}</div>
        <div style={{ color: '#6b7280', fontSize: 12, marginBottom: 12 }}>
          {page.category || 'Facebook Page'}{page.followers != null ? ` · ${Number(page.followers).toLocaleString()} followers` : ''}{b.report_scope ? ` · ${String(b.report_scope).replace(/_/g, ' ')}` : ''}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 8, marginBottom: 12 }}>
          <div style={{ background: '#fff', border: '1px solid #bfdbfe', borderRadius: 8, padding: 10 }}><div style={{ color: '#6b7280', fontSize: 11 }}>Scheduled</div><div style={{ fontWeight: 800 }}>{metrics.scheduled_posts ?? scheduledPosts.length}</div></div>
          <div style={{ background: '#fff', border: '1px solid #bfdbfe', borderRadius: 8, padding: 10 }}><div style={{ color: '#6b7280', fontSize: 11 }}>Recent posts</div><div style={{ fontWeight: 800 }}>{metrics.recent_posts ?? recentPosts.length}</div></div>
          <div style={{ background: '#fff', border: '1px solid #bfdbfe', borderRadius: 8, padding: 10 }}><div style={{ color: '#6b7280', fontSize: 11 }}>Metrics</div><div style={{ fontWeight: 800 }}>{metrics.insight_metrics_reported ?? insights.length}</div></div>
          <div style={{ background: '#fff', border: '1px solid #bfdbfe', borderRadius: 8, padding: 10 }}><div style={{ color: '#6b7280', fontSize: 11 }}>Engagement rows</div><div style={{ fontWeight: 800 }}>{metrics.recent_posts_with_engagement_counts ?? 0}</div></div>
        </div>
        {insightBullets.length > 0 && <div style={{ background: '#fff', border: '1px solid #bfdbfe', borderRadius: 10, padding: 12, marginBottom: 10 }}>
          <div style={{ fontWeight: 800, marginBottom: 6 }}>{b.insight_heading || 'Campaign insights'}</div>
          <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.45 }}>
            {insightBullets.slice(0, 4).map((item: any, i: number) => <li key={i} style={{ marginBottom: 6 }}><strong>{item.insight}</strong>{item.why_it_matters ? <span style={{ color: '#4b5563' }}> — {item.why_it_matters}</span> : null}<div style={{ color: '#6b7280', fontSize: 11 }}>{item.confidence || 'unknown'} confidence · {item.coverage || 'coverage unknown'}</div></li>)}
          </ul>
        </div>}
        {notAvailable.length > 0 && <div style={{ color: '#92400e', fontSize: 12, marginBottom: 8 }}>Not available yet: {notAvailable.slice(0, 3).join(' · ')}</div>}
        {b.recommended_next_step && <div style={{ fontWeight: 700 }}>Next: {b.recommended_next_step}</div>}
        {warnings.length > 0 && <div style={{ color: '#92400e', fontSize: 12, marginTop: 8 }}>Coverage partial: {warnings[0]?.scope || 'Meta'} permission limits detected.</div>}
      </div>
    );
  }
  if (result.block?.type === 'fb_page_post_draft') {
    return <FacebookFeedPreview pageName={result.block.page_name || brandName} adCopy={result.block.message || result.content || 'Post text missing'} ctaText="" />;
  }
  if (result.block?.type === 'fb_page_post_result') {
    const b = result.block as any;
    const scheduled = b.status === 'scheduled';
    const succeeded = b.status === 'succeeded' || scheduled;
    const previewText = sanitizeArtifactPreviewText(b.message_preview || b.message || '');
    return (
      <div style={{ padding: '14px 16px', fontSize: 13, color: '#1f2937', border: `1px solid ${succeeded ? '#bbf7d0' : '#fca5a5'}`, borderRadius: 8, background: succeeded ? '#f0fdf4' : '#fef2f2' }}>
        <div style={{ fontWeight: 700, marginBottom: 4 }}>{scheduled ? 'Facebook post scheduled' : (succeeded ? 'Published to Facebook' : 'Facebook publish failed')}</div>
        {previewText && <div style={{ color: '#4b5563', marginBottom: 6, lineHeight: 1.4 }}>{previewText.slice(0, 120)}{previewText.length > 120 ? '…' : ''}</div>}
        {scheduled && b.scheduled_at && <div style={{ color: '#166534', fontSize: 11, marginBottom: 4 }}>Scheduled for: {b.scheduled_at}</div>}
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
  if (result.block?.type === 'gbp_completeness_result') {
    const b = result.block as any;
    if (b.status === 'failed' || b.error) {
      return (
        <div style={{ padding: '18px 20px', fontSize: 13, color: '#7f1d1d', border: '1px solid #fecaca', borderRadius: 12, background: '#fef2f2' }}>
          <div style={{ fontWeight: 800, marginBottom: 4 }}>Google Business Profile not connected</div>
          <div>{b.error || result.content || 'Connect Google Business Profile in Admin → Brands.'}</div>
        </div>
      );
    }
    const fields: any[] = Array.isArray(b.fields) ? b.fields : [];
    return (
      <div style={{ padding: '16px 20px', fontSize: 13, color: '#1f2937', border: '1px solid #dbeafe', borderRadius: 12, background: '#eff6ff', maxWidth: 560 }}>
        <div style={{ fontSize: 11, color: '#1d4ed8', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 6 }}>Google Business Profile audit</div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 8 }}>
          <span style={{ fontSize: 30, fontWeight: 900 }}>{b.score ?? 0}</span>
          <span style={{ fontWeight: 800 }}>{b.rating || 'Unscored'}</span>
          {b.raw_score != null && <span style={{ color: '#6b7280' }}>{b.raw_score}/{b.max_score || 16} pts</span>}
        </div>
        {fields.slice(0, 4).map((field, idx) => (
          <div key={idx} style={{ padding: '6px 0', borderTop: idx ? '1px solid #bfdbfe' : 'none' }}>
            <strong>{field.name}</strong> · {field.status}
            {field.note && <div style={{ color: '#4b5563', fontSize: 12 }}>{field.note}</div>}
          </div>
        ))}
      </div>
    );
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
  if (result.block?.type === 'strategy_workflow') {
    const block = result.block as any;
    const thesis = (block.components || []).find((c: any) => c.type === 'strategic_thesis')?.data || {};
    const wedge = thesis.wedge || block.wedge || '';
    const motion = thesis.primary_motion || block.primary_motion || '';
    const archetype = (block.archetype || '').replace(/_/g, ' ');
    return (
      <div style={{ padding: '14px 16px', fontSize: 13, color: '#1f2937', border: '1px solid #e5dccb', borderRadius: 12, background: '#fffdf8' }}>
        <div style={{ fontSize: 11, color: '#826D40', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 6 }}>Strategy Workflow{archetype ? ` · ${archetype}` : ''}</div>
        {motion && <div style={{ fontWeight: 700, marginBottom: 6 }}>{motion} motion</div>}
        {wedge && <div style={{ color: '#4b5563', lineHeight: 1.45, fontStyle: 'italic' }}>"{wedge}"</div>}
      </div>
    );
  }
  if (result.block?.type === 'gtm_strategy') {
    const block = result.block as any;
    const stack = block.channel_stack || {};
    const doNow: any[] = Array.isArray(stack.do_now) ? stack.do_now : [];
    const gaps: any[] = Array.isArray(block.critical_gaps) ? block.critical_gaps : [];
    return (
      <div style={{ padding: '16px 20px', fontSize: 13, color: '#1f2937', border: '1px solid #e5e7eb', borderRadius: 12, maxWidth: 560, background: '#fff' }}>
        <div style={{ color: '#6b7280', fontSize: 11, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 6 }}>GTM strategy</div>
        <div style={{ fontWeight: 800, fontSize: 16, marginBottom: 8 }}>{block.title || artifactTitle(run)}</div>
        {block.best_current_motion && <div style={{ lineHeight: 1.45, marginBottom: 10 }}><strong>Motion:</strong> {block.best_current_motion}</div>}
        {block.positioning_angle && <div style={{ color: '#4b5563', marginBottom: 10 }}>{block.positioning_angle}</div>}
        {doNow.length > 0 && (
          <div style={{ marginBottom: 10 }}>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Do now</div>
            {doNow.slice(0, 3).map((ch: any, idx: number) => (
              <div key={idx} style={{ color: '#4b5563' }}>• {ch.channel || ch.name}{ch.role ? ` — ${ch.role}` : ''}</div>
            ))}
          </div>
        )}
        {gaps.length > 0 && (
          <div>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Critical gaps</div>
            {gaps.slice(0, 2).map((gap: any, idx: number) => (
              <div key={idx} style={{ color: '#4b5563' }}>• {gap.gap || gap.name}{gap.unlocks ? ` — ${gap.unlocks}` : ''}</div>
            ))}
          </div>
        )}
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
        <img src={src} alt={b.title || b.headline || 'Generated image'} style={{ maxWidth: '100%', borderRadius: 10, display: 'block', margin: '0 auto' }} />
      </div>
    );
  }
  if (result.block?.type === 'image_asset' && (result.block as any).asset_omitted) {
    const b = result.block as any;
    return (
      <div style={{ padding: 16, textAlign: 'center', color: '#6b7280', fontSize: 13, border: '1px dashed #d1d5db', borderRadius: 10 }}>
        <div style={{ fontWeight: 700, color: '#374151', marginBottom: 4 }}>Image asset</div>
        {b.width && b.height && <div style={{ fontSize: 12, marginBottom: 4 }}>{b.width}×{b.height} · {b.mime_type || 'image/png'}</div>}
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
  if (result.block?.type === 'post_image') {
    const b = result.block as any;
    const src = b.image_data_b64 ? `data:${b.mime_type || 'image/png'};base64,${b.image_data_b64}` : null;
    return (
      <div style={{ maxWidth: 540, border: '1px solid #e5e7eb', borderRadius: 12, background: '#fff', overflow: 'hidden' }}>
        {src ? (
          <img src={src} alt={b.headline || 'Post image'} style={{ width: '100%', display: 'block' }} />
        ) : (
          <div style={{ minHeight: 220, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 13 }}>Image preview unavailable</div>
        )}
        {(b.headline || b.subheadline || b.body_copy || b.cta_text || b.drive_web_view_link) && (
          <div style={{ padding: '14px 16px', lineHeight: 1.4 }}>
            {b.headline && <div style={{ fontSize: 17, fontWeight: 800, color: '#111827', marginBottom: 4 }}>{b.headline}</div>}
            {b.subheadline && <div style={{ fontSize: 13, color: '#4b5563', marginBottom: 6 }}>{b.subheadline}</div>}
            {b.body_copy && <div style={{ fontSize: 13, color: '#374151', marginBottom: 10 }}>{b.body_copy}</div>}
            {b.cta_text && <div style={{ display: 'inline-block', padding: '6px 14px', background: '#111827', color: '#fff', borderRadius: 6, fontSize: 12, fontWeight: 700 }}>{b.cta_text}</div>}
            {b.drive_web_view_link && <div style={{ marginTop: 10 }}><a href={b.drive_web_view_link} target="_blank" rel="noreferrer" style={{ color: '#2563eb', fontSize: 12, fontWeight: 700 }}>Open in Drive →</a></div>}
          </div>
        )}
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
    const videoSrc = localVideoSrcFromBlock(b);
    const isRevision = (run.module_id || '').toLowerCase().includes('video.edit') && Boolean(b.source_run_id);
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {isRevision && (b.change_summary || b.source_run_id) && (
          <div style={{ padding: '8px 12px', background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 7, fontSize: 12 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: '#0369a1', textTransform: 'uppercase', letterSpacing: '.1em', marginBottom: 3 }}>
              Change
            </div>
            {b.change_summary && <div style={{ color: '#1e40af', lineHeight: 1.35 }}>{b.change_summary}</div>}
            {b.source_run_id && (
              <button
                onClick={e => { e.stopPropagation(); window.dispatchEvent(new CustomEvent('bos:focus-artifact', { detail: { run_id: b.source_run_id } })); }}
                style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', marginTop: 4, color: '#2563eb', fontSize: 10, textDecoration: 'underline', display: 'block', textAlign: 'left' }}
              >
                ← View source cut
              </button>
            )}
          </div>
        )}
        {videoSrc ? (
          <FacebookFeedPreview pageName={brandName} adCopy={b.hook_text || ''} videoSrc={videoSrc} ctaText={b.cta_text || 'Learn More'} />
        ) : (
          <DriveVideoPreview title={b.drive_file_name || 'Drive video'} webViewLink={b.drive_web_view_link} />
        )}
      </div>
    );
  }
  return <div className="stream-artifact-fallback">{result.content || 'Artifact content unavailable.'}</div>;
}

function streamCardTitle(update: StreamUpdateOut): string {
  if (update.type === 'decision_brief') return 'Decision Brief';
  if (update.type === 'outcome') return 'Outcome · Memory Updated';
  if (update.type === 'setup_blocker') return 'Setup Blocker';
  if (update.type === 'pending_artifact') return 'Pending Artifact';
  if (update.type === 'alert') return 'Alert';
  if (update.type === 'recommendation') return 'Recommendation';
  return titleCase(update.type || 'Stream Card');
}

function buildCmoPrefill(update: StreamUpdateOut): string {
  const data = update.data_json || {};
  const title = streamCardTitle(update);
  const summary = data.why_now || data.summary || data.body || data.headline || data.recommended_next || 'Review this stream card.';
  const evidence = asStringArray(data.primary_evidence || data.evidence).slice(0, 3);
  const lines = [
    `Help me act on this ${title.toLowerCase()}.`,
    `Card: ${title}`,
    data.brand_name || data.brand ? `Brand: ${String(data.brand_name || data.brand)}` : null,
    data.objective_ref || data.objective ? `Goal: ${String(data.objective_ref || data.objective)}` : null,
    `Context: ${String(summary)}`,
    evidence.length ? `Evidence: ${evidence.join(' | ')}` : null,
    update.source_key ? `Source: ${update.source_key}` : null,
  ].filter(Boolean);
  return lines.join('\n');
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

function StreamDataCard({ update, brandName, objectiveTitle, onDelete, onAskCMO, onInvestigate, onConfigure }: {
  update: StreamUpdateOut;
  brandName: string;
  objectiveTitle: string;
  onDelete: (update: StreamUpdateOut) => void;
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
  const cardObjective = String(data.objective_ref || data.objective || objectiveTitle || 'Current operations');
  const cardBrand = String(data.brand_name || data.brand || brandName);

  async function deleteUpdate() {
    if (!window.confirm('Delete this Stream card? This cannot be undone.')) return;
    setBusy(true);
    onDelete(update);
    try { await api.deleteStreamUpdate(update.id); } catch { } finally { setBusy(false); }
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
      <div className="g2why">{String(data.why_now || data.summary || data.body || data.headline || 'BOS surfaced this for review.')}</div>
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
          <button className="btn btn-secondary" onClick={() => onConfigure(update)}>Configure</button>
        )}
        {update.type !== 'outcome' && (
          <button className="btn btn-ghost" onClick={() => onAskCMO(update)}>Ask CMO</button>
        )}
        <button type="button" className="btn btn-ghost" onClick={deleteUpdate} disabled={busy}>{busy ? '…' : 'Delete'}</button>
      </div>
    </article>
  );
}

function StreamArtifactCard({ run, brandName, objectiveTitle, focused = false, registerCard, onApproved, onDeleted, onRevised }: {
  run: RunResponse;
  brandName: string;
  objectiveTitle: string;
  focused?: boolean;
  registerCard?: (runId: string, node: HTMLElement | null) => void;
  onApproved: (run: RunResponse) => void;
  onDeleted: (run: RunResponse) => void;
  onRevised: (original: RunResponse) => void;
}) {
  const [hydratedRun, setHydratedRun] = useState<RunResponse | null>(null);
  const [hydrating, setHydrating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [hasEnteredView, setHasEnteredView] = useState(false);
  const cardRef = useRef<HTMLElement | null>(null);
  const navigate = useNavigate();
  const displayRun = hydratedRun || run;
  const status = artifactStatus(displayRun);
  const displayBrandName = artifactBrandName(displayRun, brandName);

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
        setHydratedRun({
          ...fullRun,
          approval_status: fullRun.approval_status || run.approval_status,
          brand_id: fullRun.brand_id || run.brand_id,
          brand_name: fullRun.brand_name || run.brand_name,
        } as RunResponse);
      }
      setHydrating(false);
    });
  }, [hasEnteredView, hydratedRun, hydrating, run]);

  async function deleteArtifact() {
    if (!window.confirm('Delete this artifact permanently? This cannot be undone.')) return;
    setDeleting(true);
    onDeleted(displayRun);
    try {
      await api.deleteRun(displayRun.run_id);
    } catch {
      setDeleting(false);
    }
  }

  return (
    <article className={`g2card${focused ? ' stream-focused-artifact' : ''}`} ref={setCardNode}>
      <div className="g2top">
        <span className="g2type pending_artifact">{artifactTitle(displayRun)}</span>
        <span className={`g2conf ${status === 'approved' ? 'green' : 'amber'}`}>{statusText(status)}</span>
      </div>
      <div className="g2obj">{objectiveTitle || 'Current operations'}</div>
      <div className="g2brand">{displayBrandName}</div>
      {hydrating && !hydratedRun ? (
        <div className="stream-artifact-fallback" style={{ marginTop: 10 }}><span className="spinner" /> Loading artifact…</div>
      ) : displayRun.result?.block?.type === 'strategy_workflow' ? (
        <>
          <StrategyWorkflowStreamCard block={displayRun.result.block as any} onOpen={() => {
            const url = (displayRun.result?.block as any)?.workflow_url;
            if (url) navigate(url);
          }} />
          {status !== 'dismissed' && (
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10 }}>
              <button type="button" className="btn btn-ghost" onClick={deleteArtifact} disabled={deleting}>{deleting ? 'Deleting…' : 'Delete'}</button>
            </div>
          )}
        </>
      ) : status === 'pending' || status === 'failed' ? (
        <ApprovalBundle
          run={displayRun}
          surfaceContext="panel"
          revisionHistory={[{ role: 'ai', text: displayRun.result?.content || '' }]}
          onApproved={onApproved}
          onDeleted={onDeleted}
          onRevision={(_, _revised) => onRevised(displayRun)}
        />
      ) : (
        <div className="stream-artifact-preview" style={{ marginTop: 10 }}>
          {renderNativePreview(displayRun)}
          {status !== 'dismissed' && (
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10 }}>
              <button type="button" className="btn btn-ghost" onClick={deleteArtifact} disabled={deleting}>{deleting ? 'Deleting…' : 'Delete'}</button>
            </div>
          )}
        </div>
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
const DELETED_ARTIFACTS_KEY = 'bos_deleted_artifact_ids';

function readDeletedArtifactIds(): Set<string> {
  try {
    const current = JSON.parse(localStorage.getItem(DELETED_ARTIFACTS_KEY) || '[]');
    const legacy = JSON.parse(localStorage.getItem('bos_dismissed_artifact_ids') || '[]');
    return new Set([...current, ...legacy].filter(id => typeof id === 'string'));
  } catch {
    return new Set();
  }
}

function writeDeletedArtifactIds(ids: Set<string>): void {
  try {
    localStorage.setItem(DELETED_ARTIFACTS_KEY, JSON.stringify(Array.from(ids).slice(-500)));
  } catch {}
}

export function Stream({ embedded = false }: { embedded?: boolean } = {}) {
  const navigate = useNavigate();
  const { pendingRunItems, removePendingRun, activeBrand } = useUI();
  const [artifacts, setArtifacts] = useState<RunResponse[]>([]);
  const [streamUpdates, setStreamUpdates] = useState<StreamUpdateOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [panelItem, setPanelItem] = useState<StreamUpdateOut | null>(null);
  const [runOffset, setRunOffset] = useState(0);
  const [totalArtifacts, setTotalArtifacts] = useState(0);
  const [hasMoreRuns, setHasMoreRuns] = useState(true);
  const [loadingMoreRuns, setLoadingMoreRuns] = useState(false);
  const [focusedRunId, setFocusedRunId] = useState<string | null>(null);
  const [deletedArtifactIds, setDeletedArtifactIds] = useState<Set<string>>(() => readDeletedArtifactIds());
  const deletedArtifactIdsRef = useRef(deletedArtifactIds);
  const knownRunIds = useRef(new Set<string>());
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const feedColRef = useRef<HTMLDivElement | null>(null);
  const artifactCardRefs = useRef(new Map<string, HTMLElement>());

  useEffect(() => {
    deletedArtifactIdsRef.current = deletedArtifactIds;
  }, [deletedArtifactIds]);

  const registerArtifactCard = useCallback((runId: string, node: HTMLElement | null) => {
    if (node) artifactCardRefs.current.set(runId, node);
    else artifactCardRefs.current.delete(runId);
  }, []);

  // When CMO chat references an artifact, focus the exact matching Stream card.
  // If it is outside the currently loaded page, fetch a lightweight preview and inject it.
  useEffect(() => {
    const upsertFocusedRun = (focusedRun: RunResponse) => {
      if (deletedArtifactIdsRef.current.has(focusedRun.run_id) || focusedRun.approval_status === 'dismissed') return;
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
      api.getRun(runId, { includeAssets: true })
        .then(run => upsertFocusedRun(run))
        .catch(() => {});
    };
    window.addEventListener('bos:focus-artifact', handleFocusArtifact);
    const params = new URLSearchParams(window.location.search);
    const initialRunId = params.get('artifact') || params.get('run_id');
    let timer: number | null = null;
    if (initialRunId) {
      timer = window.setTimeout(() => {
        handleFocusArtifact(new CustomEvent('bos:focus-artifact', { detail: { run_id: initialRunId } }));
      }, 600);
    }
    return () => {
      window.removeEventListener('bos:focus-artifact', handleFocusArtifact);
      if (timer) window.clearTimeout(timer);
    };
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
      Promise.all([
        api.getRuns({ limit: RUN_PAGE_SIZE, offset: 0, brand_id: brandId, exclude_approval_status: 'dismissed', include_preview: true }),
        api.getRuns({ limit: 100, offset: 0, brand_id: brandId, approval_status: 'pending', include_preview: true }),
        api.getRuns({ limit: 100, offset: 0, brand_id: brandId, approval_status: 'failed', include_preview: true }),
      ]).then(([recent, pending, failed]) => {
        setRunOffset(recent.runs.length);
        setTotalArtifacts(recent.total);
        setHasMoreRuns(recent.runs.length >= RUN_PAGE_SIZE && recent.runs.length < recent.total);
        const byId = new Map<string, RunResponse>();
        [...pending.runs, ...failed.runs, ...recent.runs]
          .filter(run => run.approval_status !== 'dismissed' && !deletedArtifactIdsRef.current.has(run.run_id) && (!brandId || run.brand_id === brandId))
          .forEach(run => { if (!byId.has(run.run_id)) byId.set(run.run_id, runFromListItem(run)); });
        return sortStreamRuns(Array.from(byId.values()));
      }),
      api.refreshStream().catch(() => null).then(() => api.getStream(false).catch(() => ({ updates: [], total: 0 }))),
    ])
      .then(([fullRuns, stream]) => {
        if (!cancelled) {
          knownRunIds.current = new Set(fullRuns.map(r => r.run_id));
          setArtifacts(fullRuns);
          setStreamUpdates((stream.updates || []).filter(update => {
            const ref = updateBrandRef(update);
            return ['outcome', 'decision_brief', 'setup_blocker', 'pending_artifact', 'alert', 'recommendation'].includes(update.type) &&
              (!brandId || !ref || ref === brandId);
          }));
        }
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [activeBrand?.id]);

  const loadMoreRuns = useCallback(async () => {
    if (loadingMoreRuns || !hasMoreRuns) return;
    const brandId = activeBrand?.id;
    const currentOffset = runOffset;
    setLoadingMoreRuns(true);
    try {
      const r = await api.getRuns({ limit: RUN_PAGE_SIZE, offset: currentOffset, brand_id: brandId, exclude_approval_status: 'dismissed', include_preview: true });
      setRunOffset(prev => prev + r.runs.length);
      setTotalArtifacts(r.total);
      setHasMoreRuns(r.runs.length >= RUN_PAGE_SIZE && currentOffset + r.runs.length < r.total);
      const next = r.runs
        .filter(run =>
          run.approval_status !== 'dismissed' &&
          !deletedArtifactIdsRef.current.has(run.run_id) &&
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
    const root = feedColRef.current;
    if (!node || !hasMoreRuns || !root) return;
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) {
        loadMoreRuns();
      }
    }, { root, rootMargin: '600px 0px' });
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasMoreRuns, runOffset, loadingMoreRuns, loadMoreRuns]);

  // Poll every 15 s for new runs — makes Stream a live TikTok-style feed.
  useEffect(() => {
    if (loading) return;
    const brandId = activeBrand?.id;

    const poll = async () => {
      try {
        const r = await api.getRuns({ limit: 10, brand_id: brandId, exclude_approval_status: 'dismissed', include_preview: true });
        setTotalArtifacts(r.total);
        const newCandidates = r.runs.filter(run =>
          run.approval_status !== 'dismissed' &&
          !deletedArtifactIdsRef.current.has(run.run_id) &&
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
    const freshPending = pendingRunItems.filter(r =>
      r?.run_id &&
      !apiIds.has(r.run_id) &&
      !deletedArtifactIds.has(r.run_id) &&
      (!brandId || r.brand_id === brandId)
    );
    return sortStreamRuns(
      [...artifacts, ...freshPending]
        .filter(r => !!r?.run_id && r.approval_status !== 'dismissed' && !deletedArtifactIds.has(r.run_id) && runTimestamp(r) > 0 && (!brandId || r.brand_id === brandId))
    );
  }, [activeBrand?.id, artifacts, deletedArtifactIds, pendingRunItems]);

  // Keep infinite scroll active even when deletes/filtering leave the visible
  // feed shorter than the viewport. The sentinel still handles normal scrolling;
  // this pre-fill guard prevents a short/empty feed from getting stuck before
  // the observer can naturally intersect again.
  useEffect(() => {
    if (loading || loadingMoreRuns || !hasMoreRuns) return;
    if (streamArtifacts.length >= RUN_PAGE_SIZE) return;
    loadMoreRuns();
  }, [hasMoreRuns, loadMoreRuns, loading, loadingMoreRuns, streamArtifacts.length]);

  useEffect(() => {
    window.dispatchEvent(new CustomEvent('bos:stream-count', {
      detail: { count: totalArtifacts || streamArtifacts.length, brand_id: activeBrand?.id || null },
    }));
  }, [activeBrand?.id, streamArtifacts.length, totalArtifacts]);

  function removeLocalRun(run: RunResponse) {
    removePendingRun(run.run_id);
    setDeletedArtifactIds(prev => {
      const next = new Set(prev);
      next.add(run.run_id);
      writeDeletedArtifactIds(next);
      return next;
    });
    setArtifacts(prev => prev.filter(item => item.run_id !== run.run_id));
    setRunOffset(prev => Math.max(0, prev - 1));
    setTotalArtifacts(prev => Math.max(0, prev - 1));
  }

  function updateLocalStatus(run: RunResponse, status: 'approved' | 'rejected') {
    removePendingRun(run.run_id);
    setArtifacts(prev => prev.map(item =>
      item.run_id === run.run_id ? ({ ...item, approval_status: status } as RunResponse) : item
    ));
  }

  function configureFromCard(update: StreamUpdateOut) {
    const target = String(update.data_json?.config_target || 'stream-setup');
    if (target.includes('connector')) navigate('/admin/modules');
    else if (target.includes('gmail')) navigate('/admin/brands');
    else navigate('/admin/stream-setup');
  }

  function askCmoAboutCard(update: StreamUpdateOut) {
    window.dispatchEvent(new CustomEvent('bos:stream-card-context', {
      detail: {
        sourceType: 'update',
        id: update.id,
        type: update.type,
        actionLabel: 'Ask CMO',
        data_json: update.data_json,
        priority: update.priority,
        source_key: update.source_key,
      },
    }));
    const prefill = buildCmoPrefill(update);
    try { sessionStorage.setItem('bos:cmo-prefill', prefill); } catch {}
    window.dispatchEvent(new CustomEvent('bos:cmo-prefill', { detail: prefill }));
    navigate('/cmo');
  }

  async function deleteUrgentUnread() {
    const toDelete = streamUpdates.filter(update => update.priority === 'urgent');
    if (toDelete.length === 0) return;
    if (!window.confirm(`Delete ${toDelete.length} urgent Stream alert${toDelete.length === 1 ? '' : 's'}? This cannot be undone.`)) return;
    setStreamUpdates(prev => prev.filter(update => update.priority !== 'urgent'));
    try {
      await Promise.all(toDelete.map(update => api.deleteStreamUpdate(update.id)));
    } catch {
      // Reload the stream if the optimistic delete failed.
      const brandId = activeBrand?.id;
      api.getStream(false).then(stream => setStreamUpdates((stream.updates || []).filter(update => {
        const ref = updateBrandRef(update);
        return !brandId || !ref || ref === brandId;
      }))).catch(() => {});
    }
  }

  if (loading) {
    return <div className="loading-full"><span className="spinner" /></div>;
  }

  const visibleStreamArtifacts = streamArtifacts;
  const visibleStreamUpdates = streamUpdates;
  const attentionCount = totalArtifacts || visibleStreamArtifacts.length;
  const dateLabel = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
  const brandLabel = activeBrand?.name || 'All brands';
  const objectiveTitle = 'Current operations';

  return (
    <div className={`stream-fullscreen${embedded ? ' stream-embedded' : ''}`}>
      <div ref={feedColRef} className={`stream-feed-col${panelItem ? ' stream-panel-open' : ''}`}>
        <div className="stream-content-inner">
          <div className="stream-header-zone">
            <div className="stream-kicker">{dateLabel} · {brandLabel}</div>
            <h2 className="stream-title">
              {attentionCount} artifact{attentionCount !== 1 ? 's' : ''}
            </h2>
            <div className="stream-sub">
              Newest artifacts first. Act on what matters, delete what does not.
            </div>
            {streamUpdates.some(update => update.priority === 'urgent') && (
              <button className="btn btn-ghost" style={{ marginBottom: 10 }} onClick={deleteUrgentUnread}>
                Delete urgent alerts ({streamUpdates.filter(update => update.priority === 'urgent').length})
              </button>
            )}
          </div>

          <div className="stream-artifact-feed">
            {visibleStreamArtifacts.length === 0 && visibleStreamUpdates.length === 0 && (
              <div className="g2card">
                <span className="g2type outcome">Stream quiet</span>
                <div className="g2why" style={{ marginTop: 10, fontWeight: 700 }}>No decisions need attention right now.</div>
                <div className="g2why">BOS is watching Gmail replies, pending outcomes, setup readiness, and new artifacts.</div>
                <div className="g2rec"><b>Next —</b>No action needed until BOS finds a decision, outcome, or setup blocker.</div>
                <button className="btn btn-accent" onClick={() => navigate('/admin/stream-setup')}>Review Stream setup →</button>
              </div>
            )}
            {visibleStreamArtifacts.map(run => (
              <StreamArtifactCard
                key={run.run_id}
                run={run}
                brandName={brandLabel}
                objectiveTitle={objectiveTitle}
                focused={focusedRunId === run.run_id}
                registerCard={registerArtifactCard}
                onApproved={r => updateLocalStatus(r, 'approved')}
                onDeleted={r => removeLocalRun(r)}
                onRevised={original => setArtifacts(prev => prev.filter(r => r.run_id !== original.run_id))}
              />
            ))}
            {visibleStreamUpdates.map(update => (
              <StreamDataCard
                key={update.id}
                update={update}
                brandName={brandLabel}
                objectiveTitle={objectiveTitle}
                onDelete={deleted => setStreamUpdates(prev => prev.filter(item => item.id !== deleted.id))}
                onAskCMO={askCmoAboutCard}
                onInvestigate={card => setPanelItem(card)}
                onConfigure={configureFromCard}
              />
            ))}
            <div ref={loadMoreRef} className="stream-load-more">
              {loadingMoreRuns ? (
                <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
                  Loading more…
                </span>
              ) : hasMoreRuns ? (
                'Scroll for more'
              ) : (
                'End of stream'
              )}
            </div>
          </div>
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
