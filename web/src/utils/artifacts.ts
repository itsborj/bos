import type { RunResponse } from '../api/types';

export type ArtifactStatus = 'pending_review' | 'approved' | 'dismissed' | 'saved' | 'failed';

export interface ArtifactRef {
  artifact_id: string;
  title: string;
  type: 'draft_artifact' | 'plan_artifact' | 'intelligence_artifact' | 'action_result' | 'decision_artifact' | 'setup_blocker';
  status: ArtifactStatus;
  renderer: string;
  workspace_url: string;
}

export function titleCase(value: string): string {
  return value
    .replace(/[_-]/g, ' ')
    .split(' ')
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export function artifactTitle(run: RunResponse): string {
  if (!run?.module_id) return 'Artifact';
  const id = run.module_id.toLowerCase();
  const platform = titleCase(run.result?.platform || run.module_id.split('.').pop() || 'asset');
  const platformKey = platform.toLowerCase();
  const block = (run.result?.block || {}) as any;
  const blockTitle = String(block.display_title || block.title || '').trim();
  if (blockTitle) return blockTitle;
  if (id.includes('strategy_workflow')) return 'Strategy Workflow';
  if (id.includes('storyboard.motion')) return 'Previs Motion Draft';
  if (id.includes('storyboard.render')) return 'Storyboard Image';
  if (id.includes('storyboard')) return 'Storyboard Draft';
  if ((run.result?.block as any)?.type === 'imprint_draft' || id === 'imprint.draft') return 'Creative Copy Draft';
  if ((run.result?.block as any)?.type === 'imprint_asset' || id.includes('imprint.generate')) return 'Imprint PNG';
  if (id.includes('gtm_plan') || id.includes('gtm')) return 'GTM Strategy';
  if ((id.includes('email') || id.includes('gmail') || platformKey.includes('email')) && id.includes('plan')) return 'Email Campaign Plan';
  if (id.includes('email') || id.includes('gmail') || platformKey.includes('email')) return 'Email Draft';
  if (id.includes('gbp') || platformKey.includes('google business')) return 'Google Business Profile Audit';
  if (id.includes('plan')) return 'Campaign Plan';
  if (id.includes('report') || id.includes('analytics') || id.includes('inbox') || id.includes('read')) return 'Marketing Intelligence';
  if (id.includes('google')) return 'Google Ad Draft';
  if (id.includes('facebook')) return 'Facebook Draft';
  if (id.includes('instagram')) return 'Instagram Draft';
  if (id.includes('twitter') || id.includes('x.')) return 'Social Post Draft';
  if (id.includes('pinterest')) return 'Pinterest Draft';
  if ((run.result?.block as any)?.status === 'failed') return `${platform} Failed`;
  return `${platform} Artifact`;
}

export function artifactType(run: RunResponse): ArtifactRef['type'] {
  if (!run?.module_id) return 'draft_artifact';
  const id = run.module_id.toLowerCase();
  if ((run.result?.block as any)?.status === 'failed') return 'setup_blocker';
  if ((run.result?.block as any)?.type === 'gbp_completeness_result' || id.includes('gbp')) return 'intelligence_artifact';
  if (id.includes('plan')) return 'plan_artifact';
  if (id.includes('report') || id.includes('analytics') || id.includes('inbox') || id.includes('read')) return 'intelligence_artifact';
  if (id.includes('send') || id.includes('publish') || id.includes('action')) return 'action_result';
  return 'draft_artifact';
}

export function artifactStatus(run: RunResponse): ArtifactStatus {
  const status = run.approval_status || (run as any).approval_status || (run.result as any)?.approval_status;
  if (run.status === 'failed' || (run.result?.block as any)?.status === 'failed') return 'failed';
  if (status === 'approved') return 'approved';
  if (status === 'dismissed') return 'dismissed';
  if (status === 'rejected' || status === 'revised') return 'pending_review';
  if (status === 'pending') return 'pending_review';
  return run.result?.self_check === 'pass' ? 'pending_review' : 'saved';
}

export function artifactRenderer(run: RunResponse): string {
  if (!run?.module_id) return 'artifact_detail';
  const id = run.module_id.toLowerCase();
  const channel = `${id} ${(run.result?.platform || '').toLowerCase()}`;
  if (id.includes('strategy_workflow')) return 'strategy_workflow_preview';
  if (id.includes('storyboard')) return 'storyboard_preview';
  if (id.includes('imprint') || (run.result?.block as any)?.type === 'imprint_draft') return 'imprint_draft_preview';
  if (id.includes('gtm_plan') || id.includes('gtm')) return 'gtm_strategy_preview';
  if (channel.includes('email')) return 'email_preview';
  if ((run.result?.block as any)?.type === 'gbp_completeness_result' || id.includes('gbp')) return 'gbp_completeness_preview';
  if (id.includes('google') && (id.includes('text') || id.includes('search'))) return 'google_search_preview';
  if (channel.includes('google') && channel.includes('display')) return 'google_display_preview';
  if (channel.includes('facebook')) return 'facebook_feed_preview';
  if (channel.includes('instagram') && channel.includes('story')) return 'instagram_story_preview';
  if (channel.includes('instagram')) return 'instagram_feed_preview';
  if (channel.includes('twitter') || id.includes('twitter') || id.includes('.x.')) return 'twitter_feed_preview';
  if (channel.includes('pinterest')) return 'pinterest_preview';
  if (artifactType(run) === 'intelligence_artifact') return 'performance_report';
  return 'artifact_detail';
}

export function buildArtifactRef(run: RunResponse): ArtifactRef {
  const renderer = artifactRenderer(run);
  const workflowUrl = renderer === 'strategy_workflow_preview' ? (run.result?.block?.workflow_url as string | undefined) : undefined;
  return {
    artifact_id: run.run_id,
    title: artifactTitle(run),
    type: artifactType(run),
    status: artifactStatus(run),
    renderer,
    workspace_url: workflowUrl || `/workspace/artifacts/${run.run_id}`,
  };
}

export function artifactStatusLabel(status: ArtifactStatus): string {
  if (status === 'approved') return 'Approved';
  if (status === 'dismissed') return 'Deleted';
  if (status === 'failed') return 'Failed';
  if (status === 'saved') return 'Saved';
  return 'Needs approval';
}

export function sanitizeArtifactPreviewText(value: string | null | undefined): string {
  const text = String(value || '').trim();
  if (!text) return '';
  const blockedFragments = [
    'reference assets provided',
    'apply the json revision spec exactly',
    'you are editing an existing approved social ad',
    'are editing an existing approved social ad',
    'apply this change only',
    'do not redesign the ad',
    'do not change copy unless the json says to',
    'contact sheet layout',
    '1024x1024 brand social media post',
  ];
  const blockedPrefixes = [
    'template:',
    'format:',
    'headline:',
    'subheadline:',
    'body copy:',
    'body:',
    'cta:',
    'visual direction:',
    'asset/brand notes:',
    'campaign:',
    'json_revision_spec:',
    'source_render_spec:',
    'revision source panel:',
    'reference left:',
    'reference right:',
  ];

  const kept: string[] = [];
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) {
      if (kept.length && kept[kept.length - 1] !== '') kept.push('');
      continue;
    }
    const lowered = line.toLowerCase();
    if (blockedFragments.some(fragment => lowered.includes(fragment))) continue;
    if (blockedPrefixes.some(prefix => lowered.startsWith(prefix))) continue;
    kept.push(line);
  }

  while (kept.length && kept[kept.length - 1] === '') kept.pop();
  return kept.join('\n').trim();
}
