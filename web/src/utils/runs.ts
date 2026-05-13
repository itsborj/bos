export const MODULE_META: Record<string, { short: string; platform: string; color: string }> = {
  'marketing.channel.facebook.paid.ads.copy': { short: 'FB Ad',     platform: 'Facebook',  color: '#4267B2' },
  'marketing.channel.twitter.paid.ads.copy':  { short: 'X Ad',      platform: 'Twitter/X', color: '#000000' },
  'marketing.channel.google.paid_search.ads.text':   { short: 'Google Ad', platform: 'Google',    color: '#EA4335' },
  // Legacy flat IDs remain for historical run records.
  'marketing.ad_copy.facebook': { short: 'FB Ad',     platform: 'Facebook',  color: '#4267B2' },
  'marketing.ad_copy.twitter':  { short: 'X Ad',      platform: 'Twitter/X', color: '#000000' },
  'marketing.ad_copy.google':   { short: 'Google Ad', platform: 'Google',    color: '#EA4335' },
};

export function moduleLabel(moduleId: string) {
  return MODULE_META[moduleId] ?? {
    short:    moduleId.split('.').pop() ?? moduleId,
    platform: moduleId,
    color:    '#8e8e93',
  };
}

export function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1)  return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs}h ago`;
  return new Date(iso).toLocaleDateString();
}

export function runTagProps(status: string): { cls: string; label: string } {
  if (status === 'success') return { cls: 'run-tag-success', label: 'Live' };
  if (status === 'failed')  return { cls: 'run-tag-failed',  label: 'Failed' };
  return                           { cls: 'run-tag-mock',    label: 'Mock' };
}

export function wsBadgeProps(status: string): { cls: string; label: string } {
  if (status === 'success') return { cls: 'badge-live', label: 'Live' };
  if (status === 'failed')  return { cls: 'badge-done', label: 'Failed' };
  return                           { cls: 'badge-mock', label: 'Mock' };
}
