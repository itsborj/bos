export function StatusBadge({ status }: { status: string }) {
  const cls =
    status === 'success' ? 'badge-success' :
    status === 'partial' ? 'badge-warning' :
    status === 'failed'  ? 'badge-error'   : 'badge-muted';
  return <span className={`badge ${cls}`}>{status}</span>;
}
