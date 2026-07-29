import { useState, useCallback, useEffect, useRef, type ReactNode } from 'react';
import { api, getApiKey } from '../../api/client';
import { useUI } from '../../context/UIContext';
import { GoogleSearchPreview } from './previews/GoogleSearchPreview';
import { GoogleDisplayPreview } from './previews/GoogleDisplayPreview';
import { FacebookFeedPreview } from './previews/FacebookFeedPreview';
import { InstagramFeedPreview } from './previews/InstagramFeedPreview';
import { InstagramStoryPreview } from './previews/InstagramStoryPreview';
import { EmailPreview } from './previews/EmailPreview';
import { PinterestPreview } from './previews/PinterestPreview';
import { TwitterFeedPreview } from './previews/TwitterFeedPreview';
import { sanitizeArtifactPreviewText } from '../../utils/artifacts';
import type { ChatHistoryItem, ChatReference, RunResponse } from '../../api/types';

type DriveFile = { id: string; name: string; mimeType: string; size?: number; webViewLink?: string; thumbnailLink?: string };
type DriveFolder = { id: string; name: string };
type DriveMediaKind = 'all' | 'image' | 'video';
type SocialConnection = { id: string; brand_id: string | null; platform: string; page_id: string; page_name: string | null; page_handle: string | null; status: string };
type PublishOption = { action: string; moduleId: string; label: string; platform: string; connected: boolean; accountLabel?: string };

const DOC_MIMES_SET = new Set([
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/vnd.ms-powerpoint',
  'application/pdf',
  'application/vnd.google-apps.document',
  'application/vnd.google-apps.presentation',
  'application/json',
  'text/plain',
]);

const LOCAL_ATTACHMENT_ACCEPT = [
  '.jpg', '.jpeg', '.png', '.webp', '.gif',
  '.doc', '.docx', '.ppt', '.pptx', '.pdf', '.json', '.txt',
  'image/jpeg', 'image/png', 'image/webp', 'image/gif',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.ms-powerpoint',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/pdf', 'application/json', 'text/plain',
].join(',');

function dataTransferHasFiles(dataTransfer?: DataTransfer | null): boolean {
  return Array.from(dataTransfer?.types || []).includes('Files');
}

interface ApprovalBundleProps {
  run: RunResponse;
  surfaceContext: 'chat-inline' | 'panel' | 'full-screen';
  onRevision?: (reply: string, run: RunResponse, previousRunId?: string) => void;
  onApproved?: (run: RunResponse) => void;
  onDeleted?: (run: RunResponse) => void;
  revisionHistory?: ChatHistoryItem[];
}

type ReviewStatus = 'pending' | 'draft' | 'deleted' | 'dismissed' | 'approved' | 'failed';

function titleCase(value: string): string {
  return value
    .replace(/[_-]/g, ' ')
    .split(' ')
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function artifactTitle(run: RunResponse, platformLabel: string): string {
  if (!run?.module_id) return 'Artifact';
  const moduleId = run.module_id.toLowerCase();
  if (moduleId.includes('strategy_workflow')) return 'Strategy Workflow';
  if (moduleId.includes('storyboard.motion')) return 'Previs Motion Draft';
  if ((run.result?.block as any)?.artifact_kind === 'video_production_blueprint') return 'Video Production Blueprint';
  if (moduleId.includes('storyboard.render')) return 'Storyboard Image';
  if (moduleId.includes('storyboard')) return 'Storyboard Draft';
  if (moduleId.includes('gtm_plan') || moduleId.includes('gtm')) return 'GTM Strategy';
  if (moduleId.includes('marketing.plan')) return 'Marketing Plan';
  if (moduleId.includes('email') && moduleId.includes('plan')) return 'Email Campaign Plan';
  if (moduleId.includes('email') || platformLabel.toLowerCase().includes('email')) return 'Email Draft';
  if (moduleId.includes('gbp') || platformLabel.toLowerCase().includes('google business')) return 'Google Business Profile Audit';
  if (moduleId.includes('postcraft')) return 'Postcraft Image';
  if (moduleId.includes('plan')) return 'Campaign Plan';
  if (moduleId.includes('meta.pages.insights.report')) return 'Meta Insight Report';
  if (moduleId.includes('report') || moduleId.includes('analytics')) return 'Marketing Report';
  if ((run.result?.block as any)?.type === 'imprint_asset') return 'Imprint Image';
  if (moduleId.includes('imprint')) return 'Image Draft';
  if (moduleId.includes('video.edit')) {
    const b = run.result?.block as any;
    return b?.source_run_id ? 'Video Edit · Revision' : 'Video Edit · Cut 1';
  }
  if (moduleId.includes('shortform.video')) return 'Shortform Video Draft';
  if (moduleId.includes('creative.post')) return 'Facebook Post Creative';
  if (moduleId.includes('meta.pages.read')) return 'Facebook Pages';
  if (moduleId.includes('meta.posts.draft')) return 'Facebook Post Draft';
  if (moduleId.includes('meta.posts.publish')) return 'Facebook Post';
  if (moduleId.includes('meta.posts.read')) return 'Facebook Posts';
  if (moduleId.includes('google')) return 'Google Ad Draft';
  if (moduleId.includes('facebook')) return 'Facebook Draft';
  if (moduleId.includes('instagram')) return 'Instagram Draft';
  if (moduleId.includes('twitter') || moduleId.includes('x.')) return 'Social Post Draft';
  if (moduleId.includes('pinterest')) return 'Pinterest Draft';
  return `${titleCase(platformLabel)} Draft`;
}

function initialReviewStatus(run: RunResponse): ReviewStatus {
  const block = run.result?.block as any;
  const status = run.approval_status || (run as any).approval_status || (run.result as any)?.approval_status;
  if (run.status === 'failed' || block?.status === 'failed' || status === 'failed') return 'failed';
  if (status === 'dismissed') return 'dismissed';
  // ApprovalBundle is an operator decision surface. On first render, default
  // every non-failed/non-deleted artifact to needs-revision/review so a newly
  // generated artifact never appears as Approved/Revised just because a source
  // artifact or backend action carried a terminal approval_status.
  return 'pending';
}

function statusLabel(status: ReviewStatus): string {
  if (status === 'approved') return 'Approved';
  if (status === 'deleted' || status === 'dismissed') return 'Deleted';
  if (status === 'draft') return 'Saved draft';
  if (status === 'failed') return 'Failed';
  return 'Needs approval';
}

function statusColor(status: ReviewStatus): string {
  if (status === 'approved') return 'var(--success)';
  if (status === 'deleted' || status === 'dismissed') return 'var(--ink-muted)';
  if (status === 'draft') return 'var(--forest)';
  if (status === 'failed') return 'var(--crimson)';
  return 'var(--border)';
}

function hasArtifactAction(run: RunResponse, action: string): boolean {
  const block = run.result?.block;
  const blockType = (block as any)?.type || (block as any)?.legacy_type || '';
  // Backward-compatible: storyboard images always support generate_video
  if (action === 'generate_video' && (blockType === 'image_asset' || blockType === 'storyboard_image')) {
    return true;
  }
  return Array.isArray(block?.allowed_actions)
    && block.allowed_actions.includes(action)
    && typeof block?.action_modules?.[action] === 'string';
}

function publishPlatform(action: string, moduleId: string): string {
  if (action === 'generate_video') return 'video';
  const key = `${action} ${moduleId}`.toLowerCase();
  if (key.includes('youtube')) return 'youtube';
  if (key.includes('tiktok')) return 'tiktok';
  if (key.includes('instagram')) return 'instagram';
  if (key.includes('facebook') || key.includes('meta')) return 'facebook';
  return action.replace(/^publish_/, '');
}

function publishLabel(action: string, moduleId: string, blockType?: string): string {
  if (action === 'generate_video') return 'Generate Video';
  const platform = publishPlatform(action, moduleId);
  const isVideo = blockType === 'video_asset' || blockType === 'creative_shortform_video';
  if (platform === 'youtube') return isVideo ? 'YouTube Shorts' : 'YouTube';
  if (platform === 'facebook') return isVideo ? 'Facebook Reels' : 'Facebook';
  if (platform === 'instagram') return isVideo ? 'Instagram Reels' : 'Instagram';
  if (platform === 'tiktok') return 'TikTok';
  return titleCase(action.replace(/^publish_/, ''));
}

function buildPublishOptions(actionModules: Record<string, string> | undefined, connections: SocialConnection[], blockType?: string, allowImplicitGenerateVideo = false): PublishOption[] {
  if (!actionModules) actionModules = {};
  // Backward-compatible: only storyboard images implicitly support generate_video.
  // Do not infer this from block.type === "image_asset" alone: Postcraft and
  // Imprint images use the same generic block type and must not show a bogus
  // Generate Video option in their approval bundle.
  if (allowImplicitGenerateVideo && !actionModules.generate_video) {
    actionModules = { ...actionModules, generate_video: 'storyboard.motion.render' };
  }
  return Object.entries(actionModules)
    .filter(([action]) => action.startsWith('publish') || action === 'generate_video')
    .map(([action, moduleId]) => {
      const platform = publishPlatform(action, moduleId);
      const connection = connections.find(c => c.status === 'connected' && c.platform === platform);
      const isInternalWorkflowAction = action === 'generate_video';
      return {
        action,
        moduleId,
        platform,
        label: publishLabel(action, moduleId, blockType),
        connected: isInternalWorkflowAction || Boolean(connection),
        accountLabel: isInternalWorkflowAction ? 'BOS workflow' : (connection?.page_name || connection?.page_handle || connection?.page_id),
      };
    });
}

function actionRunFailed(actionRun: RunResponse): boolean {
  const blockStatus = String((actionRun.result?.block as any)?.status || '').toLowerCase();
  return actionRun.status === 'failed' || blockStatus === 'failed';
}

function actionRunError(actionRun: RunResponse): string {
  const block = (actionRun.result?.block as any) || {};
  return block.message || actionRun.result?.content || 'Publish action failed.';
}

function minFacebookScheduleLocal(): string {
  const d = new Date(Date.now() + 11 * 60 * 1000);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function signalPipelineStatus(detail: { id: string; label: string; detail?: string; status: 'running' | 'done' | 'failed' }) {
  window.dispatchEvent(new CustomEvent('bos:pipeline-status', { detail: { startedAt: Date.now(), ...detail } }));
}

function referenceDisplayName(ref: ChatReference): string {
  return ref.title || ref.drive_file_name || 'Attachment';
}

function referencePreviewKind(ref: ChatReference): 'image' | 'document' | 'text' {
  if (ref.kind === 'image') return 'image';
  if (ref.kind === 'document') return 'document';
  return 'text';
}

function sanitizeMarketingCopy(value: string): string {
  const text = String(value || '').trim();
  if (!text) return '';
  const blockedPrefixes = [
    'template:', 'format:', 'headline:', 'subheadline:', 'body copy:', 'body:',
    'cta:', 'visual direction:', 'asset/brand notes:', 'campaign:',
    'json_revision_spec:', 'source_render_spec:', 'revision source panel:',
  ];
  const blockedFragments = [
    'json_revision_spec', 'source_render_spec', 'revision source panel',
    'you are editing an existing approved social ad', 'apply the json revision spec exactly',
  ];
  const kept: string[] = [];
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) {
      if (kept.length && kept[kept.length - 1] !== '') kept.push('');
      continue;
    }
    const lowered = line.toLowerCase();
    if (blockedPrefixes.some(prefix => lowered.startsWith(prefix))) continue;
    if (blockedFragments.some(fragment => lowered.includes(fragment))) continue;
    kept.push(line);
  }
  while (kept.length && kept[kept.length - 1] === '') kept.pop();
  const cleaned = kept.join('\n').trim();
  return ['-', '—', '_'].includes(cleaned) ? '' : cleaned;
}

function templateNameFromAssetName(name: string): string {
  const raw = String(name || '').trim();
  if (!raw) return 'Brand template draft';
  return raw.replace(/\.[a-z0-9]{2,5}$/i, '').replace(/[_-]+/g, ' ').trim() || 'Brand template draft';
}

function templateFormatForValue(value: string | undefined | null): string {
  const text = String(value || '').trim().toLowerCase();
  if (!text) return 'square_feed';
  if (text === 'square' || text === '1:1') return 'square_feed';
  if (text === 'portrait' || text === 'portrait_feed' || text === '4:5') return 'portrait_feed';
  if (text === 'story' || text === 'reel' || text === 'story_reel' || text === '9:16') return 'story_reel';
  if (text === 'landscape' || text === '16:9') return 'landscape';
  return text;
}

function DriveSwapContainer({
  kind,
  selectedFile,
  onSwap,
  onClear,
  children,
}: {
  kind: DriveMediaKind;
  selectedFile?: DriveFile | null;
  onSwap: () => void;
  onClear?: () => void;
  children: ReactNode;
}) {
  const label = kind === 'video' ? 'Video' : 'Image';
  return (
    <div style={{ width: '100%', maxWidth: 540, border: '1px solid #e5e7eb', borderRadius: 12, overflow: 'hidden', background: '#fff', boxShadow: '0 1px 2px rgba(15, 23, 42, 0.04)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 11px', borderBottom: '1px solid #eef2f7', background: '#fbfbfa' }}>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--forest)', textTransform: 'uppercase', letterSpacing: '.14em' }}>{label} artifact</div>
          <div style={{ fontSize: 11, color: selectedFile ? 'var(--success)' : 'var(--ink-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {selectedFile ? `Using Drive ${kind}: ${selectedFile.name}` : `Generated ${kind} · can be swapped from Google Drive`}
          </div>
        </div>
        {selectedFile && onClear && (
          <button className="artifact-btn ghost" style={{ flexShrink: 0 }} onClick={onClear}>Use generated</button>
        )}
        <button className="artifact-btn ghost" style={{ flexShrink: 0 }} onClick={onSwap}>Swap · Drive</button>
      </div>
      <div style={{ padding: 12, display: 'flex', justifyContent: 'center', background: '#f9fafb' }}>
        {children}
      </div>
    </div>
  );
}

export function ApprovalBundle({ run, surfaceContext, onRevision, onApproved, onDeleted, revisionHistory = [] }: ApprovalBundleProps) {
  const { removePendingRun, addPendingRun, activeCampaign, activeBrand } = useUI();
  const [reviewStatus, setReviewStatus] = useState<ReviewStatus>(() => initialReviewStatus(run));
  const [modifying, setModifying] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [revisionBusy, setRevisionBusy] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [revisionError, setRevisionError] = useState<string | null>(null);
  const [revision, setRevision] = useState<RunResponse | null>(null);
  const [revisionReply, setRevisionReply] = useState<string>('');
  const [localRevisionHistory, setLocalRevisionHistory] = useState<ChatHistoryItem[]>([]);
  const [storyboardRenderRun, setStoryboardRenderRun] = useState<RunResponse | null>(null);
  const [storyboardVideoRun, setStoryboardVideoRun] = useState<RunResponse | null>(null);
  const [postcraftRenderRun, setPostcraftRenderRun] = useState<RunResponse | null>(null);

  // Drive picker (shared between fb_page_post_draft attach, creative_post_asset swap, shortform video swap)
  const [drivePickerOpen, setDrivePickerOpen] = useState(false);
  const [drivePickerMediaType, setDrivePickerMediaType] = useState<string>('image');
  const [driveFiles, setDriveFiles] = useState<DriveFile[]>([]);
  const [driveFolders, setDriveFolders] = useState<DriveFolder[]>([]);
  const [driveCurrentFolder, setDriveCurrentFolder] = useState<DriveFolder | null>(null);
  const [driveFolderStack, setDriveFolderStack] = useState<DriveFolder[]>([]);
  const [driveLoading, setDriveLoading] = useState(false);
  const [driveError, setDriveError] = useState<string | null>(null);
  const [driveSearch, setDriveSearch] = useState('');
  const [attachedImage, setAttachedImage] = useState<DriveFile | null>(null);
  const [attaching, setAttaching] = useState(false);
  const [revisionReferences, setRevisionReferences] = useState<ChatReference[]>([]);
  const [dragTarget, setDragTarget] = useState<'revision' | 'modal' | null>(null);
  const [templateModalOpen, setTemplateModalOpen] = useState(false);
  const [templateSaving, setTemplateSaving] = useState(false);
  const [templateError, setTemplateError] = useState<string | null>(null);
  const [templateNotice, setTemplateNotice] = useState<string | null>(null);
  const [templateSource, setTemplateSource] = useState<{ driveFileId: string; name: string; mimeType?: string; webViewLink?: string; existingTemplateId?: string | null; existingStatus?: string | null } | null>(null);
  const [templateNameDraft, setTemplateNameDraft] = useState('');
  const [templateFormatDraft, setTemplateFormatDraft] = useState('square_feed');
  const [templateContentTypeDraft, setTemplateContentTypeDraft] = useState('promo');
  const uploadInputRef = useRef<HTMLInputElement>(null);

  const result = run.result;
  const moduleId = run.module_id.toLowerCase();
  const channel = `${moduleId} ${(run.result?.platform || '').toLowerCase()}`;
  const platformLabel = titleCase(run.result?.platform || run.module_id.split('.').pop() || 'asset');
  const title = artifactTitle(run, platformLabel);

  if (!result) return <div className="bos-ws-empty">No artifact content available.</div>;

  // Artifact actions must stay scoped to the artifact's brand, not whatever
  // brand happens to be selected in the global UI. This matters in All Brands
  // views and when reviewing old/pending artifacts after switching brands.
  const artifactBrandId = String(run.brand_id || (result.block as any)?.brand_id || activeBrand?.id || '');
  const brandName = result.block?.brand_name || result.brand_name || run.brand_name || 'Unknown brand';

  // Google Drive thumbnailLink URLs require Google auth cookies, so they fail
  // when used directly in <img> tags. Use the backend proxy instead.
  function driveThumbnailUrl(fileId: string): string {
    const key = getApiKey() || '';
    return `/api/social/drive/thumbnail/${encodeURIComponent(fileId)}?brand_id=${encodeURIComponent(artifactBrandId)}${key ? `&api_key=${encodeURIComponent(key)}` : ''}`;
  }
  function localVideoSrcFromBlock(block: any): string | undefined {
    const url = String(block?.video_proxy_url || '').trim();
    return url || undefined;
  }
  const socialHandle = result.block?.brand_handle || result.brand_handle || '@brand';
  const selfCheckPassed = result.self_check === 'pass';
  const isFbDraft = result.block?.type === 'fb_page_post_draft';
  const isStoryboardDraft = result.block?.type === 'storyboard_json'
    || moduleId.includes('storyboard.create')
    || (moduleId.includes('storyboard.render') && String(result.content || '').includes('Render was held'))
    || (moduleId.includes('storyboard') && String(result.content || '').includes('Spec JSON:'));
  const isProductionBlueprint = result.block?.type === 'storyboard_json' && (result.block as any)?.artifact_kind === 'video_production_blueprint';
  const isStoryboardImage = moduleId.includes('storyboard.render') && (result.block?.type === 'image_asset' || (result.block as any)?.legacy_type === 'storyboard_image');
  const isImprintDraft = result.block?.type === 'imprint_draft' || moduleId.includes('imprint.draft');
  const isImprintAsset = result.block?.type === 'imprint_asset' || (result.block as any)?.legacy_type === 'imprint_asset';
  const isCreativePost = result.block?.type === 'creative_post_asset' && result.block?.status === 'succeeded';
  const isPostcraftDraft = result.block?.type === 'postcraft_draft' || moduleId === 'postcraft.draft';
  const isPostcraftImage = moduleId.includes('postcraft.render') && result.block?.type === 'image_asset' && result.block?.status === 'succeeded';
  const isShortformVideo = (result.block?.type === 'creative_shortform_video' || result.block?.type === 'video_asset') && result.block?.status === 'succeeded';
  const isImageAsset = (result.block?.type === 'image_asset' || isImprintAsset) && result.block?.status === 'succeeded';
  const canPublish = hasArtifactAction(run, 'publish') && (!isFbDraft || Boolean(result.block?.page_id)) && !isImageAsset && !isShortformVideo && !isPostcraftImage;

  // Editable state for creative_post_asset review
  const [editedCaption, setEditedCaption] = useState<string>(result.block?.caption || result.block?.message || '');
  const [swappedAttachment, setSwappedAttachment] = useState<DriveFile | null>(null);

  // Editable state for creative_shortform_video review
  const [editedHookText, setEditedHookText] = useState<string>((result.block as any)?.hook_text || '');
  const [editedCtaText, setEditedCtaText] = useState<string>((result.block as any)?.cta_text || '');
  const [swappedVideo, setSwappedVideo] = useState<DriveFile | null>(null);

  // Editable state for image_asset review
  const [imageCaption, setImageCaption] = useState<string>('');

  // Optional operator notes passed directly into Previs Motion video generation.
  const [videoGenerationNotes, setVideoGenerationNotes] = useState<string>('');

  // Omni-channel publish selection: options come from the artifact's declared
  // action_modules, readiness comes from the active brand's connected accounts.
  const [brandConnections, setBrandConnections] = useState<SocialConnection[]>([]);
  const [publishSelections, setPublishSelections] = useState<Record<string, boolean>>({});
  const [publishOptionsLoading, setPublishOptionsLoading] = useState(false);
  const [scheduleAtLocal, setScheduleAtLocal] = useState('');
  const actionModules = (result.block as any)?.action_modules as Record<string, string> | undefined;
  const publishOptions = buildPublishOptions(actionModules, brandConnections, result.block?.type, isStoryboardImage);
  const selectedPublishOptions = publishOptions.filter(opt => opt.connected && publishSelections[opt.action]);
  const selectedSchedulableFacebookOptions = selectedPublishOptions.filter(opt => opt.platform === 'facebook' && opt.moduleId.includes('marketing.channel.meta.posts.publish'));
  const hasSchedulableFacebookOption = publishOptions.some(opt => opt.connected && opt.platform === 'facebook' && opt.moduleId.includes('marketing.channel.meta.posts.publish'));
  const hasPublishActionModules = Boolean(actionModules && Object.keys(actionModules).some(action => action.startsWith('publish') || action === 'generate_video'));
  const isOmniPublishAsset = !isStoryboardImage && (isShortformVideo || isImageAsset) && hasPublishActionModules;

  useEffect(() => {
    if (!isOmniPublishAsset || !artifactBrandId) {
      setBrandConnections([]);
      return;
    }
    setPublishOptionsLoading(true);
    api.listSocialConnections(artifactBrandId)
      .then(rows => setBrandConnections(rows as SocialConnection[]))
      .catch(() => setBrandConnections([]))
      .finally(() => setPublishOptionsLoading(false));
  }, [isOmniPublishAsset, artifactBrandId, run.run_id]);

  useEffect(() => {
    setPublishSelections(prev => {
      const next: Record<string, boolean> = {};
      for (const opt of publishOptions) next[opt.action] = Boolean(prev[opt.action] && opt.connected);
      return next;
    });
  }, [publishOptions.map(opt => `${opt.action}:${opt.connected}`).join('|')]);

  const handleApprove = async () => {
    if (isShortformVideo) {
      await handleVideoApprove();
      return;
    }
    if (isStoryboardDraft) {
      await handleStoryboardRenderApprove();
      return;
    }
    if (isPostcraftDraft) {
      await handlePostcraftDraftApprove();
      return;
    }
    if (isImprintDraft) {
      await handleImprintDraftApprove();
      return;
    }
    if (isCreativePost) {
      await handleCreativeApprove();
      return;
    }
    if (isStoryboardImage && hasArtifactAction(run, 'generate_video')) {
      await handleStoryboardImageVideoApprove();
      return;
    }
    if (canPublish) {
      await handleApproveAndPublish();
      return;
    }
    setReviewStatus('approved');
    try {
      await api.approveRun(run.run_id);
      removePendingRun(run.run_id);
      onApproved?.(run);
    } catch (e) {
      setReviewStatus('pending');
      addPendingRun(run);
      setRevisionError(e instanceof Error ? e.message : 'Could not approve this artifact.');
    }
  };


  const handlePostcraftDraftApprove = async () => {
    setPublishing(true);
    setRevisionError(null);
    setPostcraftRenderRun(null);
    signalPipelineStatus({
      id: `postcraft-render-${run.run_id}`,
      label: 'Postcraft image generation in progress',
      detail: 'BOS is rendering the approved Postcraft draft into a branded image. The generated image will appear as a new Needs approval artifact.',
      status: 'running',
    });
    // Mirror storyboard behavior: keep the draft visible while rendering runs.
    // Rendering can take minutes; if we mark/remove the source card immediately,
    // the operator sees “Approved” but no obvious generation progress.
    addPendingRun({ ...run, approval_status: 'pending' } as RunResponse);
    setReviewStatus('pending');
    try {
      const resp: any = hasArtifactAction(run, 'render')
        ? await api.renderPostcraftRun(run.run_id, { confirm: true })
        : await api.approveRun(run.run_id);
      const actionRun = resp.action_run as RunResponse | undefined;
      if (actionRun) {
        addPendingRun(actionRun);
        window.dispatchEvent(new CustomEvent('bos:focus-artifact', { detail: actionRun }));
        setPostcraftRenderRun(actionRun);
        signalPipelineStatus({
          id: `postcraft-render-${run.run_id}`,
          label: 'Postcraft image ready for approval',
          detail: 'A new Postcraft image artifact was added for review.',
          status: 'done',
        });
        if (actionRunFailed(actionRun)) {
          setRevisionError(actionRunError(actionRun));
          throw new Error(actionRunError(actionRun));
        }
      } else {
        signalPipelineStatus({
          id: `postcraft-render-${run.run_id}`,
          label: 'Postcraft render accepted',
          detail: 'BOS accepted the approval. The generated image will appear as a Needs approval artifact when ready.',
          status: 'running',
        });
      }
      setReviewStatus('pending');
      addPendingRun({ ...run, approval_status: 'pending' } as RunResponse);
    } catch (e) {
      setReviewStatus('pending');
      addPendingRun(run);
      signalPipelineStatus({
        id: `postcraft-render-${run.run_id}`,
        label: 'Postcraft image generation failed',
        detail: e instanceof Error ? e.message : 'Could not render this Postcraft draft.',
        status: 'failed',
      });
      setRevisionError(e instanceof Error ? e.message : 'Could not render this Postcraft draft.');
    } finally {
      setPublishing(false);
    }
  };

  const handleImprintDraftApprove = async () => {
    setPublishing(true);
    setRevisionError(null);
    signalPipelineStatus({
      id: `imprint-generate-${run.run_id}`,
      label: 'Image generation in progress',
      detail: 'BOS is generating the approved copy into a durable image asset. The generated image will appear as a new Needs approval artifact.',
      status: 'running',
    });
    addPendingRun({ ...run, approval_status: 'pending' } as RunResponse);
    setReviewStatus('pending');
    try {
      const resp: any = await api.approveRun(run.run_id);
      const actionRun = resp.action_run as RunResponse | undefined;
      if (actionRun) {
        addPendingRun(actionRun);
        window.dispatchEvent(new CustomEvent('bos:focus-artifact', { detail: actionRun }));
        signalPipelineStatus({
          id: `imprint-generate-${run.run_id}`,
          label: 'Image ready for approval',
          detail: 'A new generated image artifact was added for review. Approve it separately when it is final.',
          status: 'done',
        });
        if (actionRunFailed(actionRun)) {
          setReviewStatus('pending');
          addPendingRun(run);
          throw new Error(actionRunError(actionRun));
        }
      } else {
        signalPipelineStatus({
          id: `imprint-generate-${run.run_id}`,
          label: 'Image generation started',
          detail: 'BOS accepted the approval. The generated image will appear as a Needs approval artifact when ready.',
          status: 'running',
        });
      }
      setReviewStatus('approved');
      removePendingRun(run.run_id);
      onApproved?.(run);
    } catch (e) {
      setReviewStatus('pending');
      addPendingRun(run);
      signalPipelineStatus({
        id: `imprint-generate-${run.run_id}`,
        label: 'Image generation failed',
        detail: e instanceof Error ? e.message : 'Could not generate the image asset.',
        status: 'failed',
      });
      setRevisionError(e instanceof Error ? e.message : 'Could not generate the image asset.');
    } finally {
      setPublishing(false);
    }
  };

  const handleStoryboardRenderApprove = async () => {
    setPublishing(true);
    setRevisionError(null);
    setStoryboardRenderRun(null);
    const sourceStoryboardVersion = (result.block as any)?.storyboard_spec?.revision?.variation_id || (result.block as any)?.artifact_version || (result.block as any)?.variation_id || '';
    signalPipelineStatus({
      id: `storyboard-render-${run.run_id}`,
      label: sourceStoryboardVersion
        ? (isProductionBlueprint ? `Image storyboard ${sourceStoryboardVersion} generation in progress` : `Storyboard render ${sourceStoryboardVersion} in progress`)
        : (isProductionBlueprint ? 'Image storyboard generation in progress' : 'Storyboard render in progress'),
      detail: isProductionBlueprint
        ? `BOS is rendering the approved production blueprint${sourceStoryboardVersion ? ` ${sourceStoryboardVersion}` : ''} into an image storyboard. Video generation happens after that storyboard is approved.`
        : `BOS is generating the image storyboard${sourceStoryboardVersion ? ` ${sourceStoryboardVersion}` : ''}. The new artifact will appear as Needs approval.`,
      status: 'running',
    });
    // Keep the text storyboard visible while the image render runs. Rendering can
    // take minutes, so do not mark the visible card Approved or remove it from
    // needs-review; otherwise the user thinks the process disappeared/ended.
    addPendingRun({ ...run, approval_status: 'pending' } as RunResponse);
    setReviewStatus('pending');
    try {
      const actionName = 'render';
      const resp: any = hasArtifactAction(run, actionName)
        ? await api.renderStoryboardRun(run.run_id, { confirm: true })
        : await api.approveRun(run.run_id);
      const actionRun = resp.action_run as RunResponse | undefined;
      if (actionRun) {
        addPendingRun(actionRun);
        window.dispatchEvent(new CustomEvent('bos:focus-artifact', { detail: actionRun }));
        setStoryboardRenderRun(actionRun);
        const storyboardVersion = (actionRun.result?.block as any)?.artifact_version || (actionRun.result?.block as any)?.variation_id || '';
        signalPipelineStatus({
          id: `storyboard-render-${run.run_id}`,
          label: storyboardVersion ? `Storyboard image ${storyboardVersion} ready` : 'Storyboard image ready',
          detail: isProductionBlueprint
            ? `A new Storyboard Image${storyboardVersion ? ` ${storyboardVersion}` : ''} artifact was added for review. Approve it when ready to generate the video.`
            : `A new Storyboard Image${storyboardVersion ? ` ${storyboardVersion}` : ''} artifact was added for review.`,
          status: 'done',
        });
        if (actionRunFailed(actionRun)) {
          setReviewStatus('pending');
          addPendingRun(run);
          throw new Error(actionRunError(actionRun));
        }
      } else {
        throw new Error('BOS accepted the approval but did not return a storyboard render run. No image render was started. Refresh this artifact and try Approve & Render again.');
      }
    } catch (e) {
      setReviewStatus('pending');
      addPendingRun(run);
      signalPipelineStatus({
        id: `storyboard-render-${run.run_id}`,
        label: 'Storyboard render failed',
        detail: e instanceof Error ? e.message : 'Could not render this storyboard.',
        status: 'failed',
      });
      setRevisionError(e instanceof Error ? e.message : 'Could not render this storyboard.');
    } finally {
      setPublishing(false);
    }
  };

  const handleStoryboardImageVideoApprove = async () => {
    setPublishing(true);
    setRevisionError(null);
    setStoryboardVideoRun(null);
    signalPipelineStatus({
      id: `storyboard-video-${run.run_id}`,
      label: 'Video generation in progress',
      detail: 'BOS is generating video from the approved storyboard image. The new video artifact will appear as Needs approval.',
      status: 'running',
    });
    addPendingRun({ ...run, approval_status: 'pending' } as RunResponse);
    setReviewStatus('pending');
    try {
      const note = videoGenerationNotes.trim();
      const overrides: Record<string, unknown> = {};
      if (note) {
        overrides.edit_instruction = note;
        overrides.approval_notes = note;
        overrides.video_generation_notes = note;
      }
      if (swappedAttachment) {
        overrides.drive_file_id = swappedAttachment.id;
        overrides.drive_file_mime = swappedAttachment.mimeType;
        overrides.drive_file_name = swappedAttachment.name;
        overrides._image_swapped = true;
      }
      const resp = await api.generatePrevisVideo(run.run_id, { confirm: true, overrides: Object.keys(overrides).length ? overrides : undefined });
      addPendingRun(resp.action_run);
      window.dispatchEvent(new CustomEvent('bos:focus-artifact', { detail: resp.action_run }));
      setStoryboardVideoRun(resp.action_run);
      signalPipelineStatus({
        id: `storyboard-video-${run.run_id}`,
        label: 'Video artifact ready',
        detail: 'A new video artifact was added for review.',
        status: 'done',
      });
      if (actionRunFailed(resp.action_run)) {
        setReviewStatus('pending');
        addPendingRun(run);
        throw new Error(actionRunError(resp.action_run));
      }
      setReviewStatus('approved');
      removePendingRun(run.run_id);
      onApproved?.(run);
    } catch (e) {
      setReviewStatus('pending');
      addPendingRun(run);
      signalPipelineStatus({
        id: `storyboard-video-${run.run_id}`,
        label: 'Video generation failed',
        detail: e instanceof Error ? e.message : 'Could not generate video from this storyboard.',
        status: 'failed',
      });
      setRevisionError(e instanceof Error ? e.message : 'Could not generate video from this storyboard.');
    } finally {
      setPublishing(false);
    }
  };

  const handleCreativeApprove = async () => {
    const trimmedCaption = editedCaption.trim();
    if (!trimmedCaption) {
      setRevisionError('Post copy is required before publishing. Enter the caption text above.');
      return;
    }
    setPublishing(true);
    setRevisionError(null);
    try {
      const overrides: Record<string, unknown> = { message: trimmedCaption };
      if (swappedAttachment) {
        overrides.drive_file_id = swappedAttachment.id;
        overrides.drive_file_mime = swappedAttachment.mimeType;
        overrides.drive_file_name = swappedAttachment.name;
        overrides._image_swapped = true;
      }
      const resp = await api.executeRunAction(run.run_id, 'publish', { confirm: true, overrides });
      addPendingRun(resp.action_run);
      window.dispatchEvent(new CustomEvent('bos:focus-artifact', { detail: resp.action_run }));
      if (actionRunFailed(resp.action_run)) {
        setReviewStatus('pending');
        addPendingRun(run);
        throw new Error(actionRunError(resp.action_run));
      }
      setReviewStatus('approved');
      setModifying(false);
      removePendingRun(run.run_id);
      onApproved?.(run);
    } catch (e) {
      setReviewStatus('pending');
      setRevisionError(e instanceof Error ? e.message : 'Could not publish to Facebook.');
    } finally {
      setPublishing(false);
    }
  };

  const buildVideoPublishOverrides = (): Record<string, unknown> => {
    const b = result.block as any;
    return {
      video_path: b?.video_path,
      drive_file_id: swappedVideo ? swappedVideo.id : (b?.drive_file_id || undefined),
      drive_file_mime: swappedVideo ? swappedVideo.mimeType : 'video/mp4',
      // Signal to the backend that the user picked a different Drive file.
      // _resolve_drive_video uses this to bypass the local-file-exists early exit.
      ...(swappedVideo ? { _video_swapped: true } : {}),
      hook_text: editedHookText || b?.hook_text,
      cta_text: editedCtaText || b?.cta_text,
      description: editedHookText || b?.hook_text || b?.cta_text || '',
      title: editedHookText || b?.hook_text || 'Shortform video',
    };
  };

  const handleVideoApprove = async () => {
    setPublishing(true);
    setRevisionError(null);
    try {
      setReviewStatus('approved');
      await api.approveRun(run.run_id);
      removePendingRun(run.run_id);
      onApproved?.(run);
    } catch (e) {
      setReviewStatus('pending');
      addPendingRun(run);
      setRevisionError(e instanceof Error ? e.message : 'Could not approve this artifact.');
    } finally {
      setPublishing(false);
    }
  };

  const imagePublishMessage = (b: any): string => {
    if (imageCaption.trim()) return imageCaption.trim();
    const parts = [b?.headline, b?.subheadline, b?.body_copy || b?.body, b?.cta_text || b?.cta]
      .map(v => sanitizeMarketingCopy(String(v || '').trim()))
      .filter(Boolean);
    return parts.length > 0 ? parts.join('\n\n') : '';
  };

  const buildImagePublishOverrides = (): Record<string, unknown> => {
    const b = result.block as any;
    const message = imagePublishMessage(b);
    return swappedAttachment ? {
      drive_file_id: swappedAttachment.id,
      drive_file_mime: swappedAttachment.mimeType,
      drive_file_name: swappedAttachment.name,
      _image_swapped: true,
      message,
    } : {
      _image_data_b64: b?.image_data_b64,
      _image_mime: b?.mime_type || 'image/png',
      message,
      brand_id: artifactBrandId, // Ensure brand scoping for publish
    };
  };

  const handlePublishSelected = async () => {
    if (selectedPublishOptions.length === 0) {
      setRevisionError('Select at least one connected publishing destination.');
      return;
    }
    if (scheduleAtLocal && selectedSchedulableFacebookOptions.length > 0) {
      setRevisionError('A schedule time is selected. Use Schedule Selected, or clear the time to publish immediately.');
      return;
    }
    setPublishing(true);
    setRevisionError(null);
    const publishedRuns: RunResponse[] = [];
    try {
      const overrides = isImageAsset ? buildImagePublishOverrides() : buildVideoPublishOverrides();
      for (const opt of selectedPublishOptions) {
        const resp = await api.executeRunAction(run.run_id, opt.action, { confirm: true, overrides });
        publishedRuns.push(resp.action_run);
        addPendingRun(resp.action_run);
        window.dispatchEvent(new CustomEvent('bos:focus-artifact', { detail: resp.action_run }));
        if (actionRunFailed(resp.action_run)) {
          throw new Error(`${opt.label}: ${actionRunError(resp.action_run)}`);
        }
      }
      setReviewStatus('approved');
      removePendingRun(run.run_id);
      onApproved?.(run);
    } catch (e) {
      setReviewStatus('pending');
      addPendingRun(run);
      const succeededCount = publishedRuns.filter(r => !actionRunFailed(r)).length;
      const suffix = succeededCount > 0 ? ` (${succeededCount} destination${succeededCount === 1 ? '' : 's'} published before the error.)` : '';
      setRevisionError((e instanceof Error ? e.message : 'Could not publish selected destinations.') + suffix);
    } finally {
      setPublishing(false);
    }
  };

  const handleScheduleSelected = async () => {
    if (selectedPublishOptions.length !== 1 || selectedSchedulableFacebookOptions.length !== 1) {
      setRevisionError('Select exactly one connected Facebook destination to schedule.');
      return;
    }
    if (!scheduleAtLocal) {
      setRevisionError('Choose a schedule date and time.');
      return;
    }
    const scheduledAt = new Date(scheduleAtLocal);
    if (Number.isNaN(scheduledAt.getTime())) {
      setRevisionError('Choose a valid schedule date and time.');
      return;
    }
    if (scheduledAt.getTime() < Date.now() + 10 * 60 * 1000) {
      setRevisionError('Facebook requires scheduled posts to be at least 10 minutes in the future. Choose a later time.');
      return;
    }
    setPublishing(true);
    setRevisionError(null);
    try {
      const opt = selectedSchedulableFacebookOptions[0];
      const overrides = isImageAsset ? buildImagePublishOverrides() : buildVideoPublishOverrides();
      overrides.scheduled_at = scheduledAt.toISOString();
      const resp = await api.executeRunAction(run.run_id, opt.action, { confirm: true, overrides });
      addPendingRun(resp.action_run);
      window.dispatchEvent(new CustomEvent('bos:focus-artifact', { detail: resp.action_run }));
      if (actionRunFailed(resp.action_run)) {
        throw new Error(`${opt.label}: ${actionRunError(resp.action_run)}`);
      }
      setReviewStatus('approved');
      removePendingRun(run.run_id);
      onApproved?.(run);
    } catch (e) {
      setReviewStatus('pending');
      addPendingRun(run);
      setRevisionError(e instanceof Error ? e.message : 'Could not schedule this Facebook post.');
    } finally {
      setPublishing(false);
    }
  };

  const handleApproveAndPublish = async () => {
    setPublishing(true);
    setRevisionError(null);
    try {
      const overrides = attachedImage ? {
        drive_file_id: attachedImage.id,
        drive_file_mime: attachedImage.mimeType,
        drive_file_name: attachedImage.name,
        _image_swapped: true,
      } : undefined;
      const resp = await api.executeRunAction(run.run_id, 'publish', { confirm: true, overrides });
      addPendingRun(resp.action_run);
      window.dispatchEvent(new CustomEvent('bos:focus-artifact', { detail: resp.action_run }));
      if (actionRunFailed(resp.action_run)) {
        setReviewStatus('pending');
        addPendingRun(run);
        throw new Error(actionRunError(resp.action_run));
      }
      setReviewStatus('approved');
      setModifying(false);
      removePendingRun(run.run_id);
      onApproved?.(run);
    } catch (e) {
      setReviewStatus('pending');
      addPendingRun(run);
      setRevisionError(e instanceof Error ? e.message : 'Could not publish this artifact.');
    } finally {
      setPublishing(false);
    }
  };

  const handleSaveDraft = () => {
    setReviewStatus('draft');
    setModifying(false);
    removePendingRun(run.run_id);
  };

  const handleDelete = () => {
    if (!window.confirm('Delete this artifact permanently? This cannot be undone.')) return;
    setReviewStatus('deleted');
    setModifying(false);
    removePendingRun(run.run_id);
    onDeleted?.(run);
    api.deleteRun(run.run_id).catch(() => {});
  };

  const loadDrivePickerFolder = useCallback(async (mediaType: string, folder?: DriveFolder | null, stack?: DriveFolder[], searchOverride?: string) => {
    setDriveError(null);
    setDriveFiles([]);
    setDriveFolders([]);
    setDriveLoading(true);
    try {
      const brandId = artifactBrandId;
      if (!brandId) {
        setDriveError('No artifact brand — select a brand or open a brand-scoped artifact first.');
        return;
      }
      const foldersRes = await api.listDriveFolders(brandId, folder?.id);
      const currentFolder = folder || {
        id: (foldersRes as any).folder_id || 'root',
        name: (foldersRes as any).folder_name || 'Drive',
      };
      const query = searchOverride !== undefined ? searchOverride : driveSearch;
      const filesRes = await api.listDriveImages(brandId, currentFolder.id, mediaType, query.trim() || undefined);
      setDriveCurrentFolder(currentFolder);
      setDriveFolderStack(stack || []);
      setDriveFolders(foldersRes.folders || []);
      setDriveFiles(filesRes.files || []);
    } catch (e) {
      setDriveError(e instanceof Error ? e.message : 'Could not load Drive files.');
    } finally {
      setDriveLoading(false);
    }
  }, [artifactBrandId, driveSearch]);

  const openDrivePicker = useCallback(async (mediaType?: string) => {
    const mt = mediaType || 'image';
    setDrivePickerOpen(true);
    setDrivePickerMediaType(mt);
    setDriveSearch('');
    await loadDrivePickerFolder(mt, null, [], '');
  }, [loadDrivePickerFolder]);

  const driveFileToRevisionReference = (file: DriveFile): ChatReference => ({
    kind: DOC_MIMES_SET.has(file.mimeType) ? 'document' : 'image',
    source: 'google_drive',
    title: file.name,
    drive_file_id: file.id,
    drive_file_name: file.name,
    drive_web_view_link: file.webViewLink,
    mime_type: file.mimeType,
    thumbnail_link: file.thumbnailLink,
  });

  const uploadedReferenceToDriveFile = (ref: ChatReference): DriveFile | null => {
    const id = ref.drive_file_id || ref.id;
    if (!id) return null;
    return {
      id,
      name: ref.drive_file_name || ref.title || 'Attachment',
      mimeType: ref.mime_type || 'application/octet-stream',
      webViewLink: ref.drive_web_view_link,
      thumbnailLink: ref.thumbnail_link,
    };
  };

  const openTemplateModalForDriveAsset = useCallback(async (asset: { driveFileId: string; name: string; mimeType?: string; webViewLink?: string }, defaults?: { format?: string; contentType?: string }) => {
    if (!artifactBrandId) {
      setTemplateError('No artifact brand — open a brand-scoped artifact before saving a template.');
      return;
    }
    if (!asset.driveFileId) {
      setTemplateError('This asset is missing a Drive file id and cannot be saved as a template.');
      return;
    }
    setTemplateError(null);
    setTemplateNotice(null);
    try {
      const resources = await api.getBrandKitResources(artifactBrandId);
      const existing = (resources.template_manifest?.templates || []).find((tmpl: any) => {
        const sourceId = String(tmpl?.source?.drive_file_id || tmpl?.source_drive_file_id || '');
        return sourceId === asset.driveFileId;
      }) as any;
      setTemplateSource({
        driveFileId: asset.driveFileId,
        name: asset.name,
        mimeType: asset.mimeType,
        webViewLink: asset.webViewLink,
        existingTemplateId: existing?.id || null,
        existingStatus: existing?.status || null,
      });
      setTemplateNameDraft(String(existing?.name || templateNameFromAssetName(asset.name)));
      setTemplateFormatDraft(templateFormatForValue(String(existing?.format || defaults?.format || 'square_feed')));
      setTemplateContentTypeDraft(String(existing?.content_type || defaults?.contentType || 'promo'));
      setTemplateModalOpen(true);
    } catch (e) {
      setTemplateError(e instanceof Error ? e.message : 'Could not load Brand Kit templates for this brand.');
    }
  }, [artifactBrandId]);

  const openTemplateModalForReference = useCallback((ref: ChatReference) => {
    const driveFile = uploadedReferenceToDriveFile(ref);
    if (!driveFile || !(driveFile.mimeType || '').startsWith('image/')) {
      setTemplateError('Only image references can be saved as templates.');
      return;
    }
    void openTemplateModalForDriveAsset({
      driveFileId: driveFile.id,
      name: driveFile.name,
      mimeType: driveFile.mimeType,
      webViewLink: driveFile.webViewLink,
    }, {
      format: (result.block as any)?.post_format || 'square_feed',
      contentType: (result.block as any)?.template_type || 'promo',
    });
  }, [openTemplateModalForDriveAsset, result.block]);

  const openTemplateModalForGeneratedArtifact = useCallback(() => {
    const b = (result.block || {}) as any;
    const driveFileId = String(b.drive_file_id || '').trim();
    if (!driveFileId) {
      setTemplateError('This generated artifact does not have a durable Drive file yet, so it cannot be saved as a template.');
      return;
    }
    void openTemplateModalForDriveAsset({
      driveFileId,
      name: String(b.drive_file_name || b.title || b.headline || 'Generated artifact template'),
      mimeType: String(b.drive_file_mime || b.mime_type || 'image/png'),
      webViewLink: String(b.drive_web_view_link || ''),
    }, {
      format: b.post_format || 'square_feed',
      contentType: b.template_type || 'promo',
    });
  }, [openTemplateModalForDriveAsset, result.block]);

  const handleTemplateSave = useCallback(async () => {
    if (!artifactBrandId || !templateSource) {
      setTemplateError('Missing brand or template source.');
      return;
    }
    const name = templateNameDraft.trim();
    if (!name) {
      setTemplateError('Template name is required.');
      return;
    }
    setTemplateSaving(true);
    setTemplateError(null);
    setTemplateNotice(null);
    try {
      if (templateSource.existingTemplateId) {
        await api.updateBrandKitTemplate(artifactBrandId, templateSource.existingTemplateId, {
          name,
          format: templateFormatDraft,
          content_type: templateContentTypeDraft,
          renderer: 'postcraft',
          source: {
            provider: 'google_drive',
            drive_file_id: templateSource.driveFileId,
            web_view_link: templateSource.webViewLink,
          },
        });
        setTemplateNotice(`Updated template draft: ${name}`);
      } else {
        await api.bulkUpdateBrandKitTemplates(artifactBrandId, {
          templates: [{
            name,
            status: 'draft',
            renderer: 'postcraft',
            format: templateFormatDraft,
            content_type: templateContentTypeDraft,
            required_slots: ['headline', 'logo'],
            optional_slots: ['cta'],
            copy_density: 'medium',
            source: {
              provider: 'google_drive',
              drive_file_id: templateSource.driveFileId,
              web_view_link: templateSource.webViewLink,
            },
          }],
        });
        setTemplateNotice(`Saved template draft: ${name}`);
      }
      setTemplateModalOpen(false);
    } catch (e) {
      setTemplateError(e instanceof Error ? e.message : 'Could not save this template draft.');
    } finally {
      setTemplateSaving(false);
    }
  }, [artifactBrandId, templateContentTypeDraft, templateFormatDraft, templateNameDraft, templateSource]);

  const triggerLocalUpload = (mediaType?: string) => {
    if (mediaType) setDrivePickerMediaType(mediaType);
    setDriveError(null);
    uploadInputRef.current?.click();
  };

  const uploadLocalFiles = async (files: File[], mediaType: DriveMediaKind = drivePickerMediaType as DriveMediaKind) => {
    if (!files.length) return;
    if (!artifactBrandId) {
      setDriveError('No artifact brand — select a brand or open a brand-scoped artifact first.');
      return;
    }
    if (mediaType === 'video') {
      setDriveError('Desktop upload is currently supported for image/document attachments only.');
      return;
    }
    const acceptedFiles = mediaType === 'all' ? files : files.filter(file => file.type.startsWith('image/'));
    if (!acceptedFiles.length) {
      setDriveError('Please choose an image file for this attachment.');
      return;
    }
    setAttaching(true);
    setDriveError(null);
    try {
      if (mediaType === 'all') {
        const uploadedRefs: ChatReference[] = [];
        for (const file of acceptedFiles) uploadedRefs.push(await api.uploadDriveAttachment(artifactBrandId, file));
        setRevisionReferences(prev => {
          const next = [...prev];
          for (const uploaded of uploadedRefs) {
            if (!next.some(ref => ref.drive_file_id === uploaded.drive_file_id)) next.push(uploaded);
          }
          return next;
        });
        setDrivePickerOpen(false);
        return;
      }
      const uploaded = await api.uploadDriveAttachment(artifactBrandId, acceptedFiles[0]);
      const mapped = uploadedReferenceToDriveFile(uploaded);
      if (!mapped) throw new Error('Uploaded attachment is missing a Drive file id.');
      if (isCreativePost || isImageAsset) {
        setSwappedAttachment(mapped);
        setDrivePickerOpen(false);
        return;
      }
      setAttachedImage(mapped);
      setDrivePickerOpen(false);
      api.attachImageToRun(run.run_id, mapped.id, mapped.name, mapped.mimeType)
        .catch(e => setDriveError(e instanceof Error ? e.message : 'Could not persist attached image.'));
    } catch (e) {
      setDriveError(e instanceof Error ? e.message : 'Could not upload attachment.');
    } finally {
      setAttaching(false);
    }
  };

  const handleLocalAttachmentUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    e.target.value = '';
    await uploadLocalFiles(files);
  };

  const handleDragOver = (e: React.DragEvent<HTMLElement>, target: 'revision' | 'modal') => {
    if (attaching || revisionBusy || !dataTransferHasFiles(e.dataTransfer)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    setDragTarget(target);
  };

  const handleDragLeave = (target: 'revision' | 'modal') => {
    setDragTarget(current => current === target ? null : current);
  };

  const handleDropFiles = async (e: React.DragEvent<HTMLElement>, target: 'revision' | 'modal', mediaType?: DriveMediaKind) => {
    if (!dataTransferHasFiles(e.dataTransfer)) return;
    e.preventDefault();
    setDragTarget(current => current === target ? null : current);
    if (attaching || revisionBusy) return;
    await uploadLocalFiles(Array.from(e.dataTransfer.files || []), mediaType || (drivePickerMediaType as DriveMediaKind));
  };

  const selectDriveImage = async (file: DriveFile) => {
    if (drivePickerMediaType === 'all' || (modifying && !revision && isPostcraftImage)) {
      if (file.mimeType?.startsWith('image/')) {
        setRevisionReferences(prev => prev.some(ref => ref.drive_file_id === file.id) ? prev : [...prev, driveFileToRevisionReference(file)]);
      }
      setDrivePickerOpen(false);
      return;
    }
    if (isShortformVideo) {
      setSwappedVideo(file);
      setDrivePickerOpen(false);
      return;
    }
    if (isCreativePost || isImageAsset) {
      setSwappedAttachment(file);
      setDrivePickerOpen(false);
      return;
    }
    setDriveError(null);
    setAttachedImage(file);
    setDrivePickerOpen(false);
    api.attachImageToRun(run.run_id, file.id, file.name, file.mimeType)
      .catch(e => setDriveError(e instanceof Error ? e.message : 'Could not persist attached image.'));
  };

  const handleRevisionSubmit = async () => {
    const note = feedback.trim() || 'Make this draft stronger, clearer, and more conversion-focused while preserving the original intent.';
    const isVideoRevision = isShortformVideo || moduleId.includes('storyboard.motion') || result.block?.type === 'video_asset';
    const isImageRevision = isImageAsset || isImprintAsset || moduleId.includes('imprint.generate') || moduleId.includes('imprint');
    const revisionKindLabel = isVideoRevision ? 'Video' : (isImageRevision ? 'Image' : 'Artifact');
    const statusId = `artifact-revision-${run.run_id}`;
    setRevisionBusy(true);
    setRevisionError(null);
    signalPipelineStatus({
      id: statusId,
      label: `${revisionKindLabel} revision in progress`,
      detail: isVideoRevision
        ? 'BOS is processing the requested video edit. This can take a few minutes; the revised video will appear as a new Needs approval artifact.'
        : (isImageRevision
          ? 'BOS is regenerating the image with your requested changes. The revised image will appear as a new Needs approval artifact.'
          : 'BOS is applying your requested changes. The revised artifact will appear as a new Needs approval item.'),
      status: 'running',
    });
    addPendingRun({ ...run, approval_status: 'pending' } as RunResponse);
    try {
      // Send only the operator's revision note. The backend loads the original
      // artifact/spec by run_id; sending serialized artifact JSON here made
      // storyboard/image revisions slow and could exceed provider prompt limits.
      const history = [
        ...revisionHistory,
        ...localRevisionHistory,
      ];
      let revised: RunResponse | undefined;
      let revisionReply = '';
      const blockType = String(result.block?.type || '');
      const legacyType = String((result.block as any)?.legacy_type || '');
      if (moduleId.includes('postcraft') || blockType === 'postcraft_draft') {
        const resp = await api.revisePostcraftRun(run.run_id, { feedback: note, references: revisionReferences });
        revised = resp.action_run;
        revisionReply = 'Processing your Postcraft revision. The revised image will appear as a new Needs approval artifact.';
      } else if (moduleId.includes('storyboard.motion')) {
        const resp = await api.revisePrevisVideo(run.run_id, { feedback: note, references: revisionReferences });
        revised = resp.action_run;
        revisionReply = 'Processing your Previs Motion revision. The revised video will appear as a new Needs approval artifact.';
      } else if (moduleId.includes('storyboard') || blockType === 'storyboard_json' || legacyType === 'storyboard_image') {
        const resp = await api.reviseStoryboardRun(run.run_id, { feedback: note, references: revisionReferences });
        revised = resp.action_run;
        revisionReply = 'Processing your Storyboard revision. The revised artifact will appear as a new Needs approval item.';
      } else {
        const resp = await api.chatReviseRun(run.run_id, note, history, revisionReferences);
        revised = resp.runs?.[0] || resp.run;
        revisionReply = resp.reply;
      }
      if (!revised) throw new Error('The revision endpoint did not return a revised draft.');
      if (actionRunFailed(revised)) {
        addPendingRun(revised);
        window.dispatchEvent(new CustomEvent('bos:focus-artifact', { detail: revised }));
        throw new Error(actionRunError(revised));
      }
      setRevisionReply(revisionReply);
      setLocalRevisionHistory(prev => [
        ...prev,
        { role: 'user', text: `Revise this ${platformLabel} draft: ${note}` },
        { role: 'ai', text: revisionReply },
      ]);
      if (onRevision) {
        onRevision(revisionReply, revised, run.run_id);
      } else {
        setRevision(revised);
      }
      addPendingRun(revised);
      window.dispatchEvent(new CustomEvent('bos:focus-artifact', { detail: revised }));
      signalPipelineStatus({
        id: statusId,
        label: `${revisionKindLabel} revision ready`,
        detail: isImageRevision ? 'A revised image artifact was added for review.' : 'A revised artifact was added for review.',
        status: 'done',
      });
      removePendingRun(run.run_id);
      setReviewStatus('pending');
      setModifying(false);
      setFeedback('');
      setRevisionReferences([]);
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Could not create a revision.';
      signalPipelineStatus({
        id: statusId,
        label: `${revisionKindLabel} revision failed`,
        detail: message,
        status: 'failed',
      });
      addPendingRun(run);
      setRevisionError(message);
    } finally {
      setRevisionBusy(false);
    }
  };

  const renderPreview = () => {
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
    const blockType = result.block?.type as string | undefined;

    if (blockType === 'setup_blocker' || (result.block as any)?.reason_code === 'postcraft_preflight_failed') {
      const b = (result.block || {}) as any;
      const items = Array.isArray(b.preflight_checklist) ? b.preflight_checklist : [];
      return (
        <div style={{ padding: '20px', textAlign: 'left', color: '#7f1d1d', fontSize: 13, border: '1px solid #fecaca', borderRadius: 14, background: '#fef2f2', maxWidth: 620 }}>
          <div style={{ fontWeight: 900, fontSize: 16, marginBottom: 6 }}>Setup needed before Postcraft can run</div>
          <div style={{ lineHeight: 1.5, marginBottom: 12 }}>{b.message || result.content || 'Postcraft is missing required brand/campaign setup.'}</div>
          {items.length > 0 && (
            <div style={{ display: 'grid', gap: 8 }}>
              {items.map((item: any, idx: number) => {
                const brandBase = run.brand_id ? `/admin/brands/${run.brand_id}` : '/admin/brands';
                const key = String(item.key || 'setup');
                const fallbackHref = key.includes('campaign')
                  ? '/admin/campaigns'
                  : key.includes('logo') || key.includes('drive')
                    ? `${brandBase}?tab=integrations`
                    : `${brandBase}?tab=brand-kit`;
                const fallbackLabel = key.includes('campaign')
                  ? 'Open Campaigns'
                  : key.includes('logo') || key.includes('drive')
                    ? 'Open Drive Source'
                    : 'Open Brand Kit';
                return (
                  <div key={`${item.key || idx}`} style={{ padding: 10, border: '1px solid #fecaca', borderRadius: 10, background: '#fff', display: 'flex', gap: 10, alignItems: 'flex-start', justifyContent: 'space-between' }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 800, color: '#991b1b', marginBottom: 2 }}>{key.replace(/_/g, ' ')}</div>
                      <div style={{ color: '#4b5563', lineHeight: 1.45 }}>{item.fix || 'Complete this setup item.'}</div>
                    </div>
                    <a href={item.href || fallbackHref} className="artifact-btn primary" style={{ flexShrink: 0, textDecoration: 'none' }}>
                      {item.label || fallbackLabel}
                    </a>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      );
    }

    if (blockType === 'gbp_completeness_result') {
      const b = result.block as any;
      if (b.status === 'failed' || b.error) {
        return (
          <div style={{ padding: '22px', textAlign: 'left', color: '#7f1d1d', fontSize: 13, border: '1px solid #fecaca', borderRadius: 14, background: '#fef2f2', maxWidth: 560 }}>
            <div style={{ fontWeight: 900, fontSize: 16, marginBottom: 6 }}>Google Business Profile not connected</div>
            <div style={{ lineHeight: 1.5 }}>{b.error || result.content || 'Connect Google Business Profile in Admin → Brands.'}</div>
          </div>
        );
      }
      const fields: any[] = Array.isArray(b.fields) ? b.fields : [];
      return (
        <div style={{ padding: '20px', textAlign: 'left', color: '#1f2937', fontSize: 13, border: '1px solid #dbeafe', borderRadius: 14, maxWidth: 560, background: '#eff6ff' }}>
          <div style={{ color: '#1d4ed8', fontSize: 11, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 8 }}>Google Business Profile audit</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 12 }}>
            <span style={{ fontSize: 36, fontWeight: 900 }}>{b.score ?? 0}</span>
            <span style={{ fontWeight: 800 }}>{b.rating || 'Unscored'}</span>
            {b.raw_score != null && <span style={{ color: '#6b7280' }}>{b.raw_score}/{b.max_score || 16} pts</span>}
          </div>
          {b.business_name && <div style={{ marginBottom: 10 }}><strong>Business:</strong> {b.business_name}</div>}
          {fields.map((field, idx) => (
            <div key={idx} style={{ padding: '8px 0', borderTop: idx ? '1px solid #bfdbfe' : 'none' }}>
              <div><strong>{field.name}</strong> · {field.status}{field.points != null ? ` · ${field.points} pt${field.points === 1 ? '' : 's'}` : ''}</div>
              {field.note && <div style={{ color: '#4b5563', fontSize: 12, marginTop: 2 }}>{field.note}</div>}
            </div>
          ))}
          {b.note && <div style={{ marginTop: 10, color: '#6b7280', fontSize: 11 }}>{b.note}</div>}
        </div>
      );
    }

    if (blockType === 'storyboard_json' || moduleId.includes('storyboard.create') || (moduleId.includes('storyboard') && String(result.content || '').includes('Spec JSON:'))) {
      const b = (result.block || {}) as any;
      const raw = b.storyboard_text || b.body_markdown || b.message || result.content || 'Storyboard text unavailable.';
      const text = String(raw).split('\n---\nReview/revise')[0].split('\n---\nRender was held')[0].trim();
      const isBlueprint = b.artifact_kind === 'video_production_blueprint';
      const reviewNote = isBlueprint ? (b.review_note || '15-second hard cap: full story arc + CTA must fit within 15 seconds max.') : '';
      return (
        <div style={{ padding: '18px 20px', fontSize: 13, color: '#1f2937', maxWidth: 720, border: '1px solid #e5e7eb', borderRadius: 12, background: '#fff' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', marginBottom: 10 }}>
            <div style={{ fontSize: 11, color: '#6b7280', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em' }}>{isBlueprint ? 'Video production blueprint' : 'Text storyboard'}</div>
            {b.storyboard_spec?.project?.aspect_ratio && <div style={{ fontSize: 11, color: '#6b7280' }}>{b.storyboard_spec.project.aspect_ratio}</div>}
          </div>
          {reviewNote && <div style={{ marginBottom: 10, padding: '8px 10px', borderRadius: 8, background: '#fff7ed', color: '#9a3412', fontSize: 12, fontWeight: 600 }}>{reviewNote}</div>}
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', lineHeight: 1.55, fontFamily: 'inherit' }}>{text}</pre>
        </div>
      );
    }

    if (blockType === 'imprint_draft' || moduleId.includes('imprint.draft')) {
      const b = (result.block || {}) as any;
      const text = b.message || result.content || 'Creative copy unavailable.';
      return (
        <div style={{ padding: '20px 24px', fontSize: 14, color: '#1f2937', maxWidth: 400, border: '1px solid #e5e7eb', borderRadius: 12, background: '#fff', lineHeight: 1.45 }}>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{String(text).split('\nTap Approve')[0].trim()}</pre>
        </div>
      );
    }

    if (blockType === 'imprint_asset') {
      const b = (result.block || {}) as any;
      const imageB64 = b.image_data_b64;
      const headline = b.headline || '';
      const subheadline = b.subheadline || '';
      const bodyText = b.body || '';
      const ctaText = b.cta_text || '';
      const suppressCopyPreview = Boolean(b.suppress_copy_text_preview || b.copy_embedded_in_image);
      const imageSource = b.image_source || 'generated';
      const logoApplied = b.logo_applied;
      // Imprint review cards are final creative proofs; do not show a visible
      // "AI generated" badge on the client-facing artifact surface. Audit flags
      // remain in block metadata/system details.
      const aiGenerated = false;
      const templateLabel = b.template_used_label || b.selected_drive_template?.template_used_label || b.template_used?.template_used_label;
      const src = swappedAttachment ? driveThumbnailUrl(swappedAttachment.id) : (imageB64 ? `data:${b.mime_type || 'image/png'};base64,${imageB64}` : null);
      return (
        <DriveSwapContainer kind="image" selectedFile={swappedAttachment} onSwap={() => openDrivePicker('image')} onClear={() => setSwappedAttachment(null)}>
          <div style={{ maxWidth: 400, border: '1px solid #e5e7eb', borderRadius: 12, background: '#fff', overflow: 'hidden' }}>
            {src ? (
              <img src={src} alt={headline || 'Imprint image'} style={{ width: '100%', display: 'block' }} />
            ) : (
              <div style={{ minHeight: 220, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 13 }}>Image preview unavailable</div>
            )}
            {!suppressCopyPreview && (
              <div style={{ padding: '16px 18px', lineHeight: 1.4 }}>
                {headline && <div style={{ fontSize: 17, fontWeight: 700, color: '#111827', marginBottom: 4 }}>{headline}</div>}
                {subheadline && <div style={{ fontSize: 13, color: '#4b5563', marginBottom: 6 }}>{subheadline}</div>}
                {bodyText && <div style={{ fontSize: 13, color: '#374151', marginBottom: 10 }}>{bodyText}</div>}
                {ctaText && <div style={{ display: 'inline-block', padding: '6px 16px', background: '#111827', color: '#fff', borderRadius: 6, fontSize: 12, fontWeight: 600 }}>{ctaText}</div>}
              </div>
            )}
            <div style={{ padding: '8px 18px 12px', fontSize: 11, color: '#9ca3af', borderTop: '1px solid #f3f4f6', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {imageSource === 'operator_attached' && <span>📎 Operator image</span>}
              {aiGenerated && <span>🤖 AI generated</span>}
              {logoApplied && <span title={b.logo_application_status || 'overlay_applied'}>🔷 Logo overlay applied</span>}
              {templateLabel && <span>{templateLabel}</span>}
            </div>
          </div>
        </DriveSwapContainer>
      );
    }

    if (blockType === 'fb_page_post_draft') {
      const message = result.block.message || result.content || 'Post text missing';
      const pageName = result.block.page_name || brandName;
      return (
        <div style={{ fontFamily: 'Segoe UI, Helvetica, Arial, sans-serif', maxWidth: 500, border: '1px solid #ddd', borderRadius: 8, overflow: 'hidden', backgroundColor: '#fff' }}>
          <div style={{ display: 'flex', padding: '12px', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 40, height: 40, borderRadius: '50%', backgroundColor: '#eee', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 'bold', color: '#888' }}>
              {pageName[0]}
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#050505' }}>{pageName}</div>
              <div style={{ fontSize: 12, color: '#65676b' }}>Draft · 🌐</div>
            </div>
          </div>
          <div style={{ padding: '0 12px 16px', fontSize: 14, color: '#050505', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
            {message}
          </div>
          {attachedImage && (
            <div style={{ margin: '0 12px 12px', padding: '8px 12px', background: '#f0fdf4', borderRadius: 6, border: '1px solid #bbf7d0', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
              <span style={{ fontSize: 16 }}>🖼</span>
              <span style={{ fontWeight: 600, color: '#166534' }}>Image attached:</span>
              <span style={{ color: '#374151' }}>{attachedImage.name}</span>
              <button style={{ marginLeft: 'auto', fontSize: 11, color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer' }} onClick={() => setAttachedImage(null)}>Remove</button>
            </div>
          )}
        </div>
      );
    }

    if (blockType === 'fb_page_post_result') {
      const b = result.block as any;
      const scheduled = b.status === 'scheduled';
      const succeeded = b.status === 'succeeded' || scheduled;
      const apiDetail = b.details?.response || b.details?.error || '';
      const previewText = sanitizeArtifactPreviewText(b.message_preview || b.message || result.content || '');
      return (
        <div style={{ padding: '18px 20px', fontSize: 13, color: '#1f2937', maxWidth: 520, border: '1px solid #e5e7eb', borderRadius: 12, background: succeeded ? '#f0fdf4' : '#fef2f2' }}>
          <div style={{ fontWeight: 800, fontSize: 15, marginBottom: 8 }}>{scheduled ? 'Facebook post scheduled' : (succeeded ? 'Facebook post published' : 'Facebook publish failed')}</div>
          {previewText && <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.45, marginBottom: 10 }}>{previewText}</div>}
          {scheduled && b.scheduled_at && <div style={{ color: '#166534', fontSize: 12, marginBottom: 6 }}>Scheduled for: {b.scheduled_at}</div>}
          {!succeeded && b.message && <div style={{ color: '#b91c1c', fontSize: 12, marginBottom: 6 }}>{b.message}</div>}
          {!succeeded && apiDetail && (
            <details style={{ marginBottom: 8 }}>
              <summary style={{ color: '#6b7280', fontSize: 11, cursor: 'pointer' }}>Graph API response</summary>
              <pre style={{ marginTop: 6, padding: 8, background: '#fff', borderRadius: 6, fontSize: 11, overflowX: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: '#374151' }}>{typeof apiDetail === 'string' ? apiDetail : JSON.stringify(apiDetail, null, 2)}</pre>
            </details>
          )}
          {b.post_id && <div style={{ color: '#6b7280', fontSize: 12, marginBottom: 6 }}>Post ID: {b.post_id}</div>}
          {b.permalink && <a href={b.permalink} target="_blank" rel="noreferrer" style={{ color: '#2563eb', fontWeight: 700 }}>View on Facebook →</a>}
        </div>
      );
    }

    if (blockType === 'fb_page_video_result') {
      const b = result.block as any;
      const succeeded = b.status === 'succeeded';
      const apiDetail = b.details?.response || b.details?.error || '';
      return (
        <div style={{ padding: '18px 20px', fontSize: 13, color: '#1f2937', maxWidth: 520, border: '1px solid #e5e7eb', borderRadius: 12, background: succeeded ? '#f0fdf4' : '#fef2f2' }}>
          <div style={{ fontWeight: 800, fontSize: 15, marginBottom: 8 }}>{succeeded ? 'Facebook video published' : 'Facebook video publish failed'}</div>
          <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.45, marginBottom: 10 }}>{b.description_preview || b.message || result.content}</div>
          {!succeeded && b.message && <div style={{ color: '#b91c1c', fontSize: 12, marginBottom: 6 }}>{b.message}</div>}
          {!succeeded && apiDetail && (
            <details style={{ marginBottom: 8 }}>
              <summary style={{ color: '#6b7280', fontSize: 11, cursor: 'pointer' }}>Graph API response</summary>
              <pre style={{ marginTop: 6, padding: 8, background: '#fff', borderRadius: 6, fontSize: 11, overflowX: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: '#374151' }}>{typeof apiDetail === 'string' ? apiDetail : JSON.stringify(apiDetail, null, 2)}</pre>
            </details>
          )}
          {b.video_id && <div style={{ color: '#6b7280', fontSize: 12, marginBottom: 6 }}>Video ID: {b.video_id}</div>}
          {b.permalink && <a href={b.permalink} target="_blank" rel="noreferrer" style={{ color: '#2563eb', fontWeight: 700 }}>View on Facebook →</a>}
        </div>
      );
    }

    if (blockType === 'meta_page_insights_report') {
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
        <div style={{ padding: '16px 20px', fontSize: 13, color: '#1f2937', maxWidth: 680 }}>
          <div style={{ color: '#1d4ed8', fontSize: 11, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 6 }}>Read-only Meta insight artifact · {coverageLabel}</div>
          <div style={{ fontWeight: 800, fontSize: 16, marginBottom: 4 }}>Meta Page Insights · {page.name || brandName}</div>
          <div style={{ color: '#6b7280', fontSize: 12, marginBottom: 12 }}>
            {page.category || 'Facebook Page'}{page.followers != null ? ` · ${Number(page.followers).toLocaleString()} followers` : ''}{b.report_scope ? ` · ${String(b.report_scope).replace(/_/g, ' ')}` : ''}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 8, marginBottom: 14 }}>
            <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 10 }}><div style={{ color: '#6b7280', fontSize: 11 }}>Scheduled</div><div style={{ fontWeight: 800 }}>{metrics.scheduled_posts ?? scheduledPosts.length}</div></div>
            <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 10 }}><div style={{ color: '#6b7280', fontSize: 11 }}>Recent posts</div><div style={{ fontWeight: 800 }}>{metrics.recent_posts ?? recentPosts.length}</div></div>
            <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 10 }}><div style={{ color: '#6b7280', fontSize: 11 }}>Insight metrics</div><div style={{ fontWeight: 800 }}>{metrics.insight_metrics_reported ?? insights.length}</div></div>
            <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 10 }}><div style={{ color: '#6b7280', fontSize: 11 }}>Engagement rows</div><div style={{ fontWeight: 800 }}>{metrics.recent_posts_with_engagement_counts ?? 0}</div></div>
          </div>
          {insightBullets.length > 0 && <div style={{ marginBottom: 12 }}>
            <div style={{ fontWeight: 800, marginBottom: 6 }}>{b.insight_heading || 'Campaign insights'}</div>
            <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.45 }}>
              {insightBullets.slice(0, 5).map((item: any, i: number) => <li key={i} style={{ marginBottom: 8 }}><strong>{item.insight}</strong>{item.why_it_matters ? <span style={{ color: '#4b5563' }}> — {item.why_it_matters}</span> : null}<div style={{ color: '#6b7280', fontSize: 11 }}>{item.confidence || 'unknown'} confidence · {item.coverage || 'coverage unknown'}</div></li>)}
            </ul>
          </div>}
          {insights.length > 0 && <details style={{ marginBottom: 12 }}>
            <summary style={{ fontWeight: 700, cursor: 'pointer' }}>Metrics overview</summary>
            {insights.slice(0, 8).map((m: any, i: number) => <div key={m.name || i} style={{ display: 'flex', justifyContent: 'space-between', borderTop: i ? '1px solid #f3f4f6' : 'none', padding: '6px 0' }}><span>{m.title || m.name}</span><strong>{String(m.total ?? m.latest ?? '—')}</strong></div>)}
          </details>}
          {notAvailable.length > 0 && <div style={{ color: '#92400e', fontSize: 12, marginBottom: 8 }}><strong>Not available yet:</strong> {notAvailable.slice(0, 4).join(' · ')}</div>}
          {b.recommended_next_step && <div style={{ fontWeight: 700, marginBottom: 8 }}>Next: {b.recommended_next_step}</div>}
          {warnings.length > 0 && <details style={{ marginTop: 8 }}>
            <summary style={{ color: '#92400e', cursor: 'pointer', fontWeight: 700 }}>Warnings / permission limits ({warnings.length})</summary>
            <div style={{ marginTop: 8, display: 'grid', gap: 6 }}>{warnings.slice(0, 6).map((w: any, i: number) => <div key={i} style={{ color: '#6b7280', fontSize: 12 }}>{w.scope}: {String(w.message || '').slice(0, 220)}</div>)}</div>
          </details>}
        </div>
      );
    }

    if (blockType === 'meta_page_posts') {
      const b = result.block as any;
      if (b.status === 'failed') {
        return (
          <div style={{ padding: 24, textAlign: 'center', color: '#6b7280', fontSize: 13 }}>
            <div style={{ fontSize: 28, marginBottom: 8 }}>⚠</div>
            <div style={{ color: '#ef4444', fontWeight: 600, marginBottom: 6 }}>Facebook not connected</div>
            <div>{b.message || result.content}</div>
          </div>
        );
      }
      const posts: any[] = b.posts || [];
      return (
        <div style={{ padding: '16px 20px', fontSize: 13, color: '#1f2937', maxWidth: 520 }}>
          <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 12 }}>Recent Posts · {b.page_name || brandName}</div>
          {posts.length === 0 ? (
            <div style={{ color: '#6b7280' }}>No posts found on this page.</div>
          ) : posts.slice(0, 10).map((p: any, i: number) => (
            <div key={p.post_id || i} style={{ padding: '10px 0', borderTop: i ? '1px solid #f3f4f6' : 'none' }}>
              <div style={{ color: '#6b7280', fontSize: 11, marginBottom: 4 }}>{(p.created_time || '').slice(0, 10)}</div>
              <div style={{ lineHeight: 1.45, marginBottom: 6 }}>{p.message ? (p.message.length > 160 ? p.message.slice(0, 160) + '…' : p.message) : '(no text)'}</div>
              <div style={{ color: '#6b7280', fontSize: 11 }}>❤️ {p.likes ?? 0} · 💬 {p.comments ?? 0} · ↗ {p.shares ?? 0}</div>
            </div>
          ))}
        </div>
      );
    }

    if (blockType === 'meta_page_inventory') {
      const pages: any[] = (result.block as any).pages || [];
      return (
        <div style={{ padding: '16px 20px', fontSize: 13, color: '#1f2937', maxWidth: 520 }}>
          <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 12 }}>Facebook Pages</div>
          {pages.length === 0 ? <div style={{ color: '#6b7280' }}>No pages found.</div> : pages.map((p: any, i: number) => (
            <div key={p.page_id || i} style={{ padding: '10px 0', borderTop: i ? '1px solid #f3f4f6' : 'none' }}>
              <div style={{ fontWeight: 600 }}>{p.name}</div>
              <div style={{ color: '#6b7280', fontSize: 12 }}>{p.category}{p.followers != null ? ` · ${p.followers.toLocaleString()} followers` : ''}</div>
              {p.ig_business_account_id && <div style={{ color: '#6b7280', fontSize: 11, marginTop: 2 }}>IG: {p.ig_business_account_id}</div>}
            </div>
          ))}
        </div>
      );
    }

    if (result.block?.type === 'creative_post_asset' && result.block?.status === 'succeeded') {
      const b = result.block;
      const src = swappedAttachment
        ? driveThumbnailUrl(swappedAttachment.id)
        : b.image_data_b64 ? `data:${b.mime_type || 'image/png'};base64,${b.image_data_b64}` : undefined;
      return (
        <DriveSwapContainer kind="image" selectedFile={swappedAttachment} onSwap={() => openDrivePicker('image')} onClear={() => setSwappedAttachment(null)}>
          <FacebookFeedPreview pageName={brandName} adCopy={editedCaption || b.caption || 'Caption pending'} imageUrl={src} ctaText={b.cta || 'Learn More'} />
        </DriveSwapContainer>
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
    if (result.block?.type === 'gtm_strategy') {
      const block = result.block as any;
      const stack = block.channel_stack || {};
      const doNow = Array.isArray(stack.do_now) ? stack.do_now : [];
      const hold = Array.isArray(stack.hold) ? stack.hold : [];
      const avoid = Array.isArray(stack.avoid_for_now) ? stack.avoid_for_now : [];
      const assumptions = Array.isArray(block.assumptions) ? block.assumptions : [];
      const gaps = Array.isArray(block.critical_gaps) ? block.critical_gaps : [];
      const nextArtifacts = Array.isArray(block.next_artifacts) ? block.next_artifacts : [];
      const sectionLabel: React.CSSProperties = { fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.08em', color: '#9ca3af', marginBottom: 8 };
      const divider: React.CSSProperties = { borderTop: '1px solid #f3f4f6', margin: '16px 0' };
      return (
        <div style={{ padding: '20px 24px', textAlign: 'left', color: '#1f2937', fontSize: '13px', lineHeight: 1.55 }}>
          <div style={sectionLabel}>GTM strategy</div>
          <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 10 }}>{block.title || title}</div>

          {block.best_current_motion && (
            <div style={{ marginBottom: 14 }}>
              <div style={sectionLabel}>Best motion</div>
              <div style={{ fontWeight: 500 }}>{block.best_current_motion}</div>
            </div>
          )}

          {block.why_this_motion && (
            <div style={{ marginBottom: 14 }}>
              <div style={sectionLabel}>Active objective</div>
              <div style={{ color: '#374151' }}>{block.why_this_motion}</div>
            </div>
          )}

          {block.positioning_angle && (
            <div style={{ marginBottom: 14, padding: '10px 14px', background: '#f9fafb', borderLeft: '3px solid #d1d5db', borderRadius: 4 }}>
              <span style={{ fontWeight: 600 }}>Positioning: </span>{block.positioning_angle}
            </div>
          )}

          {doNow.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={sectionLabel}>Do now</div>
              {doNow.map((ch: any, idx: number) => (
                <div key={idx} style={{ paddingTop: idx ? 10 : 0, marginTop: idx ? 10 : 0, borderTop: idx ? '1px solid #f3f4f6' : 'none' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <span style={{ fontWeight: 600 }}>{ch.channel || ch.name}</span>
                    {ch.role && <span style={{ fontSize: 11, color: '#6b7280', background: '#f3f4f6', borderRadius: 3, padding: '1px 6px' }}>{ch.role}</span>}
                  </div>
                  {(ch.rationale || ch.reason) && <div style={{ color: '#4b5563', fontSize: 12 }}>{ch.rationale || ch.reason}</div>}
                </div>
              ))}
            </div>
          )}

          {(hold.length > 0 || avoid.length > 0) && (
            <div style={{ marginBottom: 14 }}>
              {hold.length > 0 && (
                <div style={{ marginBottom: 10 }}>
                  <div style={sectionLabel}>Hold</div>
                  {hold.slice(0, 4).map((item: any, idx: number) => (
                    <div key={idx} style={{ color: '#4b5563', fontSize: 12, marginBottom: 4 }}>
                      <span style={{ fontWeight: 600, color: '#1f2937' }}>{item.name || item.channel}</span>
                      {item.reason && <span> — {item.reason}</span>}
                    </div>
                  ))}
                </div>
              )}
              {avoid.length > 0 && (
                <div>
                  <div style={sectionLabel}>Avoid for now</div>
                  {avoid.slice(0, 4).map((item: any, idx: number) => (
                    <div key={idx} style={{ color: '#4b5563', fontSize: 12, marginBottom: 4 }}>
                      <span style={{ fontWeight: 600, color: '#1f2937' }}>{item.name || item.channel}</span>
                      {item.reason && <span> — {item.reason}</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {assumptions.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={sectionLabel}>Assumptions</div>
              {assumptions.slice(0, 3).map((item: string, idx: number) => (
                <div key={idx} style={{ color: '#4b5563', fontSize: 12, marginBottom: 6 }}>{item}</div>
              ))}
            </div>
          )}

          {gaps.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={sectionLabel}>Critical gaps</div>
              {gaps.slice(0, 3).map((gap: any, idx: number) => {
                const text = gap.gap || gap.name || '';
                const short = text.length > 160 ? text.slice(0, 157) + '…' : text;
                return (
                  <div key={idx} style={{ color: '#4b5563', fontSize: 12, marginBottom: 6 }}>
                    <span style={{ color: '#9ca3af', marginRight: 4 }}>•</span>{short}
                  </div>
                );
              })}
            </div>
          )}

          {nextArtifacts.length > 0 && (
            <div>
              <div style={sectionLabel}>Next artifacts</div>
              {nextArtifacts.slice(0, 4).map((item: any, idx: number) => (
                <div key={idx} style={{ color: '#4b5563', fontSize: 12, marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, color: '#1f2937' }}>{item.name || item.artifact}</span>
                  {(item.reason || item.purpose) && <span style={{ color: '#9ca3af' }}> — {item.reason || item.purpose}</span>}
                </div>
              ))}
            </div>
          )}

          <div style={divider} />
          <div style={{ fontSize: 11, color: '#9ca3af' }}>Active objective · {brandName}</div>
        </div>
      );
    }
    if (result.block?.type === 'strategy_workflow' || moduleId.includes('strategy_workflow')) {
      const block = result.block as any;
      const thesis = (block?.components || []).find((c: any) => c.type === 'strategic_thesis')?.data || {};
      const wedge = thesis.wedge || block?.wedge || '';
      const motion = thesis.primary_motion || block?.primary_motion || '';
      const archetype = (block?.archetype || '').replace(/_/g, ' ');
      const componentCount = (block?.components || []).filter((c: any) => c.status === 'complete').length;
      return (
        <div style={{ padding: '14px 16px', fontSize: 13, color: '#1f2937', border: '1px solid #e5dccb', borderRadius: 12, background: '#fffdf8' }}>
          <div style={{ fontSize: 11, color: '#826D40', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 6 }}>Strategy Workflow{archetype ? ` · ${archetype}` : ''}</div>
          {motion && <div style={{ fontWeight: 700, marginBottom: 6 }}>{motion} motion</div>}
          {wedge && <div style={{ color: '#4b5563', lineHeight: 1.45, fontStyle: 'italic', marginBottom: 8 }}>"{wedge}"</div>}
          {componentCount > 0 && <div style={{ fontSize: 11, color: '#166534', background: '#dcfce7', borderRadius: 999, padding: '2px 8px', display: 'inline-block', fontWeight: 700 }}>{componentCount} components</div>}
        </div>
      );
    }
    if (result.block?.type === 'marketing_plan' || moduleId.includes('marketing.plan')) {
      const block = result.block || {};
      const channels = Array.isArray(block.recommended_channels) ? block.recommended_channels : [];
      const focus = Array.isArray(block.focus) ? block.focus : [];
      const notReady = Array.isArray(block.not_recommended_yet) ? block.not_recommended_yet : [];
      const missing = Array.isArray(block.missing_inputs) ? block.missing_inputs : [];
      const nextArtifacts = Array.isArray(block.next_artifacts) ? block.next_artifacts : [];
      return (
        <div style={{ padding: '20px', textAlign: 'left', color: '#1f2937', fontSize: '13px', border: '1px solid #e5e7eb', borderRadius: 14, maxWidth: 560, background: '#fff' }}>
          <div style={{ color: '#6b7280', fontSize: 11, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 8 }}>Marketing plan</div>
          <div style={{ fontWeight: 800, fontSize: 18, marginBottom: 6 }}>{block.title || title}</div>
          {block.campaign_theme && <div style={{ color: '#4b5563', marginBottom: 12 }}>{block.campaign_theme}</div>}
          {block.mission && <div style={{ lineHeight: 1.45, marginBottom: 14 }}>{block.mission}</div>}
          {focus.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>Focus</div>
              <ol style={{ margin: 0, paddingLeft: 18 }}>
                {focus.slice(0, 3).map((item: string, idx: number) => <li key={idx}>{item}</li>)}
              </ol>
            </div>
          )}
          {channels.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>Recommended channels</div>
              {channels.map((ch: any, idx: number) => (
                <div key={`${ch.channel || idx}`} style={{ padding: '8px 0', borderTop: idx ? '1px solid #f3f4f6' : 'none' }}>
                  <strong>{ch.channel || ch.name}</strong>{ch.status ? ` · ${ch.status}` : ''}
                  <div style={{ color: '#4b5563' }}>{[ch.role, ch.reason].filter(Boolean).join(' — ')}</div>
                </div>
              ))}
            </div>
          )}
          {notReady.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>Not recommended yet</div>
              {notReady.slice(0, 3).map((item: any, idx: number) => (
                <div key={idx} style={{ color: '#4b5563' }}>• {item.name || item.channel}{item.reason ? ` — ${item.reason}` : ''}</div>
              ))}
            </div>
          )}
          {missing.length > 0 && (
            <div style={{ marginBottom: nextArtifacts.length ? 14 : 0 }}>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>Missing inputs</div>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {missing.slice(0, 4).map((item: string, idx: number) => <li key={idx}>{item}</li>)}
              </ul>
            </div>
          )}
          {nextArtifacts.length > 0 && (
            <div>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>Next artifacts</div>
              {nextArtifacts.slice(0, 3).map((item: any, idx: number) => (
                <div key={idx} style={{ color: '#4b5563' }}>• {item.name}{item.reason ? ` — ${item.reason}` : ''}</div>
              ))}
            </div>
          )}
        </div>
      );
    }
    if (channel.includes('email') && moduleId.includes('plan')) {
      const md = result.content || 'Plan content unavailable.';
      const rendered = md
        .replace(/^### (.+)$/gm, '<h3 style="margin:14px 0 4px;font-size:12px;font-weight:900;text-transform:uppercase;letter-spacing:.06em;color:#555">$1</h3>')
        .replace(/^## (.+)$/gm, '<h2 style="margin:16px 0 6px;font-size:13px;font-weight:900;color:#1f2937">$1</h2>')
        .replace(/^# (.+)$/gm, '<h1 style="margin:0 0 10px;font-size:15px;font-weight:900;color:#0B3D2E">$1</h1>')
        .replace(/^\|(.+)\|$/gm, (row) => {
          const cells = row.split('|').slice(1, -1);
          const isHeader = cells.some(c => /^\s*[-:]+\s*$/.test(c));
          if (isHeader) return '';
          const tag = 'td';
          return `<tr>${cells.map(c => `<${tag} style="padding:3px 8px;border:1px solid #e5e7eb;font-size:11px">${c.trim()}</${tag}>`).join('')}</tr>`;
        })
        .replace(/(<tr>.*<\/tr>)/gs, (m) => `<table style="border-collapse:collapse;width:100%;margin:8px 0">${m}</table>`)
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/^- (.+)$/gm, '<li style="margin:2px 0">$1</li>')
        .replace(/(<li[^>]*>.*<\/li>)/gs, (m) => `<ul style="margin:6px 0;padding-left:18px">${m}</ul>`)
        .replace(/\n{2,}/g, '<br/><br/>')
        .replace(/\n/g, '<br/>');
      return (
        <div style={{ padding: '20px', textAlign: 'left', color: '#333', fontSize: '12px', border: '1px dashed #ccc', maxWidth: 520 }}>
          <div style={{ color: '#666', marginBottom: 10 }}>Email campaign plan</div>
          <div style={{ lineHeight: 1.6 }} dangerouslySetInnerHTML={{ __html: rendered }} />
        </div>
      );
    }
    if (channel.includes('email')) {
      return <EmailPreview senderName={brandName} subject={result.subject || 'Subject Missing'} preheader={result.preheader || 'Preheader missing'} body={result.content || 'Body missing'} />;
    }
    if (channel.includes('pinterest')) {
      return <PinterestPreview title={result.headline || 'Title Missing'} description={result.content || 'Description missing'} />;
    }

    if (result.block?.type === 'storyboard_image' && result.block?.status === 'failed') {
      return (
        <div style={{ padding: '20px', textAlign: 'center', color: '#ef4444', fontSize: '13px' }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>⚠</div>
          <div>{result.block.message || result.content}</div>
        </div>
      );
    }

    if (result.block?.type === 'image_asset' && result.block?.image_data_b64) {
      const { image_data_b64, mime_type, width, height } = result.block;
      const isImprint = result.block?.legacy_type === 'imprint_asset';
      const isStoryboardImageAsset = (result.block as any)?.legacy_type === 'storyboard_image';
      const artifactVersion = (result.block as any)?.artifact_version || (result.block as any)?.variation_id || '';
      const subtitle = isImprint
        ? `${result.block?.template_id || 'imprint'} · ${result.block?.engine || 'gemini'}`
        : isStoryboardImageAsset
          ? `Storyboard Image${artifactVersion ? ` ${artifactVersion}` : ''} · ${(result.block as any)?.provider || 'renderer'}${(result.block as any)?.model ? ` · ${(result.block as any).model}` : ''}`
          : '';
      const src = swappedAttachment ? driveThumbnailUrl(swappedAttachment.id) : `data:${mime_type || 'image/png'};base64,${image_data_b64}`;
      return (
        <DriveSwapContainer kind="image" selectedFile={swappedAttachment} onSwap={() => openDrivePicker('image')} onClear={() => setSwappedAttachment(null)}>
          <div style={{ textAlign: 'center', padding: '12px 0', width: '100%' }}>
            {src ? (
              <img
                src={src}
                alt={swappedAttachment?.name || (result.block as any)?.title || (result.block as any)?.headline || 'Generated image'}
                style={{ maxWidth: '100%', borderRadius: 10, display: 'block', margin: '0 auto' }}
              />
            ) : (
              <div style={{ minHeight: 220, border: '1px dashed #d1d5db', borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af' }}>Selected Drive image preview unavailable</div>
            )}
            {subtitle && !swappedAttachment && (
              <div style={{ color: '#888', fontSize: 11, marginTop: 8, fontStyle: 'italic' }}>
                {width && height ? `${width}×${height} · ` : ''}{subtitle}
              </div>
            )}
          </div>
        </DriveSwapContainer>
      );
    }

    if (result.block?.type === 'image_asset' && (result.block as any)?.asset_omitted) {
      const b = result.block as any;
      return (
        <div style={{ padding: 16, textAlign: 'center', color: '#6b7280', fontSize: 13, border: '1px dashed #d1d5db', borderRadius: 10, background: '#fff' }}>
          <div style={{ fontWeight: 800, color: '#374151', marginBottom: 4 }}>Loading generated image…</div>
          <div style={{ fontSize: 12 }}>The artifact preview was loaded without its large image payload. Open or focus the card to hydrate the full image.</div>
          {b.drive_web_view_link && <div style={{ marginTop: 8 }}><a href={b.drive_web_view_link} target="_blank" rel="noreferrer" style={{ color: '#2563eb', fontSize: 12, fontWeight: 700 }}>Open in Drive →</a></div>}
        </div>
      );
    }

    if (result.block?.type === 'clickup_task_status') {
      const b = result.block as any;
      const spaceNames: string[] = b.list_index
        ? [...new Set<string>((b.list_index as any[]).map((l: any) => l.space))]
        : [];
      const spaceTaskCounts: Record<string, number> = {};
      if (b.list_index) {
        (b.list_index as any[]).forEach((l: any) => {
          spaceTaskCounts[l.space] = (spaceTaskCounts[l.space] || 0) + (l.count || 0);
        });
      }
      const blocked: any[] = b.blocked || [];
      const overdue: any[] = b.overdue || [];
      const inProgress: any[] = b.in_progress || [];
      const hasAttention = blocked.length > 0 || overdue.length > 0;
      const buckets = [
        { label: 'Blocked', count: blocked.length, color: '#ef4444', bg: '#fef2f2' },
        { label: 'Overdue', count: overdue.length, color: '#f97316', bg: '#fff7ed' },
        { label: 'In Progress', count: inProgress.length, color: '#3b82f6', bg: '#eff6ff' },
        { label: 'To Do', count: b.todo_count || 0, color: '#6b7280', bg: '#f9fafb' },
        { label: 'Done', count: b.done_count || 0, color: '#16a34a', bg: '#f0fdf4' },
      ];
      return (
        <div style={{ padding: '16px 20px', textAlign: 'left', color: '#1f2937', fontSize: 13, maxWidth: 560 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
            <div style={{ fontWeight: 800, fontSize: 15 }}>ClickUp Workspace</div>
            <div style={{ color: '#6b7280', fontSize: 12 }}>
              {b.space_count} space{b.space_count !== 1 ? 's' : ''} · {b.list_count} lists · {b.task_count} tasks
            </div>
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
            {buckets.map(bk => (
              <div key={bk.label} style={{ background: bk.bg, border: `1px solid ${bk.color}22`, borderRadius: 8, padding: '6px 12px', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontWeight: 700, color: bk.color, fontSize: 16 }}>{bk.count}</span>
                <span style={{ color: '#374151', fontSize: 12 }}>{bk.label}</span>
              </div>
            ))}
          </div>

          {spaceNames.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 6 }}>Spaces</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {spaceNames.map(space => (
                  <div key={space} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 10px', background: '#f9fafb', borderRadius: 6, fontSize: 12 }}>
                    <span style={{ fontWeight: 600 }}>{space}</span>
                    <span style={{ color: '#6b7280' }}>{spaceTaskCounts[space] || 0} tasks</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {hasAttention && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#ef4444', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 6 }}>Needs Attention</div>
              {[...blocked.map(t => ({ ...t, _label: 'Blocked' })), ...overdue.map(t => ({ ...t, _label: 'Overdue' }))].slice(0, 6).map((t: any, i) => (
                <div key={i} style={{ padding: '6px 10px', background: '#fef2f2', borderRadius: 6, marginBottom: 4, fontSize: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontWeight: 600 }}>{t.name}</span>
                    <span style={{ color: '#ef4444', fontSize: 11 }}>{t._label}</span>
                  </div>
                  <div style={{ color: '#6b7280', fontSize: 11 }}>{[t.space, t.list].filter(Boolean).join(' › ')}{t.assignees?.length ? ` · ${t.assignees.join(', ')}` : ''}</div>
                </div>
              ))}
            </div>
          )}

          {inProgress.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#3b82f6', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 6 }}>In Progress</div>
              {inProgress.slice(0, 5).map((t: any, i) => (
                <div key={i} style={{ padding: '6px 10px', background: '#eff6ff', borderRadius: 6, marginBottom: 4, fontSize: 12 }}>
                  <span style={{ fontWeight: 600 }}>{t.name}</span>
                  <div style={{ color: '#6b7280', fontSize: 11 }}>{[t.space, t.list].filter(Boolean).join(' › ')}{t.assignees?.length ? ` · ${t.assignees.join(', ')}` : ''}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    if (result.block?.type === 'image_asset' && result.block?.status === 'failed') {
      return (
        <div style={{ padding: '20px', textAlign: 'center', color: '#ef4444', fontSize: '13px' }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>⚠</div>
          <div>{result.block.message || result.content}</div>
        </div>
      );
    }

    if (result.block?.type === 'post_image') {
      const b = result.block as any;
      const imageB64 = b.image_data_b64;
      const detectedMime = imageB64?.startsWith('/9j/') ? 'image/jpeg' : (b.mime_type || 'image/png');
      const src = swappedAttachment ? driveThumbnailUrl(swappedAttachment.id) : (imageB64 ? `data:${detectedMime};base64,${imageB64}` : null);
      return (
        <DriveSwapContainer kind="image" selectedFile={swappedAttachment} onSwap={() => openDrivePicker('image')} onClear={() => setSwappedAttachment(null)}>
          <div style={{ maxWidth: 540, border: '1px solid #e5e7eb', borderRadius: 12, background: '#fff', overflow: 'hidden' }}>
            {src ? (
              <img src={src} alt="Post image" style={{ width: '100%', display: 'block' }} />
            ) : (
              <div style={{ minHeight: 220, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 13 }}>Image preview unavailable</div>
            )}
            <div style={{ padding: '8px 18px 12px', fontSize: 11, color: '#9ca3af', borderTop: '1px solid #f3f4f6', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {b.template_type && <span>{b.template_type}</span>}
              {b.post_format && <span>{b.post_format}</span>}
              {b.drive_web_view_link && <a href={b.drive_web_view_link} target="_blank" rel="noreferrer" style={{ color: '#2563eb', fontSize: 11, fontWeight: 700 }}>Open in Drive →</a>}
            </div>
          </div>
        </DriveSwapContainer>
      );
    }

    if (result.block?.type === 'creative_shortform_video' || result.block?.type === 'video_asset') {
      const b = result.block as any;
      if (b.status !== 'succeeded') {
        return <div style={{ padding: 16, color: '#ef4444', fontSize: 13 }}>{b.message || result.content}</div>;
      }
      const proxiedVideoSrc = !swappedVideo ? localVideoSrcFromBlock(b) : undefined;
      const selectedDriveVideoLink = swappedVideo?.webViewLink || b.drive_web_view_link;
      const selectedDriveVideoName = swappedVideo?.name || b.drive_file_name || 'Drive video';
      const isRevision = moduleId.includes('video.edit') && Boolean(b.source_run_id);
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '100%' }}>
          {isRevision && (b.change_summary || b.source_run_id) && (
            <div style={{ padding: '10px 14px', background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 8, fontSize: 12 }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: '#0369a1', textTransform: 'uppercase', letterSpacing: '.1em', marginBottom: 4 }}>
                Change
              </div>
              {b.change_summary && <div style={{ color: '#1e40af', lineHeight: 1.4 }}>{b.change_summary}</div>}
              {b.source_run_id && (
                <button
                  onClick={() => window.dispatchEvent(new CustomEvent('bos:focus-artifact', { detail: { run_id: b.source_run_id } }))}
                  style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', marginTop: 6, color: '#0369a1', fontSize: 11, textDecoration: 'underline', display: 'block', textAlign: 'left' }}
                >
                  ← View source cut
                </button>
              )}
            </div>
          )}
          <DriveSwapContainer kind="video" selectedFile={swappedVideo} onSwap={() => openDrivePicker('video')} onClear={() => setSwappedVideo(null)}>
            {proxiedVideoSrc ? (
              <FacebookFeedPreview
                pageName={brandName}
                adCopy={editedHookText || b.hook_text || ''}
                videoSrc={proxiedVideoSrc}
                ctaText={editedCtaText || b.cta_text || 'Learn More'}
              />
            ) : (
              <div style={{ width: '100%', maxWidth: 540, border: '1px solid #e5e7eb', borderRadius: 12, overflow: 'hidden', background: '#fff' }}>
                <div style={{ padding: '18px 16px', textAlign: 'center', color: '#4b5563' }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#111827', marginBottom: 4 }}>{selectedDriveVideoName}</div>
                  <div style={{ fontSize: 12 }}>Video preview is stored in Drive. Open it there or keep the generated cut.</div>
                </div>
                {selectedDriveVideoLink && (
                  <div style={{ padding: '8px 10px', background: '#fff', textAlign: 'right', borderTop: '1px solid #e5e7eb' }}>
                    <a href={selectedDriveVideoLink} target="_blank" rel="noreferrer" style={{ color: '#2563eb', fontSize: 12, fontWeight: 700 }}>Open video in Drive →</a>
                  </div>
                )}
              </div>
            )}
          </DriveSwapContainer>
        </div>
      );
    }

    return (
      <div style={{ padding: '20px', textAlign: 'left', color: '#333', fontSize: '12px', border: '1px dashed #ccc', maxWidth: 520 }}>
        <div style={{ color: '#666', marginBottom: 10 }}>Preview is not available for this artifact type yet.</div>
        <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>{result.content}</div>
      </div>
    );
  };

  return (
    <div className={`approval-bundle ${surfaceContext}`}>
      <div className="artifact-card" style={{ borderColor: statusColor(reviewStatus) }}>
        <div className="artifact-card-header">
          <div>
            <div className="artifact-eyebrow">Artifact</div>
            <div className="artifact-title">{title}</div>
            {moduleId.includes('video.edit') && (result.block as any)?.change_summary && (
              <div style={{ fontSize: 12, color: '#374151', marginTop: 2, marginBottom: 2, lineHeight: 1.4, fontStyle: 'italic' }}>
                {(result.block as any).change_summary}
              </div>
            )}
            <div className="artifact-meta">
              {moduleId.includes('strategy_workflow')
                ? 'Strategy Workflow · Draft for review'
                : moduleId.includes('marketing.plan')
                ? 'Plan artifact · Draft for review'
                : moduleId.includes('gbp')
                ? 'Read-only local SEO audit'
                : moduleId.includes('postcraft')
                ? (() => { const b = run.result?.block as any; return `${b?.template_type || 'promo'} · ${b?.post_format || 'square'} · ${b?.provider || 'ai'}`; })()
                : `${activeCampaign?.name ? `Campaign: ${activeCampaign.name}` : 'Campaign: Unassigned'} · ${platformLabel}`}

            </div>
          </div>
          <span className={`artifact-status ${reviewStatus}`} style={{ color: statusColor(reviewStatus), borderColor: statusColor(reviewStatus) }}>
            {statusLabel(reviewStatus)}
          </span>
        </div>

        <div className="artifact-preview">
          {renderPreview()}
        </div>

        {(moduleId.includes('google') && moduleId.includes('text')) && (
          <div className="artifact-copy-panel">
            <div className="artifact-section-label">Copy</div>
            <div className="artifact-copy-text">{result.content || 'No copy available'}</div>
          </div>
        )}

        {isCreativePost && reviewStatus !== 'dismissed' && reviewStatus !== 'deleted' && (
          <>
            <div className="artifact-copy-panel">
              <div className="artifact-section-label">Copy</div>
              <textarea
                className="artifact-revision-input"
                value={editedCaption}
                onChange={e => setEditedCaption(e.target.value)}
                rows={4}
                placeholder="Post copy…"
              />
            </div>
            <div className="artifact-copy-panel">
              <div className="artifact-section-label">Attachment</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {swappedAttachment ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, flex: 1, minWidth: 0 }}>
                    {swappedAttachment
                      ? <img src={driveThumbnailUrl(swappedAttachment.id)} alt={swappedAttachment.name} loading="lazy" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 6, border: '1px solid #e5e7eb', flexShrink: 0 }} />
                      : <span style={{ fontSize: 20, flexShrink: 0 }}>🖼</span>
                    }
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{swappedAttachment.name}</div>
                      <div style={{ color: '#6b7280', fontSize: 11 }}>{swappedAttachment.mimeType}</div>
                    </div>
                    <button style={{ marginLeft: 'auto', flexShrink: 0, fontSize: 11, color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer' }} onClick={() => setSwappedAttachment(null)}>Remove</button>
                  </div>
                ) : result.block?.image_data_b64 ? (
                  <img
                    src={`data:${result.block.mime_type || 'image/png'};base64,${result.block.image_data_b64}`}
                    alt="Post image"
                    style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 6, border: '1px solid #e5e7eb', flexShrink: 0 }}
                  />
                ) : (
                  <div style={{ width: 56, height: 56, borderRadius: 6, border: '1px dashed #d1d5db', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 20, flexShrink: 0 }}>🖼</div>
                )}
                <button className="artifact-btn ghost" onClick={() => openDrivePicker()}>Swap · Drive</button>
              </div>
            </div>
          </>
        )}

        {isShortformVideo && reviewStatus !== 'dismissed' && reviewStatus !== 'deleted' && (
          <>
            <div className="artifact-copy-panel">
              <div className="artifact-section-label">Hook</div>
              <textarea
                className="artifact-revision-input"
                value={editedHookText}
                onChange={e => setEditedHookText(e.target.value)}
                rows={2}
                placeholder="Hook text overlay…"
              />
            </div>
            <div className="artifact-copy-panel">
              <div className="artifact-section-label">CTA</div>
              <textarea
                className="artifact-revision-input"
                value={editedCtaText}
                onChange={e => setEditedCtaText(e.target.value)}
                rows={1}
                placeholder="Call to action…"
              />
            </div>
            <div className="artifact-copy-panel">
              <div className="artifact-section-label">Attachment</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {swappedVideo ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, flex: 1, minWidth: 0 }}>
                    {swappedVideo
                      ? <img src={driveThumbnailUrl(swappedVideo.id)} alt={swappedVideo.name} loading="lazy" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 6, border: '1px solid #e5e7eb', flexShrink: 0 }} />
                      : <span style={{ fontSize: 20, flexShrink: 0 }}>🎬</span>
                    }
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{swappedVideo.name}</div>
                      <div style={{ color: '#6b7280', fontSize: 11 }}>{swappedVideo.mimeType}</div>
                    </div>
                    <button style={{ marginLeft: 'auto', flexShrink: 0, fontSize: 11, color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer' }} onClick={() => setSwappedVideo(null)}>Remove</button>
                  </div>
                ) : (() => {
                  const b = result.block as any;
                  const src = localVideoSrcFromBlock(b);
                  return src
                    ? <video src={src} muted preload="metadata" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 6, border: '1px solid #e5e7eb', flexShrink: 0 }} />
                    : <div style={{ width: 56, height: 56, borderRadius: 6, border: '1px dashed #d1d5db', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 20, flexShrink: 0 }}>🎬</div>;
                })()}
                <button className="artifact-btn ghost" onClick={() => openDrivePicker('video')}>Swap · Drive</button>
              </div>
            </div>
          </>
        )}

        {isStoryboardImage && reviewStatus !== 'dismissed' && reviewStatus !== 'deleted' && reviewStatus !== 'approved' && reviewStatus !== 'failed' && (
          <div className="artifact-copy-panel">
            <div className="artifact-section-label">Video generation notes</div>
            <textarea
              className="artifact-revision-input"
              value={videoGenerationNotes}
              onChange={e => setVideoGenerationNotes(e.target.value)}
              rows={2}
              placeholder="Optional — e.g. make it colored, avoid text overlays, slower camera moves…"
              disabled={publishing}
            />
            <div style={{ marginTop: 6, fontSize: 11, color: '#6b7280' }}>
              These notes are sent directly to Previs Motion when you approve and generate video.
            </div>
          </div>
        )}

        {isImageAsset && !isStoryboardImage && reviewStatus !== 'dismissed' && reviewStatus !== 'deleted' && (
          <>
            <div className="artifact-copy-panel">
              <div className="artifact-section-label">Caption</div>
              <textarea
                className="artifact-revision-input"
                value={imageCaption}
                onChange={e => setImageCaption(e.target.value)}
                rows={2}
                placeholder="Post caption (optional — leave blank to use the image prompt)"
              />
            </div>
            <div className="artifact-copy-panel">
              <div className="artifact-section-label">Attachment</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {swappedAttachment ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, flex: 1, minWidth: 0 }}>
                    {swappedAttachment
                      ? <img src={driveThumbnailUrl(swappedAttachment.id)} alt={swappedAttachment.name} loading="lazy" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 6, border: '1px solid #e5e7eb', flexShrink: 0 }} />
                      : <span style={{ fontSize: 20, flexShrink: 0 }}>🖼</span>
                    }
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{swappedAttachment.name}</div>
                      <div style={{ color: '#6b7280', fontSize: 11 }}>{swappedAttachment.mimeType}</div>
                    </div>
                    <button style={{ marginLeft: 'auto', flexShrink: 0, fontSize: 11, color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer' }} onClick={() => setSwappedAttachment(null)}>Remove</button>
                  </div>
                ) : (() => {
                  const b = result.block as any;
                  return b?.image_data_b64
                    ? <img src={`data:${b.mime_type || 'image/png'};base64,${b.image_data_b64}`} alt="Generated" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 6, border: '1px solid #e5e7eb', flexShrink: 0 }} />
                    : <div style={{ width: 56, height: 56, borderRadius: 6, border: '1px dashed #d1d5db', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 20, flexShrink: 0 }}>🖼</div>;
                })()}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginLeft: 'auto', flexShrink: 0 }}>
                  <button className="artifact-btn ghost" onClick={() => openDrivePicker('image')}>Swap · Drive</button>
                  {isPostcraftImage && (
                    <button className="artifact-btn ghost" onClick={openTemplateModalForGeneratedArtifact}>
                      Save as template
                    </button>
                  )}
                </div>
              </div>
            </div>
          </>
        )}


        {isOmniPublishAsset && reviewStatus !== 'approved' && reviewStatus !== 'dismissed' && reviewStatus !== 'deleted' && reviewStatus !== 'failed' && (
          <div className="artifact-copy-panel">
            <div className="artifact-section-label">Publishing destinations</div>
            {publishOptionsLoading ? (
              <div style={{ fontSize: 12, color: '#6b7280' }}>Checking connected brand channels…</div>
            ) : publishOptions.length === 0 ? (
              <div style={{ fontSize: 12, color: '#6b7280' }}>No publishing destinations are declared for this artifact yet.</div>
            ) : (
              <div style={{ display: 'grid', gap: 8 }}>
                {publishOptions.map(opt => (
                  <label key={opt.action} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', border: '1px solid #e5e7eb', borderRadius: 8, background: opt.connected ? '#fff' : '#f9fafb', color: opt.connected ? '#111827' : '#9ca3af' }}>
                    <input
                      type="checkbox"
                      checked={Boolean(publishSelections[opt.action])}
                      disabled={!opt.connected || publishing}
                      onChange={e => setPublishSelections(prev => ({ ...prev, [opt.action]: e.target.checked }))}
                    />
                    <span style={{ fontWeight: 700, fontSize: 13 }}>{opt.label}</span>
                    <span style={{ marginLeft: 'auto', fontSize: 11, color: opt.connected ? '#16a34a' : '#dc2626' }}>
                      {opt.connected ? `Connected${opt.accountLabel ? ` · ${opt.accountLabel}` : ''}` : 'Not connected'}
                    </span>
                  </label>
                ))}
              </div>
            )}
            {hasSchedulableFacebookOption && (
              <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid #e5e7eb', display: 'grid', gap: 6 }}>
                <div className="artifact-section-label">Schedule Facebook</div>
                <input
                  type="datetime-local"
                  value={scheduleAtLocal}
                  min={minFacebookScheduleLocal()}
                  onChange={e => setScheduleAtLocal(e.target.value)}
                  disabled={publishing}
                  style={{ border: '1px solid #d1d5db', borderRadius: 8, padding: '8px 10px', fontSize: 13 }}
                />
                <div style={{ fontSize: 11, color: '#6b7280' }}>
                  Select only the connected Facebook destination. Facebook requires scheduled posts to be at least 10 minutes in the future.
                </div>
              </div>
            )}
            <div style={{ marginTop: 8, fontSize: 11, color: '#6b7280' }}>
              Select every connected channel you want. BOS will publish to all selected destinations after approval.
            </div>
          </div>
        )}

        <div className="artifact-review-bar">
          <div className="artifact-review-note">
            {isImprintDraft && publishing && 'Copy approved. Generating the image now — this can take a few minutes. The generated image will appear as a new Needs approval artifact.'}
            {isStoryboardDraft && publishing && (isProductionBlueprint ? 'Rendering the image storyboard from the approved production blueprint — this can take a few minutes. Video comes after storyboard approval.' : 'Rendering the image storyboard now — this can take a few minutes. This draft stays in Needs approval while BOS works.')}
            {isStoryboardDraft && !publishing && storyboardRenderRun && !actionRunFailed(storyboardRenderRun) && 'Image storyboard generated and added as a new Needs approval artifact.'}
            {isPostcraftDraft && publishing && 'Rendering the approved Postcraft draft into a branded image — this can take a few minutes.'}
            {isPostcraftDraft && !publishing && postcraftRenderRun && !actionRunFailed(postcraftRenderRun) && 'Postcraft image generated and added as a new Needs approval artifact.'}
            {isStoryboardImage && publishing && 'Storyboard approved. Generating the video now — this can take a few minutes.'}
            {isStoryboardImage && !publishing && storyboardVideoRun && !actionRunFailed(storyboardVideoRun) && 'Video generated and added as a new Needs approval artifact.'}
            {reviewStatus === 'approved' && !isStoryboardDraft && 'Approved and removed from needs-attention.'}
            {reviewStatus === 'draft' && 'Saved as a draft. It will not block approvals.'}
            {(reviewStatus === 'deleted' || reviewStatus === 'dismissed') && 'Deleted from the artifact system.'}
            {reviewStatus === 'failed' && 'Generation failed. Configure credentials, retry, or delete.'}
            {reviewStatus === 'pending' && (selfCheckPassed ? 'Needs approval before anything else happens.' : 'Self-check flagged this. Revise or review before approving.')}
          </div>
          <div className="artifact-actions">
            {reviewStatus === 'failed' && (
              <>
                <button type="button" className="artifact-btn ghost" onClick={handleDelete}>Delete</button>
                <button className="artifact-btn ghost" onClick={() => { window.location.href = '/admin/modules'; }}>Configure</button>
                <button className="artifact-btn primary" onClick={() => { setModifying(v => !v); addPendingRun(run); }}>Retry</button>
              </>
            )}
            {reviewStatus !== 'approved' && reviewStatus !== 'failed' && (
              <>
                <button type="button" className="artifact-btn ghost" onClick={handleDelete} disabled={publishing || revisionBusy}>Delete</button>
                {!isCreativePost && !isShortformVideo && !isImageAsset && !isImprintDraft && !isPostcraftDraft && <button className="artifact-btn ghost" onClick={handleSaveDraft} disabled={publishing || revisionBusy}>Save draft</button>}
                <button className="artifact-btn ghost" onClick={() => { setModifying(v => !v); addPendingRun(run); }} disabled={publishing || revisionBusy}>Revise</button>
                {isFbDraft && (
                  <button className="artifact-btn ghost" onClick={() => openDrivePicker()} disabled={attaching}>
                    {attachedImage ? '🖼 Change image' : 'Attach image'}
                  </button>
                )}
                {(() => {
                  if (isOmniPublishAsset) {
                    return (
                      <>
                        <button className="artifact-btn primary" onClick={handleApprove} disabled={publishing || revisionBusy}>
                          {publishing ? 'Approving…' : 'Approve'}
                        </button>
                        {hasSchedulableFacebookOption && (
                          <button
                            className="artifact-btn ghost"
                            onClick={handleScheduleSelected}
                            disabled={publishing || !scheduleAtLocal || selectedPublishOptions.length !== 1 || selectedSchedulableFacebookOptions.length !== 1}
                          >
                            {publishing ? 'Scheduling…' : 'Schedule Selected'}
                          </button>
                        )}
                        <button
                          className="artifact-btn ghost"
                          onClick={handlePublishSelected}
                          disabled={publishing || selectedPublishOptions.length === 0 || Boolean(scheduleAtLocal && selectedSchedulableFacebookOptions.length > 0)}
                        >
                          {publishing ? 'Publishing…' : 'Publish Selected'}
                        </button>
                      </>
                    );
                  }
                  if (isStoryboardDraft && storyboardRenderRun && !publishing) {
                    return <button className="artifact-btn primary" onClick={() => window.dispatchEvent(new CustomEvent('bos:focus-artifact', { detail: storyboardRenderRun }))}>Open image storyboard</button>;
                  }
                  if (isStoryboardImage && storyboardVideoRun && !publishing) {
                    return <button className="artifact-btn primary" onClick={() => window.dispatchEvent(new CustomEvent('bos:focus-artifact', { detail: storyboardVideoRun }))}>Open video artifact</button>;
                  }
                  if (isPostcraftDraft && postcraftRenderRun && !publishing) {
                    return <button className="artifact-btn primary" onClick={() => window.dispatchEvent(new CustomEvent('bos:focus-artifact', { detail: postcraftRenderRun }))}>Open Postcraft image</button>;
                  }
                  return (
                    <button className="artifact-btn primary" onClick={handleApprove} disabled={publishing}>
                      {publishing ? (isStoryboardImage ? 'Generating video…' : ((isImprintDraft || isPostcraftDraft) ? 'Generating image…' : 'Rendering…')) : (isStoryboardDraft ? (isProductionBlueprint ? 'Approve & Render Storyboard' : 'Approve & Render') : (isPostcraftDraft ? 'Approve & Render Image' : (isImprintDraft ? 'Approve & Generate Image' : (isStoryboardImage ? 'Approve & Generate Video' : (canPublish && !isCreativePost ? 'Approve & Publish' : 'Approve')))))}
                    </button>
                  );
                })()}
              </>
            )}
            {reviewStatus === 'approved' && !publishing && (
              <>
                <button type="button" className="artifact-btn ghost" onClick={handleDelete} disabled={revisionBusy}>Delete</button>
                <button className="artifact-btn ghost" onClick={() => { setReviewStatus('pending'); addPendingRun(run); }}>Reopen</button>
              </>
            )}
          </div>
        </div>

        {result.block?.type !== 'gtm_strategy' && (
          <>
            <div className="artifact-details-row">
              <button className="artifact-link-btn" onClick={() => setDetailsOpen(v => !v)}>
                {detailsOpen ? 'Hide system details' : 'System details'}
              </button>
            </div>
            {detailsOpen && (
              <div className="artifact-system-details">
                <div><strong>Self-check:</strong> {result.self_check || 'unknown'}</div>
                <div><strong>Artifact ID:</strong> {run.run_id}</div>
                <div><strong>Capability:</strong> {run.module_id}</div>
              </div>
            )}
          </>
        )}
        {templateError && !templateModalOpen && <div className="artifact-error" style={{ marginTop: 10 }}>{templateError}</div>}
        {templateNotice && !templateModalOpen && (
          <div style={{ marginTop: 10, fontSize: 12, color: '#166534', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8, padding: '8px 10px' }}>
            {templateNotice}
          </div>
        )}
      </div>

      {modifying && !revision && (
        <div
          className="artifact-revision-box"
          onDragOver={e => handleDragOver(e, 'revision')}
          onDragLeave={() => handleDragLeave('revision')}
          onDrop={e => void handleDropFiles(e, 'revision', isPostcraftImage ? 'image' : 'all')}
          style={{ border: dragTarget === 'revision' ? '1px dashed var(--copper)' : undefined, boxShadow: dragTarget === 'revision' ? '0 0 0 3px rgba(188, 108, 37, 0.12)' : undefined }}>
          <div className="artifact-section-label">Revision direction</div>
          <textarea
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
            placeholder={`Tell the CMO what is not working — e.g. keep the opening, make the CTA stronger, try a warmer angle...`}
            rows={3}
            className="artifact-revision-input"
            disabled={revisionBusy}
          />
          {dragTarget === 'revision' && (
            <div style={{ marginTop: 8, padding: '10px 12px', borderRadius: 10, border: '1px dashed var(--copper)', background: '#fff7ed', color: '#9a3412', fontSize: 12 }}>
              {isPostcraftImage ? 'Drop image files here to attach them to this image revision.' : 'Drop image or document files here to attach them to this revision.'}
            </div>
          )}
          {revisionReferences.length > 0 && (
            <div className="artifact-revision-refs">
              <div className="artifact-section-label">Revision references · {revisionReferences.length}</div>
              <div className="artifact-revision-ref-grid">
                {revisionReferences.map((ref, idx) => {
                  const previewKind = referencePreviewKind(ref);
                  const previewSrc = previewKind === 'image' && ref.drive_file_id ? driveThumbnailUrl(ref.drive_file_id) : '';
                  return (
                    <div key={`${ref.drive_file_id || ref.title || idx}`} className="artifact-revision-ref-card">
                      <div className="artifact-revision-ref-thumb-wrap">
                        {previewSrc ? (
                          <img src={previewSrc} alt={referenceDisplayName(ref)} loading="lazy" className="artifact-revision-ref-thumb" />
                        ) : (
                          <div className={`artifact-revision-ref-fallback ${previewKind}`}>
                            {previewKind === 'document' ? '📄' : (previewKind === 'text' ? '📝' : '🖼️')}
                          </div>
                        )}
                        <button
                          type="button"
                          aria-label="Remove attachment"
                          className="artifact-revision-ref-remove"
                          onClick={() => setRevisionReferences(prev => prev.filter((_, i) => i !== idx))}
                        >
                          ×
                        </button>
                      </div>
                      <div className="artifact-revision-ref-meta">
                        <div className="artifact-revision-ref-name" title={referenceDisplayName(ref)}>{referenceDisplayName(ref)}</div>
                        <div className="artifact-revision-ref-kind">{previewKind === 'image' ? 'Image reference' : (previewKind === 'document' ? 'Document reference' : 'Text reference')}</div>
                        {previewKind === 'image' && ref.drive_file_id && (
                          <button
                            type="button"
                            className="artifact-btn ghost"
                            style={{ marginTop: 8, alignSelf: 'flex-start', padding: '4px 8px', fontSize: 11 }}
                            onClick={() => openTemplateModalForReference(ref)}
                          >
                            Save as template
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {revisionBusy && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, padding: '9px 10px', borderRadius: 10, background: '#fffbeb', border: '1px solid #fde68a', color: '#713f12', fontSize: 12 }}>
              <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
              <span>{isImageAsset || isImprintAsset || moduleId.includes('imprint') ? 'Image revision is processing…' : (isShortformVideo || moduleId.includes('storyboard.motion') ? 'Video revision is processing…' : 'Revision is processing…')}</span>
            </div>
          )}
          {revisionError && <div className="artifact-error">{revisionError}</div>}
          <div className="artifact-revision-actions">
            <button className="artifact-btn ghost" onClick={() => openDrivePicker(isPostcraftImage ? 'image' : 'all')} disabled={revisionBusy || attaching}>+ Attach from Drive</button>
            <button className="artifact-btn ghost" onClick={() => triggerLocalUpload(isPostcraftImage ? 'image' : 'all')} disabled={revisionBusy || attaching}>Upload from desktop</button>
            <button className="artifact-btn ghost" onClick={() => setModifying(false)} disabled={revisionBusy}>Cancel</button>
            <button className="artifact-btn primary" onClick={handleRevisionSubmit} disabled={revisionBusy}>
              {revisionBusy ? (isImageAsset || isImprintAsset || moduleId.includes('imprint') ? 'Processing image…' : (isShortformVideo || moduleId.includes('storyboard.motion') ? 'Processing video…' : 'Updating…')) : 'Create revision'}
            </button>
          </div>
        </div>
      )}

      {revision && (
        <div className="artifact-revision-result">
          <div className="artifact-revision-note">{revisionReply || `I revised this ${platformLabel} draft based on your note.`}</div>
          <ApprovalBundle run={revision} surfaceContext="chat-inline" revisionHistory={localRevisionHistory} />
        </div>
      )}

      {templateModalOpen && templateSource && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 10000, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={e => { if (e.target === e.currentTarget && !templateSaving) setTemplateModalOpen(false); }}>
          <div style={{ width: 420, maxWidth: '94vw', background: '#fff', borderRadius: 14, padding: 20, border: '1px solid #e5e7eb', boxShadow: '0 24px 48px rgba(15, 23, 42, 0.18)', display: 'grid', gap: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
              <div>
                <div style={{ fontSize: 16, fontWeight: 800 }}>Save as template</div>
                <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
                  {templateSource.existingTemplateId ? 'Update the saved Brand Kit template metadata.' : 'Create a Brand Kit template draft from this image.'}
                </div>
              </div>
              <button type="button" onClick={() => !templateSaving && setTemplateModalOpen(false)} style={{ background: 'none', border: 'none', cursor: templateSaving ? 'default' : 'pointer', fontSize: 18, color: '#6b7280' }}>✕</button>
            </div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '10px 12px', borderRadius: 10, background: '#f9fafb', border: '1px solid #e5e7eb' }}>
              <div style={{ width: 42, height: 42, borderRadius: 8, border: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#fff', color: '#9ca3af', fontSize: 18 }}>🖼️</div>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{templateSource.name}</div>
                <div style={{ fontSize: 11, color: '#6b7280' }}>{templateSource.mimeType || 'image'}</div>
              </div>
            </div>
            <label style={{ display: 'grid', gap: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: '#374151' }}>Template name</span>
              <input value={templateNameDraft} onChange={e => setTemplateNameDraft(e.target.value)} disabled={templateSaving} style={{ border: '1px solid #d1d5db', borderRadius: 8, padding: '8px 10px', fontSize: 13 }} />
            </label>
            <div style={{ display: 'grid', gap: 10, gridTemplateColumns: '1fr 1fr' }}>
              <label style={{ display: 'grid', gap: 6 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: '#374151' }}>Format</span>
                <select value={templateFormatDraft} onChange={e => setTemplateFormatDraft(e.target.value)} disabled={templateSaving} style={{ border: '1px solid #d1d5db', borderRadius: 8, padding: '8px 10px', fontSize: 13 }}>
                  <option value="square_feed">Square</option>
                  <option value="portrait_feed">Portrait</option>
                  <option value="story_reel">Story / Reel</option>
                  <option value="landscape">Landscape</option>
                </select>
              </label>
              <label style={{ display: 'grid', gap: 6 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: '#374151' }}>Content type</span>
                <select value={templateContentTypeDraft} onChange={e => setTemplateContentTypeDraft(e.target.value)} disabled={templateSaving} style={{ border: '1px solid #d1d5db', borderRadius: 8, padding: '8px 10px', fontSize: 13 }}>
                  <option value="promo">Promo</option>
                  <option value="price_card">Price card</option>
                  <option value="photo_hero">Photo hero</option>
                  <option value="agent_award">Agent award</option>
                  <option value="educational">Educational</option>
                </select>
              </label>
            </div>
            <div style={{ fontSize: 12, color: '#6b7280', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 10, padding: '10px 12px' }}>
              Saved templates default to <strong>draft</strong> and should be reviewed in Brand Kit before being used in production.
            </div>
            {templateError && <div className="artifact-error">{templateError}</div>}
            {templateNotice && <div style={{ fontSize: 12, color: '#166534', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8, padding: '8px 10px' }}>{templateNotice}</div>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button className="artifact-btn ghost" onClick={() => setTemplateModalOpen(false)} disabled={templateSaving}>Cancel</button>
              <button className="artifact-btn primary" onClick={() => void handleTemplateSave()} disabled={templateSaving || !templateNameDraft.trim()}>
                {templateSaving ? 'Saving…' : (templateSource.existingTemplateId ? 'Update template' : 'Save template draft')}
              </button>
            </div>
          </div>
        </div>
      )}

      <input
        ref={uploadInputRef}
        type="file"
        accept={LOCAL_ATTACHMENT_ACCEPT}
        multiple={drivePickerMediaType === 'all'}
        style={{ display: 'none' }}
        onChange={handleLocalAttachmentUpload}
      />

      {drivePickerOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onClick={e => { if (e.target === e.currentTarget) setDrivePickerOpen(false); }}>
          <div
            style={{ background: '#fff', borderRadius: 14, padding: 24, width: 480, maxWidth: '95vw', maxHeight: '80vh', display: 'flex', flexDirection: 'column', gap: 12, border: dragTarget === 'modal' ? '1px dashed var(--copper)' : undefined, boxShadow: dragTarget === 'modal' ? '0 0 0 3px rgba(188, 108, 37, 0.12)' : undefined }}
            onDragOver={e => handleDragOver(e, 'modal')}
            onDragLeave={() => handleDragLeave('modal')}
            onDrop={e => void handleDropFiles(e, 'modal')}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
              <div style={{ fontWeight: 700, fontSize: 15 }}>
                {drivePickerMediaType === 'all' ? 'Attach reference from Drive' : isShortformVideo ? 'Swap video from Drive' : (isCreativePost || isImageAsset) ? 'Swap image from Drive' : 'Attach image from Drive'}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {drivePickerMediaType !== 'video' && (
                  <button className="artifact-btn ghost" onClick={() => triggerLocalUpload(drivePickerMediaType)} disabled={attaching}>Upload from desktop</button>
                )}
                <button style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: '#6b7280' }} onClick={() => setDrivePickerOpen(false)}>✕</button>
              </div>
            </div>
            {dragTarget === 'modal' && (
              <div style={{ padding: '10px 12px', borderRadius: 10, border: '1px dashed #c2410c', background: '#fff7ed', color: '#9a3412', fontSize: 12 }}>
                Drop files here to upload them into Drive and use them in this approval bundle.
              </div>
            )}
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                value={driveSearch}
                onChange={e => setDriveSearch(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') void loadDrivePickerFolder(drivePickerMediaType, driveCurrentFolder, driveFolderStack, driveSearch); }}
                placeholder="Search Drive files in this folder…"
                style={{ flex: 1, border: '1px solid #d1d5db', borderRadius: 8, padding: '8px 10px', fontSize: 13 }}
              />
              <button className="artifact-btn ghost" onClick={() => loadDrivePickerFolder(drivePickerMediaType, driveCurrentFolder, driveFolderStack, driveSearch)} disabled={driveLoading}>Search</button>
              {driveSearch && <button className="artifact-btn ghost" onClick={() => { setDriveSearch(''); void loadDrivePickerFolder(drivePickerMediaType, driveCurrentFolder, driveFolderStack, ''); }} disabled={driveLoading}>Clear</button>}
            </div>
            {driveCurrentFolder && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#6b7280', background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: 8, padding: '7px 9px' }}>
                {driveFolderStack.length > 0 && (
                  <button
                    className="artifact-btn ghost"
                    style={{ padding: '2px 8px', fontSize: 11 }}
                    onClick={() => {
                      const nextStack = driveFolderStack.slice(0, -1);
                      const parent = nextStack[nextStack.length - 1] || null;
                      loadDrivePickerFolder(drivePickerMediaType, parent, nextStack, driveSearch);
                    }}
                    disabled={driveLoading}
                  >
                    Back
                  </button>
                )}
                <span>Folder: <strong style={{ color: '#111827' }}>{driveCurrentFolder.name}</strong></span>
              </div>
            )}
            {driveLoading && <div style={{ color: '#6b7280', fontSize: 13 }}>Loading folders and {drivePickerMediaType === 'video' ? 'videos' : drivePickerMediaType === 'all' ? 'files' : 'images'} from Drive…</div>}
            {driveError && <div style={{ color: '#ef4444', fontSize: 13 }}>{driveError}</div>}
            {!driveLoading && !driveError && driveFolders.length === 0 && driveFiles.length === 0 && (
              <div style={{ color: '#6b7280', fontSize: 13 }}>No folders or {drivePickerMediaType === 'video' ? 'video files' : drivePickerMediaType === 'all' ? 'files' : 'images'} found in this Drive folder.</div>
            )}
            {!driveLoading && (driveFolders.length > 0 || driveFiles.length > 0) && (
              <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
                {driveFolders.map(folder => (
                  <button key={folder.id}
                    style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 7, cursor: 'pointer', textAlign: 'left', fontSize: 13 }}
                    onClick={() => loadDrivePickerFolder(drivePickerMediaType, folder, [...driveFolderStack, folder], driveSearch)}>
                    <span style={{ fontSize: 20, flexShrink: 0 }}>📁</span>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{folder.name}</div>
                      <div style={{ color: '#9a3412', fontSize: 11 }}>Open folder</div>
                    </div>
                  </button>
                ))}
                {driveFiles.map(f => {
                  const isSelected = (drivePickerMediaType === 'all' || (modifying && !revision && isPostcraftImage))
                    ? revisionReferences.some(ref => ref.drive_file_id === f.id)
                    : isShortformVideo
                      ? swappedVideo?.id === f.id
                      : (isCreativePost || isImageAsset)
                        ? swappedAttachment?.id === f.id
                        : attachedImage?.id === f.id;
                  const isVideo = f.mimeType?.startsWith('video/');
                  const isDoc = DOC_MIMES_SET.has(f.mimeType);
                  return (
                    <button key={f.id} disabled={attaching}
                      style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', background: isSelected ? '#f0fdf4' : '#f9fafb', border: `1px solid ${isSelected ? '#86efac' : '#e5e7eb'}`, borderRadius: 7, cursor: 'pointer', textAlign: 'left', fontSize: 13 }}
                      onClick={() => selectDriveImage(f)}>
                      {f.mimeType?.startsWith('image/')
                        ? <img src={driveThumbnailUrl(f.id)} alt={f.name} loading="lazy" style={{ width: 44, height: 44, objectFit: 'cover', borderRadius: 5, flexShrink: 0, border: '1px solid #e5e7eb' }} />
                        : <span style={{ fontSize: 20, flexShrink: 0 }}>{isDoc ? '📄' : isVideo ? '🎬' : '🖼'}</span>
                      }
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</div>
                        <div style={{ color: '#6b7280', fontSize: 11 }}>{f.mimeType}{f.size ? ` · ${(f.size / 1024).toFixed(0)} KB` : ''}</div>
                      </div>
                      {isSelected && <span style={{ marginLeft: 'auto', color: '#16a34a', fontWeight: 700, flexShrink: 0 }}>✓</span>}
                    </button>
                  );
                })}
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button className="artifact-btn ghost" onClick={() => setDrivePickerOpen(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
