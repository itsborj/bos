import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import type { AgentStateResponse, BillingSummary, BrandResponse, CampaignOut, RunListItem } from '../../api/types';

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function moduleLabel(moduleId: string): string {
  const id = moduleId.toLowerCase();
  if (id.includes('strategy') || id.includes('plan')) return 'Strategy';
  if (id.includes('image')) return 'Image';
  if (id.includes('video')) return 'Video';
  if (id.includes('post') || id.includes('creative')) return 'Creative';
  if (id.includes('email') || id.includes('copy')) return 'Copy';
  if (id.includes('analytics') || id.includes('seo') || id.includes('search')) return 'Analysis';
  if (id.includes('drive')) return 'Drive';
  return 'Artifact';
}

export function AdminOverview() {
  const [agentState, setAgentState] = useState<AgentStateResponse | null>(null);
  const [brands, setBrands] = useState<BrandResponse[]>([]);
  const [recentRuns, setRecentRuns] = useState<RunListItem[]>([]);
  const [campaigns, setCampaigns] = useState<CampaignOut[]>([]);
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getAgentState().catch(() => null),
      api.getBrands().catch(() => ({ brands: [] as BrandResponse[], total: 0 })),
      api.getRuns({ limit: 8 }).catch(() => null),
      api.listCampaigns().catch(() => [] as CampaignOut[]),
      api.getBillingSummary().catch(() => null),
    ]).then(([state, brandsResp, runs, cams, billingSummary]) => {
      setAgentState(state);
      setBrands(brandsResp?.brands ?? []);
      setRecentRuns(runs?.runs ?? []);
      setCampaigns(cams ?? []);
      setBilling(billingSummary);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div className="admin-page"><div className="loading-full"><span className="spinner" /></div></div>;
  }

  const totalPending = agentState?.total_pending ?? 0;
  const activeCampaigns = campaigns.filter(c => c.status === 'active').length;
  const failedRuns = recentRuns.filter(run => run.status === 'failed').length;
  const brandsWithPending = brands.filter(brand => (agentState?.brands.find(b => b.brand_id === brand.id)?.pending_approvals ?? 0) > 0);

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">Command Centre</div>
          <div className="admin-page-subtitle">Morning scan for approvals, blocked clients, campaign activity, and recent output.</div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Link to="/admin/client-readiness" className="btn btn-secondary btn-sm">Client readiness →</Link>
          <Link to="/admin/agent-activity" className="btn btn-dark btn-sm">Approval queue</Link>
        </div>
      </div>

      <div className="admin-stat-grid">
        <div
          className="admin-stat-card"
          style={{ cursor: totalPending > 0 ? 'pointer' : undefined }}
          onClick={totalPending > 0 ? () => { window.location.href = '/stream'; } : undefined}
        >
          <div className="admin-stat-label">Needs Review</div>
          <div className={`admin-stat-value${totalPending > 0 ? ' admin-stat-value--amber' : ''}`}>
            {totalPending}
          </div>
          <div className="admin-stat-sub">pending approvals</div>
        </div>
        <div className="admin-stat-card">
          <div className="admin-stat-label">Active Campaigns</div>
          <div className="admin-stat-value">{activeCampaigns}</div>
          <div className="admin-stat-sub">of {campaigns.length} total</div>
        </div>
        <div className="admin-stat-card">
          <div className="admin-stat-label">Brands</div>
          <div className="admin-stat-value">{brands.length}</div>
        </div>
        <Link to="/admin/billing" className="admin-stat-card" style={{ textDecoration: 'none', color: 'inherit' }}>
          <div className="admin-stat-label">Platform Spend</div>
          <div className="admin-stat-value">
            {billing ? `$${(billing.platform_provider_cost ?? billing.total_provider_cost).toFixed(2)}` : '—'}
          </div>
          <div className="admin-stat-sub">billing & BYOK usage →</div>
        </Link>
      </div>

      <div className="admin-card" style={{ marginBottom: 16 }}>
        <div className="admin-card-title">Today’s attention queue</div>
        <div style={{ display: 'grid', gap: 10 }}>
          {totalPending > 0 ? (
            <Link to="/admin/agent-activity" style={{ textDecoration: 'none', color: 'inherit' }}>
              <div className="settings-row" style={{ padding: '10px 0' }}>
                <div className="settings-row-info">
                  <div className="settings-row-name">{totalPending} artifact{totalPending !== 1 ? 's' : ''} need human review</div>
                  <div className="settings-row-desc">Approve, reject, or revise before anything can publish.</div>
                </div>
                <span className="badge badge-warning">Review →</span>
              </div>
            </Link>
          ) : (
            <div className="settings-row" style={{ padding: '10px 0' }}>
              <div className="settings-row-info">
                <div className="settings-row-name">No pending approvals</div>
                <div className="settings-row-desc">Generated work is clear for now.</div>
              </div>
              <span className="badge badge-success">Clear</span>
            </div>
          )}
          {failedRuns > 0 && (
            <Link to="/admin/runs" style={{ textDecoration: 'none', color: 'inherit' }}>
              <div className="settings-row" style={{ padding: '10px 0' }}>
                <div className="settings-row-info">
                  <div className="settings-row-name">{failedRuns} recent failed run{failedRuns !== 1 ? 's' : ''}</div>
                  <div className="settings-row-desc">Check setup blockers, credentials, or provider routing.</div>
                </div>
                <span className="badge badge-warning">Debug →</span>
              </div>
            </Link>
          )}
          {brandsWithPending.length > 0 && (
            <div className="settings-row" style={{ padding: '10px 0' }}>
              <div className="settings-row-info">
                <div className="settings-row-name">Brands waiting on review: {brandsWithPending.map(b => b.name).join(', ')}</div>
                <div className="settings-row-desc">Prioritize client-facing work before starting new generation.</div>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="admin-two-col">
        <div className="admin-card">
          <div className="admin-card-title">
            Brands
            <Link to="/admin/brands" className="btn btn-ghost btn-sm">Manage →</Link>
          </div>
          {brands.length === 0 ? (
            <div className="empty-state" style={{ padding: '24px 0' }}>
              <div className="empty-state-text">No brands yet.</div>
              <Link to="/admin/brands" className="btn btn-secondary btn-sm" style={{ marginTop: 8 }}>
                Add brand
              </Link>
            </div>
          ) : (
            <div>
              {brands.map((brand, i) => {
                const brandState = agentState?.brands.find(b => b.brand_id === brand.id);
                const pending = brandState?.pending_approvals ?? 0;
                return (
                  <div
                    key={brand.id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '12px 0',
                      borderBottom: i < brands.length - 1 ? '1px solid var(--border)' : 'none',
                    }}
                  >
                    <div>
                      <Link
                        to={`/admin/brands/${brand.id}`}
                        style={{ fontWeight: 600, color: 'var(--text)', fontSize: 14 }}
                      >
                        {brand.name}
                      </Link>
                      {brand.domain && (
                        <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 2 }}>{brand.domain}</div>
                      )}
                    </div>
                    {pending > 0 ? (
                      <Link
                        to="/stream"
                        className="badge badge-warning"
                        style={{ textDecoration: 'none', cursor: 'pointer' }}
                      >
                        {pending} pending
                      </Link>
                    ) : (
                      <span className="badge badge-success">Up to date</span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="admin-card">
          <div className="admin-card-title">
            Recent Activity
            <Link to="/admin/runs" className="btn btn-ghost btn-sm">All runs →</Link>
          </div>
          {recentRuns.length === 0 ? (
            <div className="empty-state" style={{ padding: '24px 0' }}>
              <div className="empty-state-text">No runs yet. Ask the CMO to generate something.</div>
            </div>
          ) : (
            <div>
              {recentRuns.map((run, i) => (
                <div
                  key={run.run_id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    padding: '10px 0',
                    borderBottom: i < recentRuns.length - 1 ? '1px solid var(--border)' : 'none',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 500, fontSize: 13 }}>
                      {moduleLabel(run.module_id)}
                      {run.brand_name && (
                        <span style={{ color: 'var(--text2)', fontWeight: 400 }}> · {run.brand_name}</span>
                      )}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 2, fontFamily: 'var(--mono)' }}>
                      {run.module_id}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 12 }}>
                    <div style={{ fontSize: 12, color: 'var(--text2)' }}>{timeAgo(run.created_at)}</div>
                    {run.approval_status === 'pending' && (
                      <Link to="/stream">
                        <span className="badge badge-warning" style={{ fontSize: 10, marginTop: 4, display: 'inline-block' }}>
                          review
                        </span>
                      </Link>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
