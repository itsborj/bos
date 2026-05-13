import type { BillingSummary, RunListItem } from '../api/types';
import type { BriefingBlock } from '../types/stream';
import { timeAgo } from './runs';

export type StreamItemKind = 'approval' | 'report' | 'status' | 'error';

export interface StreamChannel {
  run_id: string;
  module_id: string;
  channel: string;
  kind: StreamItemKind;
  label: string;
  created_at: string;
}

export interface StreamCampaign {
  campaign_id: string | null;
  campaign_name: string;
  brand_id: string | null;
  channels: StreamChannel[];
  latest_at: string;
  has_pending: boolean;
}

const CHANNEL_PATTERNS: Array<[RegExp, string]> = [
  [/\.facebook\.(paid|ads)/,   'Facebook Paid'],
  [/\.facebook\.(organic)/,    'Facebook Organic'],
  [/\.facebook\./,             'Facebook'],
  [/\.instagram\.(paid|ads)/,  'Instagram Paid'],
  [/\.instagram\.(organic)/,   'Instagram Organic'],
  [/\.instagram\./,            'Instagram'],
  [/\.google\.paid/,           'Google Ads'],
  [/\.google\.(organic|seo)/,  'Google Organic'],
  [/\.google\./,               'Google'],
  [/\.seo\./,                  'SEO'],
  [/\.email\./,                'Email'],
  [/\.pinterest\./,            'Pinterest'],
  [/\.twitter\.|\.x\./,       'Twitter / X'],
  [/\.tiktok\./,               'TikTok'],
  [/analytics|reporting|report/, 'Analytics'],
  [/technical|tracking|pixel|utm/, 'Technical'],
];

export function channelLabel(moduleId: string): string {
  const id = moduleId.toLowerCase();
  for (const [pattern, label] of CHANNEL_PATTERNS) {
    if (pattern.test(id)) return label;
  }
  const parts = moduleId.split('.');
  return parts[parts.length - 1].replace(/_/g, ' ');
}

function itemKind(run: RunListItem): StreamItemKind {
  if (run.status === 'failed') return 'error';
  const id = run.module_id.toLowerCase();
  if (/analytics|report|reporting/.test(id)) return 'report';
  if (/technical|tracking|pixel|utm/.test(id)) return 'status';
  if (run.approval_status === 'pending') return 'approval';
  return 'status';
}

function kindLabel(kind: StreamItemKind, channel: string): string {
  if (kind === 'error') return 'Failed';
  if (kind === 'report') return 'Report ready';
  if (kind === 'status') return 'Complete ✓';
  return `${channel} output ready`;
}

const UNGROUPED_ID = '__ungrouped__';

export function buildCampaignStream(runs: RunListItem[]): StreamCampaign[] {
  const map = new Map<string, StreamCampaign>();

  for (const run of runs) {
    const key = run.campaign_id ?? UNGROUPED_ID;
    if (!map.has(key)) {
      map.set(key, {
        campaign_id: run.campaign_id ?? null,
        campaign_name: run.campaign_name ?? 'Recent runs',
        brand_id: run.brand_id ?? null,
        channels: [],
        latest_at: run.created_at,
        has_pending: false,
      });
    }
    const group = map.get(key)!;
    const kind = itemKind(run);
    const channel = channelLabel(run.module_id);
    group.channels.push({
      run_id: run.run_id,
      module_id: run.module_id,
      channel,
      kind,
      label: kindLabel(kind, channel),
      created_at: run.created_at,
    });
    if (kind === 'approval' || kind === 'error') group.has_pending = true;
    if (run.created_at > group.latest_at) group.latest_at = run.created_at;
  }

  return [...map.values()].sort((a, b) => {
    if (a.has_pending !== b.has_pending) return a.has_pending ? -1 : 1;
    return b.latest_at.localeCompare(a.latest_at);
  });
}

// ── Legacy export — used by ReportsView and AdminReports ──────────────────────
export function buildBriefingStream(summary: BillingSummary | null, runs: RunListItem[]): BriefingBlock[] {
  const stream: BriefingBlock[] = [];

  if (summary && summary.total_runs > 0) {
    stream.push({
      id: 'summary-block',
      timestamp: new Date().toISOString(),
      priority: 'normal',
      category: 'performance',
      layout_hint: 'table',
      interaction: 'passive',
      content: {
        title: "Today's Summary",
        metrics: [
          { label: 'Total Runs',    value: summary.total_runs },
          { label: 'Success Rate',  value: `${Math.round((summary.successful_runs / summary.total_runs) * 100)}%` },
          { label: 'Provider Cost', value: `$${summary.total_provider_cost.toFixed(3)}` },
        ],
      },
    });
  }

  const errors = runs.filter(r => r.status === 'failed');
  if (errors.length > 0) {
    stream.push({
      id: `decision-needed-${errors[0].run_id}`,
      timestamp: errors[0].created_at,
      priority: 'urgent',
      category: 'decision_needed',
      layout_hint: 'alert',
      interaction: 'actionable',
      content: {
        title: 'Action Required',
        message: `${errors.length} module run${errors.length !== 1 ? 's' : ''} failed. ${errors[0].module_id} needs attention.`,
        actionLabel: 'Tell CMO',
        actionRoute: '/cmo',
      },
    });
  }

  runs.filter(r => r.status === 'success').slice(0, 3).forEach(run => {
    stream.push({
      id: `status-${run.run_id}`,
      timestamp: run.created_at,
      priority: 'low',
      category: 'status',
      layout_hint: 'compact',
      interaction: 'expandable',
      content: {
        title: run.module_id,
        status: 'success',
        message: 'Completed successfully',
        timestamp: timeAgo(run.created_at),
        actionLabel: 'View in Workspace',
        actionRoute: '/workspace',
      },
    });
  });

  return stream;
}

export function countPendingDecisions(stream: BriefingBlock[]): number {
  return stream.filter(b => b.category === 'decision_needed').length;
}
