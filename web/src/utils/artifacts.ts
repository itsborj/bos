import type { RunResponse } from '../api/types';

export type ArtifactStatus = 'pending_review' | 'approved' | 'dismissed' | 'saved' | 'failed';

export interface ArtifactRef {
  artifact_id: string;
  title: string;
  type: 'draft_artifact' | 'plan_artifact' | 'intelligence_artifact' | 'action_result' | 'decision_artifact';
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
  if (id.includes('strategy_workflow')) return 'Strategy Workflow';
  if (id.includes('gtm_plan') || id.includes('gtm')) return 'GTM Strategy';
  if ((id.includes('email') || id.includes('gmail') || platformKey.includes('email')) && id.includes('plan')) return 'Email Campaign Plan';
  if (id.includes('email') || id.includes('gmail') || platformKey.includes('email')) return 'Email Draft';
  if (id.includes('plan')) return 'Campaign Plan';
  if (id.includes('report') || id.includes('analytics') || id.includes('inbox') || id.includes('read')) return 'Marketing Intelligence';
  if (id.includes('google')) return 'Google Ad Draft';
  if (id.includes('facebook')) return 'Facebook Draft';
  if (id.includes('instagram')) return 'Instagram Draft';
  if (id.includes('twitter') || id.includes('x.')) return 'Social Post Draft';
  if (id.includes('pinterest')) return 'Pinterest Draft';
  return `${platform} Artifact`;
}

export function artifactType(run: RunResponse): ArtifactRef['type'] {
  if (!run?.module_id) return 'draft_artifact';
  const id = run.module_id.toLowerCase();
  if (id.includes('plan')) return 'plan_artifact';
  if (id.includes('report') || id.includes('analytics') || id.includes('inbox') || id.includes('read')) return 'intelligence_artifact';
  if (id.includes('send') || id.includes('publish') || id.includes('action')) return 'action_result';
  return 'draft_artifact';
}

export function artifactStatus(run: RunResponse): ArtifactStatus {
  const status = run.approval_status || (run as any).approval_status || (run.result as any)?.approval_status;
  if (run.status === 'failed') return 'failed';
  if (status === 'approved') return 'approved';
  if (status === 'rejected' || status === 'dismissed') return 'dismissed';
  if (status === 'pending') return 'pending_review';
  return run.result?.self_check === 'pass' ? 'pending_review' : 'saved';
}

export function artifactRenderer(run: RunResponse): string {
  if (!run?.module_id) return 'artifact_detail';
  const id = run.module_id.toLowerCase();
  const channel = `${id} ${(run.result?.platform || '').toLowerCase()}`;
  if (id.includes('strategy_workflow')) return 'strategy_workflow_preview';
  if (id.includes('gtm_plan') || id.includes('gtm')) return 'gtm_strategy_preview';
  if (channel.includes('email')) return 'email_preview';
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
  if (status === 'dismissed') return 'Dismissed';
  if (status === 'failed') return 'Failed';
  if (status === 'saved') return 'Saved';
  return 'Needs review';
}
