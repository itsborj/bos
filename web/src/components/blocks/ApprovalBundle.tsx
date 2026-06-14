import { useState, useCallback, useEffect, type ReactNode } from 'react';
import { api } from '../../api/client';
import { useUI } from '../../context/UIContext';
import { GoogleSearchPreview } from './previews/GoogleSearchPreview';
import { GoogleDisplayPreview } from './previews/GoogleDisplayPreview';
import { FacebookFeedPreview } from './previews/FacebookFeedPreview';
import { InstagramFeedPreview } from './previews/InstagramFeedPreview';
import { InstagramStoryPreview } from './previews/InstagramStoryPreview';
import { EmailPreview } from './previews/EmailPreview';
import { PinterestPreview } from './previews/PinterestPreview';
import { TwitterFeedPreview } from './previews/TwitterFeedPreview';
import type { ChatHistoryItem, RunResponse } from '../../api/types';

type DriveFile = { id: string; name: string; mimeType: string; size?: number; webViewLink?: string; thumbnailLink?: string };
type DriveFolder = { id: string; name: string };
type DriveMediaKind = 'image' | 'video';
type SocialConnection = { id: string; brand_id: string | null; platform: string; page_id: string; page_name: string | null; page_handle: string | null; status: string };
type PublishOption = { action: string; moduleId: string; label: string; platform: string; connected: boolean; accountLabel?: string };

interface ApprovalBundleProps {
  run: RunResponse;
  surfaceContext: 'chat-inline' | 'panel' | 'full-screen';
  onRevision?: (reply: string, run: RunResponse, previousRunId?: string) => void;
  onApproved?: (run: RunResponse) => void;
  onDismissed?: (run: RunResponse) => void;
  revisionHistory?: ChatHistoryItem[];
}

type ReviewStatus = 'pending' | 'draft' | 'dismissed' | 'approved' | 'failed';

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
  if (moduleId.includes('gtm_plan') || moduleId.includes('gtm')) return 'GTM Strategy';
  if (moduleId.includes('marketing.plan')) return 'Marketing Plan';
  if (moduleId.includes('email') && moduleId.includes('plan')) return 'Email Campaign Plan';
  if (moduleId.includes('email') || platformLabel.toLowerCase().includes('email')) return 'Email Draft';
  if (moduleId.includes('gbp') || platformLabel.toLowerCase().includes('google business')) return 'Google Business Profile Audit';
  if (moduleId.includes('plan')) return 'Campaign Plan';
  if (moduleId.includes('report') || moduleId.includes('analytics')) return 'Marketing Report';
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
  const status = run.approval_status || (run as any).approval_status || (run.result as any)?.approval_status;
  if (run.status === 'failed' || (run.result?.block as any)?.status === 'failed' || status === 'failed') return 'failed';
  if (status === 'approved') return 'approved';
  if (status === 'rejected' || status === 'dismissed') return 'dismissed';
  return 'pending';
}

function statusLabel(status: ReviewStatus): string {
  if (status === 'approved') return 'Approved';
  if (status === 'dismissed') return 'Dismissed';
  if (status === 'draft') return 'Saved draft';
  if (status === 'failed') return 'Failed';
  return 'Needs review';
}

function statusColor(status: ReviewStatus): string {
  if (status === 'approved') return '#16a34a';
  if (status === 'dismissed') return '#6b7280';
  if (status === 'draft') return '#6366f1';
  if (status === 'failed') return '#dc2626';
  return '#111827';
}

function hasArtifactAction(run: RunResponse, action: string): boolean {
  const block = run.result?.block;
  return Array.isArray(block?.allowed_actions)
    && block.allowed_actions.includes(action)
    && typeof block?.action_modules?.[action] === 'string';
}

function publishPlatform(action: string, moduleId: string): string {
  const key = `${action} ${moduleId}`.toLowerCase();
  if (key.includes('youtube')) return 'youtube';
  if (key.includes('tiktok')) return 'tiktok';
  if (key.includes('instagram')) return 'instagram';
  if (key.includes('facebook') || key.includes('meta')) return 'facebook';
  return action.replace(/^publish_/, '');
}

function publishLabel(action: string, moduleId: string, blockType?: string): string {
  const platform = publishPlatform(action, moduleId);
  const isVideo = blockType === 'video_asset' || blockType === 'creative_shortform_video';
  if (platform === 'youtube') return isVideo ? 'YouTube Shorts' : 'YouTube';
  if (platform === 'facebook') return isVideo ? 'Facebook Reels' : 'Facebook';
  if (platform === 'instagram') return isVideo ? 'Instagram Reels' : 'Instagram';
  if (platform === 'tiktok') return 'TikTok';
  return titleCase(action.replace(/^publish_/, ''));
}

function buildPublishOptions(actionModules: Record<string, string> | undefined, connections: SocialConnection[], blockType?: string): PublishOption[] {
  if (!actionModules) return [];
  return Object.entries(actionModules).map(([action, moduleId]) => {
    const platform = publishPlatform(action, moduleId);
    const connection = connections.find(c => c.status === 'connected' && c.platform === platform);
    return {
      action,
      moduleId,
      platform,
      label: publishLabel(action, moduleId, blockType),
      connected: Boolean(connection),
      accountLabel: connection?.page_name || connection?.page_handle || connection?.page_id,
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
          <div style={{ fontSize: 10, fontWeight: 900, color: '#826D40', textTransform: 'uppercase', letterSpacing: '.08em' }}>{label} artifact</div>
          <div style={{ fontSize: 11, color: selectedFile ? '#166534' : '#6b7280', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
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

export function ApprovalBundle({ run, surfaceContext, onRevision, onApproved, onDismissed, revisionHistory = [] }: ApprovalBundleProps) {
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

  // Drive picker (shared between fb_page_post_draft attach, creative_post_asset swap, shortform video swap)
  const [drivePickerOpen, setDrivePickerOpen] = useState(false);
  const [drivePickerMediaType, setDrivePickerMediaType] = useState<string>('image');
  const [driveFiles, setDriveFiles] = useState<DriveFile[]>([]);
  const [driveFolders, setDriveFolders] = useState<DriveFolder[]>([]);
  const [driveCurrentFolder, setDriveCurrentFolder] = useState<DriveFolder | null>(null);
  const [driveFolderStack, setDriveFolderStack] = useState<DriveFolder[]>([]);
  const [driveLoading, setDriveLoading] = useState(false);
  const [driveError, setDriveError] = useState<string | null>(null);
  const [attachedImage, setAttachedImage] = useState<DriveFile | null>(null);
  const [attaching, setAttaching] = useState(false);

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
  const socialHandle = result.block?.brand_handle || result.brand_handle || '@brand';
  const selfCheckPassed = result.self_check === 'pass';
  const isFbDraft = result.block?.type === 'fb_page_post_draft';
  const canPublish = hasArtifactAction(run, 'publish') && (!isFbDraft || Boolean(result.block?.page_id));
  const isCreativePost = result.block?.type === 'creative_post_asset' && result.block?.status === 'succeeded';
  const isShortformVideo = (result.block?.type === 'creative_shortform_video' || result.block?.type === 'video_asset') && result.block?.status === 'succeeded';
  const isImageAsset = result.block?.type === 'image_asset' && result.block?.status === 'succeeded';

  // Editable state for creative_post_asset review
  const [editedCaption, setEditedCaption] = useState<string>(result.block?.caption || result.block?.message || '');
  const [swappedAttachment, setSwappedAttachment] = useState<DriveFile | null>(null);

  // Editable state for creative_shortform_video review
  const [editedHookText, setEditedHookText] = useState<string>((result.block as any)?.hook_text || '');
  const [editedCtaText, setEditedCtaText] = useState<string>((result.block as any)?.cta_text || '');
  const [swappedVideo, setSwappedVideo] = useState<DriveFile | null>(null);

  // Editable state for image_asset review
  const [imageCaption, setImageCaption] = useState<string>('');

  // Omni-channel publish selection: options come from the artifact's declared
  // action_modules, readiness comes from the active brand's connected accounts.
  const [brandConnections, setBrandConnections] = useState<SocialConnection[]>([]);
  const [publishSelections, setPublishSelections] = useState<Record<string, boolean>>({});
  const [publishOptionsLoading, setPublishOptionsLoading] = useState(false);
  const actionModules = (result.block as any)?.action_modules as Record<string, string> | undefined;
  const publishOptions = buildPublishOptions(actionModules, brandConnections, result.block?.type);
  const selectedPublishOptions = publishOptions.filter(opt => opt.connected && publishSelections[opt.action]);
  const isOmniPublishAsset = (isShortformVideo || isImageAsset) && Boolean(actionModules);

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
    if (isCreativePost) {
      await handleCreativeApprove();
      return;
    }
    if (canPublish) {
      await handleApproveAndPublish();
      return;
    }
    setReviewStatus('approved');
    removePendingRun(run.run_id);
    try {
      await api.approveRun(run.run_id);
      onApproved?.(run);
    } catch (e) {
      setReviewStatus('pending');
      setRevisionError(e instanceof Error ? e.message : 'Could not approve this artifact.');
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
      removePendingRun(run.run_id);
      await api.approveRun(run.run_id);
      onApproved?.(run);
    } catch (e) {
      setReviewStatus('pending');
      setRevisionError(e instanceof Error ? e.message : 'Could not approve this artifact.');
    } finally {
      setPublishing(false);
    }
  };

  const buildImagePublishOverrides = (): Record<string, unknown> => {
    const b = result.block as any;
    return swappedAttachment ? {
      drive_file_id: swappedAttachment.id,
      drive_file_mime: swappedAttachment.mimeType,
      message: imageCaption.trim() || b?.prompt || '',
    } : {
      _image_data_b64: b?.image_data_b64,
      _image_mime: b?.mime_type || 'image/png',
      message: imageCaption.trim() || b?.prompt || '',
    };
  };

  const handlePublishSelected = async () => {
    if (selectedPublishOptions.length === 0) {
      setRevisionError('Select at least one connected publishing destination.');
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

  const handleApproveAndPublish = async () => {
    setPublishing(true);
    setRevisionError(null);
    try {
      const resp = await api.executeRunAction(run.run_id, 'publish', { confirm: true });
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

  const handleDismiss = () => {
    setReviewStatus('dismissed');
    setModifying(false);
    removePendingRun(run.run_id);
    onDismissed?.(run);
    if (surfaceContext !== 'panel') return;
    api.rejectRun(run.run_id, 'Dismissed from panel.').catch(() => {});
  };

  const loadDrivePickerFolder = useCallback(async (mediaType: string, folder?: DriveFolder | null, stack?: DriveFolder[]) => {
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
      const foldersRes = await api.listDriveFolders(brandId, folder?.id ?? 'root');
      const currentFolder = folder || {
        id: (foldersRes as any).folder_id || 'root',
        name: (foldersRes as any).folder_name || 'My Drive',
      };
      const filesRes = await api.listDriveImages(brandId, currentFolder.id, mediaType);
      setDriveCurrentFolder(currentFolder);
      setDriveFolderStack(stack || []);
      setDriveFolders(foldersRes.folders || []);
      setDriveFiles(filesRes.files || []);
    } catch (e) {
      setDriveError(e instanceof Error ? e.message : 'Could not load Drive files.');
    } finally {
      setDriveLoading(false);
    }
  }, [artifactBrandId]);

  const openDrivePicker = useCallback(async (mediaType?: string) => {
    const mt = mediaType || 'image';
    setDrivePickerOpen(true);
    setDrivePickerMediaType(mt);
    await loadDrivePickerFolder(mt, null, []);
  }, [loadDrivePickerFolder]);

  const selectDriveImage = async (file: DriveFile) => {
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
    setAttaching(true);
    setDriveError(null);
    try {
      await api.attachImageToRun(run.run_id, file.id, file.name, file.mimeType);
      setAttachedImage(file);
      setDrivePickerOpen(false);
    } catch (e) {
      setDriveError(e instanceof Error ? e.message : 'Could not attach image.');
    } finally {
      setAttaching(false);
    }
  };

  const buildRevisionContext = () => {
    const block = result.block || {};
    // Strip large binary fields before serialising — image_data_b64 alone can be >500 KB
    const { image_data_b64: _dropped, ...blockForContext } = block as Record<string, unknown>;
    return [
      `Current module: ${run.module_id}`,
      `Current platform: ${platformLabel}`,
      result.content ? `Current full draft:\n${result.content}` : '',
      Object.keys(blockForContext).length ? `Current structured draft JSON:\n${JSON.stringify(blockForContext, null, 2)}` : '',
    ].filter(Boolean).join('\n\n');
  };

  const handleRevisionSubmit = async () => {
    const note = feedback.trim() || 'Make this draft stronger, clearer, and more conversion-focused while preserving the original intent.';
    const revisionRequest = `${note}\n\nModify the exact draft below. Keep the same platform/module unless I explicitly ask for a different one.\n\n${buildRevisionContext()}`;
    setRevisionBusy(true);
    setRevisionError(null);
    try {
      const history = [
        ...revisionHistory,
        ...localRevisionHistory,
        { role: 'ai' as const, text: buildRevisionContext() },
      ];
      const resp = await api.chatReviseRun(run.run_id, revisionRequest, history);
      const revised = resp.runs?.[0] || resp.run;
      if (!revised) throw new Error('The CMO did not return a revised draft.');
      setRevisionReply(resp.reply);
      setLocalRevisionHistory(prev => [
        ...prev,
        { role: 'user', text: `Revise this ${platformLabel} draft: ${note}` },
        { role: 'ai', text: resp.reply },
      ]);
      if (onRevision) {
        onRevision(resp.reply, revised, run.run_id);
      } else {
        setRevision(revised);
      }
      addPendingRun(revised);
      removePendingRun(run.run_id);
      setReviewStatus('pending');
      setModifying(false);
      setFeedback('');
    } catch (e) {
      setRevisionError(e instanceof Error ? e.message : 'Could not create a revision.');
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
      const succeeded = b.status === 'succeeded';
      const apiDetail = b.details?.response || b.details?.error || '';
      return (
        <div style={{ padding: '18px 20px', fontSize: 13, color: '#1f2937', maxWidth: 520, border: '1px solid #e5e7eb', borderRadius: 12, background: succeeded ? '#f0fdf4' : '#fef2f2' }}>
          <div style={{ fontWeight: 800, fontSize: 15, marginBottom: 8 }}>{succeeded ? 'Facebook post published' : 'Facebook publish failed'}</div>
          <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.45, marginBottom: 10 }}>{b.message_preview || b.message || result.content}</div>
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
        ? swappedAttachment.thumbnailLink
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

    if (result.block?.type === 'image_asset' && result.block?.image_data_b64) {
      const { image_data_b64, mime_type, prompt, width, height } = result.block;
      const src = swappedAttachment ? swappedAttachment.thumbnailLink : `data:${mime_type || 'image/png'};base64,${image_data_b64}`;
      return (
        <DriveSwapContainer kind="image" selectedFile={swappedAttachment} onSwap={() => openDrivePicker('image')} onClear={() => setSwappedAttachment(null)}>
          <div style={{ textAlign: 'center', padding: '12px 0', width: '100%' }}>
            {src ? (
              <img
                src={src}
                alt={swappedAttachment?.name || prompt || 'Generated image'}
                style={{ maxWidth: '100%', borderRadius: 10, display: 'block', margin: '0 auto' }}
              />
            ) : (
              <div style={{ minHeight: 220, border: '1px dashed #d1d5db', borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af' }}>Selected Drive image preview unavailable</div>
            )}
            {prompt && !swappedAttachment && (
              <div style={{ color: '#888', fontSize: 11, marginTop: 8, fontStyle: 'italic' }}>
                {width && height ? `${width}×${height} · ` : ''}{prompt}
              </div>
            )}
          </div>
        </DriveSwapContainer>
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

    if (result.block?.type === 'creative_shortform_video' || result.block?.type === 'video_asset') {
      const b = result.block as any;
      if (b.status !== 'succeeded') {
        return <div style={{ padding: 16, color: '#ef4444', fontSize: 13 }}>{b.message || result.content}</div>;
      }
      const filename = (b.video_path || '').split('/').pop();
      const videoSrc = filename ? `/api/media/video/${filename}` : b.video_url;
      return (
        <DriveSwapContainer kind="video" selectedFile={swappedVideo} onSwap={() => openDrivePicker('video')} onClear={() => setSwappedVideo(null)}>
          <FacebookFeedPreview
            pageName={brandName}
            adCopy={editedHookText || b.hook_text || ''}
            videoSrc={swappedVideo ? undefined : videoSrc}
            imageUrl={swappedVideo?.thumbnailLink}
            ctaText={editedCtaText || b.cta_text || 'Learn More'}
          />
        </DriveSwapContainer>
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
            <div className="artifact-meta">
              {moduleId.includes('strategy_workflow')
                ? 'Strategy Workflow · Draft for review'
                : moduleId.includes('marketing.plan')
                ? 'Plan artifact · Draft for review'
                : moduleId.includes('gbp')
                ? 'Read-only local SEO audit'
                : `${activeCampaign?.name ? `Campaign: ${activeCampaign.name}` : 'Campaign: Unassigned'} · ${platformLabel}`}

            </div>
          </div>
          <span className="artifact-status" style={{ color: statusColor(reviewStatus), borderColor: statusColor(reviewStatus) }}>
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

        {isCreativePost && reviewStatus !== 'dismissed' && (
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
                    {swappedAttachment.thumbnailLink
                      ? <img src={swappedAttachment.thumbnailLink} alt={swappedAttachment.name} style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 6, border: '1px solid #e5e7eb', flexShrink: 0 }} />
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

        {isShortformVideo && reviewStatus !== 'dismissed' && (
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
                    {swappedVideo.thumbnailLink
                      ? <img src={swappedVideo.thumbnailLink} alt={swappedVideo.name} style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 6, border: '1px solid #e5e7eb', flexShrink: 0 }} />
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
                  const fname = (b?.video_path || '').split('/').pop();
                  const src = fname ? `/api/media/video/${fname}` : b?.video_url || null;
                  return src
                    ? <video src={src} muted preload="metadata" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 6, border: '1px solid #e5e7eb', flexShrink: 0 }} />
                    : <div style={{ width: 56, height: 56, borderRadius: 6, border: '1px dashed #d1d5db', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 20, flexShrink: 0 }}>🎬</div>;
                })()}
                <button className="artifact-btn ghost" onClick={() => openDrivePicker('video')}>Swap · Drive</button>
              </div>
            </div>
          </>
        )}

        {isImageAsset && reviewStatus !== 'dismissed' && (
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
                    {swappedAttachment.thumbnailLink
                      ? <img src={swappedAttachment.thumbnailLink} alt={swappedAttachment.name} style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 6, border: '1px solid #e5e7eb', flexShrink: 0 }} />
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
                <button className="artifact-btn ghost" onClick={() => openDrivePicker('image')}>Swap · Drive</button>
              </div>
            </div>
          </>
        )}

        {isOmniPublishAsset && reviewStatus !== 'approved' && reviewStatus !== 'dismissed' && reviewStatus !== 'failed' && (
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
            <div style={{ marginTop: 8, fontSize: 11, color: '#6b7280' }}>
              Select every connected channel you want. BOS will publish to all selected destinations after approval.
            </div>
          </div>
        )}

        <div className="artifact-review-bar">
          <div className="artifact-review-note">
            {reviewStatus === 'approved' && 'Approved and removed from needs-attention.'}
            {reviewStatus === 'draft' && 'Saved as a draft. It will not block approvals.'}
            {reviewStatus === 'dismissed' && 'Dismissed from the review queue.'}
            {reviewStatus === 'failed' && 'Generation failed. Configure credentials, retry, or dismiss.'}
            {reviewStatus === 'pending' && (selfCheckPassed ? 'Self-check passed. Waiting for your review.' : 'Self-check flagged this. Review before approving.')}
          </div>
          <div className="artifact-actions">
            {reviewStatus === 'failed' && (
              <>
                <button className="artifact-btn ghost" onClick={handleDismiss}>Dismiss</button>
                <button className="artifact-btn ghost" onClick={() => { window.location.href = '/admin/modules'; }}>Configure</button>
                <button className="artifact-btn primary" onClick={() => { setModifying(v => !v); addPendingRun(run); }}>Retry</button>
              </>
            )}
            {reviewStatus !== 'approved' && reviewStatus !== 'failed' && (
              <>
                <button className="artifact-btn ghost" onClick={handleDismiss}>Dismiss</button>
                {!isCreativePost && !isShortformVideo && !isImageAsset && <button className="artifact-btn ghost" onClick={handleSaveDraft}>Save draft</button>}
                <button className="artifact-btn ghost" onClick={() => { setModifying(v => !v); addPendingRun(run); }}>Revise</button>
                {isFbDraft && (
                  <button className="artifact-btn ghost" onClick={() => openDrivePicker()} disabled={attaching}>
                    {attachedImage ? '🖼 Change image' : 'Attach image'}
                  </button>
                )}
                {(() => {
                  if (isOmniPublishAsset) {
                    return (
                      <>
                        <button
                          className={selectedPublishOptions.length > 0 ? 'artifact-btn ghost' : 'artifact-btn primary'}
                          onClick={handleApprove}
                          disabled={publishing}
                        >
                          {publishing ? 'Working…' : 'Approve'}
                        </button>
                        <button
                          className="artifact-btn primary"
                          onClick={handlePublishSelected}
                          disabled={publishing || selectedPublishOptions.length === 0}
                        >
                          {publishing ? 'Publishing…' : 'Approve & Publish Selected'}
                        </button>
                      </>
                    );
                  }
                  return (
                    <button className="artifact-btn primary" onClick={handleApprove} disabled={publishing}>
                      {publishing ? 'Publishing…' : (canPublish && !isCreativePost ? 'Approve & Publish' : 'Approve')}
                    </button>
                  );
                })()}
              </>
            )}
            {reviewStatus === 'approved' && (
              <button className="artifact-btn ghost" onClick={() => { setReviewStatus('pending'); addPendingRun(run); }}>Reopen</button>
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
      </div>

      {modifying && !revision && (
        <div className="artifact-revision-box">
          <div className="artifact-section-label">Revision direction</div>
          <textarea
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
            placeholder={`Tell the CMO what is not working — e.g. keep the opening, make the CTA stronger, try a warmer angle...`}
            rows={3}
            className="artifact-revision-input"
            disabled={revisionBusy}
          />
          {revisionError && <div className="artifact-error">{revisionError}</div>}
          <div className="artifact-revision-actions">
            <button className="artifact-btn ghost" onClick={() => setModifying(false)} disabled={revisionBusy}>Cancel</button>
            <button className="artifact-btn primary" onClick={handleRevisionSubmit} disabled={revisionBusy}>
              {revisionBusy ? 'Updating…' : 'Create revision'}
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

      {drivePickerOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onClick={e => { if (e.target === e.currentTarget) setDrivePickerOpen(false); }}>
          <div style={{ background: '#fff', borderRadius: 14, padding: 24, width: 480, maxWidth: '95vw', maxHeight: '80vh', display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontWeight: 700, fontSize: 15 }}>
                {isShortformVideo ? 'Swap video from Drive' : (isCreativePost || isImageAsset) ? 'Swap image from Drive' : 'Attach image from Drive'}
              </div>
              <button style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: '#6b7280' }} onClick={() => setDrivePickerOpen(false)}>✕</button>
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
                      loadDrivePickerFolder(drivePickerMediaType, parent, nextStack);
                    }}
                    disabled={driveLoading}
                  >
                    Back
                  </button>
                )}
                <span>Folder: <strong style={{ color: '#111827' }}>{driveCurrentFolder.name}</strong></span>
              </div>
            )}
            {driveLoading && <div style={{ color: '#6b7280', fontSize: 13 }}>Loading folders and {drivePickerMediaType === 'video' ? 'videos' : 'images'} from Drive…</div>}
            {driveError && <div style={{ color: '#ef4444', fontSize: 13 }}>{driveError}</div>}
            {!driveLoading && !driveError && driveFolders.length === 0 && driveFiles.length === 0 && (
              <div style={{ color: '#6b7280', fontSize: 13 }}>No folders or {drivePickerMediaType === 'video' ? 'video files' : 'images'} found in this Drive folder.</div>
            )}
            {!driveLoading && (driveFolders.length > 0 || driveFiles.length > 0) && (
              <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
                {driveFolders.map(folder => (
                  <button key={folder.id}
                    style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 7, cursor: 'pointer', textAlign: 'left', fontSize: 13 }}
                    onClick={() => loadDrivePickerFolder(drivePickerMediaType, folder, [...driveFolderStack, folder])}>
                    <span style={{ fontSize: 20, flexShrink: 0 }}>📁</span>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{folder.name}</div>
                      <div style={{ color: '#9a3412', fontSize: 11 }}>Open folder</div>
                    </div>
                  </button>
                ))}
                {driveFiles.map(f => {
                  const isSelected = isShortformVideo
                    ? swappedVideo?.id === f.id
                    : (isCreativePost || isImageAsset)
                      ? swappedAttachment?.id === f.id
                      : attachedImage?.id === f.id;
                  const isVideo = f.mimeType?.startsWith('video/');
                  return (
                    <button key={f.id} disabled={attaching}
                      style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', background: isSelected ? '#f0fdf4' : '#f9fafb', border: `1px solid ${isSelected ? '#86efac' : '#e5e7eb'}`, borderRadius: 7, cursor: 'pointer', textAlign: 'left', fontSize: 13 }}
                      onClick={() => selectDriveImage(f)}>
                      {f.thumbnailLink
                        ? <img src={f.thumbnailLink} alt={f.name} style={{ width: 44, height: 44, objectFit: 'cover', borderRadius: 5, flexShrink: 0, border: '1px solid #e5e7eb' }} />
                        : <span style={{ fontSize: 20, flexShrink: 0 }}>{isVideo ? '🎬' : '🖼'}</span>
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
