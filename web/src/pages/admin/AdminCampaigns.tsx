import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { CampaignOut } from '../../api/types';

const STATUS_META: Record<string, { label: string; cls: string }> = {
  draft:    { label: 'Draft',    cls: 'badge-muted' },
  active:   { label: 'Active',   cls: 'badge-success' },
  complete: { label: 'Complete', cls: 'badge-info' },
  archived: { label: 'Archived', cls: 'badge-muted' },
};

const STATUS_FLOW = ['draft', 'active', 'complete', 'archived'];

function statusMeta(status: string) {
  return STATUS_META[status] ?? { label: status, cls: 'badge-muted' };
}

function nextStatus(current: string): string | null {
  const idx = STATUS_FLOW.indexOf(current);
  return idx >= 0 && idx < STATUS_FLOW.length - 1 ? STATUS_FLOW[idx + 1] : null;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const d = Math.floor(diff / 86400000);
  if (d < 1) return 'Today';
  if (d === 1) return 'Yesterday';
  if (d < 30) return `${d}d ago`;
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' });
}

export function AdminCampaigns() {
  const [campaigns, setCampaigns] = useState<CampaignOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState('');
  const [saving, setSaving] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listCampaigns()
      .then(setCampaigns)
      .catch(() => setError('Could not load campaigns.'))
      .finally(() => setLoading(false));
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const name = newName.trim();
    if (!name) return;
    setSaving(true);
    setError(null);
    try {
      const created = await api.createCampaign({ name, status: 'draft' });
      setCampaigns(prev => [created, ...prev]);
      setNewName('');
      setAdding(false);
    } catch {
      setError('Failed to create campaign.');
    } finally {
      setSaving(false);
    }
  }

  async function handleAdvance(campaign: CampaignOut) {
    const next = nextStatus(campaign.status);
    if (!next) return;
    setUpdatingId(campaign.id);
    try {
      const updated = await api.updateCampaign(campaign.id, { status: next });
      setCampaigns(prev => prev.map(c => c.id === campaign.id ? updated : c));
    } catch {
      setError('Failed to update status.');
    } finally {
      setUpdatingId(null);
    }
  }

  const active = campaigns.filter(c => c.status === 'active');
  const draft = campaigns.filter(c => c.status === 'draft');
  const done = campaigns.filter(c => c.status === 'complete' || c.status === 'archived');

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">Campaigns</div>
          <div className="admin-page-subtitle">Track briefs from draft through to completion</div>
        </div>
        {!adding && (
          <button className="btn btn-dark" onClick={() => setAdding(true)}>
            + New Campaign
          </button>
        )}
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 16 }} onClick={() => setError(null)}>
          {error}
        </div>
      )}

      {adding && (
        <form onSubmit={handleCreate}>
          <div className="admin-card" style={{ marginBottom: 20 }}>
            <div className="admin-card-title">New Campaign</div>
            <div className="form-group" style={{ marginBottom: 16 }}>
              <label className="label">Campaign Name</label>
              <input
                className="input"
                placeholder="e.g. June Lead Push, Q3 Brand Awareness"
                value={newName}
                onChange={e => setNewName(e.target.value)}
                autoFocus
              />
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button type="submit" className="btn btn-dark" disabled={!newName.trim() || saving}>
                {saving ? 'Creating…' : 'Create Campaign'}
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => { setAdding(false); setNewName(''); }}>
                Cancel
              </button>
            </div>
          </div>
        </form>
      )}

      {loading ? (
        <div className="admin-card">
          <div className="loading-full"><span className="spinner" /></div>
        </div>
      ) : campaigns.length === 0 ? (
        <div className="admin-card">
          <div className="empty-state" style={{ padding: '48px 0' }}>
            <div className="empty-state-title">No campaigns yet</div>
            <div className="empty-state-text">
              Create a campaign to group briefs, runs, and artifacts together.
            </div>
            <button
              className="btn btn-secondary btn-sm"
              style={{ marginTop: 12 }}
              onClick={() => setAdding(true)}
            >
              + New Campaign
            </button>
          </div>
        </div>
      ) : (
        <>
          {active.length > 0 && (
            <CampaignSection
              title="Active"
              campaigns={active}
              updatingId={updatingId}
              onAdvance={handleAdvance}
            />
          )}
          {draft.length > 0 && (
            <CampaignSection
              title="Draft"
              campaigns={draft}
              updatingId={updatingId}
              onAdvance={handleAdvance}
            />
          )}
          {done.length > 0 && (
            <CampaignSection
              title="Completed"
              campaigns={done}
              updatingId={updatingId}
              onAdvance={handleAdvance}
            />
          )}
        </>
      )}
    </div>
  );
}

function CampaignSection({
  title,
  campaigns,
  updatingId,
  onAdvance,
}: {
  title: string;
  campaigns: CampaignOut[];
  updatingId: string | null;
  onAdvance: (c: CampaignOut) => void;
}) {
  return (
    <div className="admin-card" style={{ marginBottom: 20 }}>
      <div className="admin-card-title">{title}</div>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Created</th>
              <th style={{ width: 140 }}></th>
            </tr>
          </thead>
          <tbody>
            {campaigns.map(c => {
              const { label, cls } = statusMeta(c.status);
              const next = nextStatus(c.status);
              return (
                <tr key={c.id}>
                  <td style={{ fontWeight: 600 }}>{c.name}</td>
                  <td><span className={`badge ${cls}`}>{label}</span></td>
                  <td style={{ color: 'var(--text2)', fontSize: 12 }}>{timeAgo(c.created_at)}</td>
                  <td>
                    {next && (
                      <button
                        className="btn btn-ghost btn-sm"
                        disabled={updatingId === c.id}
                        onClick={() => onAdvance(c)}
                        style={{ whiteSpace: 'nowrap' }}
                      >
                        {updatingId === c.id ? '…' : `→ ${statusMeta(next).label}`}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
