import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import type { BrandResponse, OnboardingStatus, PluginInfo, SocialConnectionResponse } from '../../api/types';

type ReadinessRow = {
  brand: BrandResponse;
  status: OnboardingStatus | null;
  connections: SocialConnectionResponse[];
  plugins: PluginInfo[];
  driveRootName: string | null;
};

function isActive(plugin: PluginInfo, brandId: string): boolean {
  const brandRow = plugin.activation_by_brand?.find(a => a.brand_id === brandId);
  const orgRow = plugin.activation_by_brand?.find(a => a.brand_id === null);
  return (brandRow || orgRow)?.status === 'active';
}

function connected(connections: SocialConnectionResponse[], platform: string): boolean {
  return connections.some(c => c.platform === platform && c.status === 'connected');
}

function StatusCell({ ok, label, warnLabel }: { ok: boolean; label: string; warnLabel?: string }) {
  return (
    <span className={`badge badge-${ok ? 'success' : 'warning'}`} style={{ whiteSpace: 'nowrap' }}>
      {ok ? label : (warnLabel || 'Missing')}
    </span>
  );
}

function readinessBlockers(row: ReadinessRow): string[] {
  const profileDone = Boolean(row.status?.brand_profile_configured || row.brand.voice || row.brand.tone || row.brand.values?.length);
  const kitDone = Boolean(row.status?.campaign_brand_kit_approved);
  const hasDrive = connected(row.connections, 'google_drive');
  const driveReady = hasDrive && Boolean(row.driveRootName);
  const installedUsablePlugins = row.plugins.filter(p => p.status === 'installed' && !p.plugin_id.toLowerCase().includes('test_stub'));
  const activePlugins = installedUsablePlugins.filter(p => isActive(p, row.brand.id));

  const blockers: string[] = [];
  if (!profileDone) blockers.push('Import brand brief');
  if (!kitDone) blockers.push('Approve brand kit');
  if (!hasDrive) blockers.push('Connect Drive');
  else if (!driveReady) blockers.push('Choose Drive folder');
  if (installedUsablePlugins.length > 0 && activePlugins.length === 0) blockers.push('Activate capabilities');
  return blockers;
}

export function AdminClientReadiness() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<ReadinessRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError('');
      try {
        const [brandResult, allConnections] = await Promise.all([
          api.getBrands().catch(() => ({ brands: [] as BrandResponse[], total: 0 })),
          api.listSocialConnections().catch(() => [] as SocialConnectionResponse[]),
        ]);

        const data = await Promise.all((brandResult.brands ?? []).map(async brand => {
          const brandConnections = (allConnections as SocialConnectionResponse[]).filter(c => c.brand_id === brand.id);
          const [status, pluginResult, driveRoot] = await Promise.all([
            api.getOnboardingStatus(brand.id).catch(() => null),
            api.listPlugins(brand.id).catch(() => ({ plugins: [] as PluginInfo[] })),
            brandConnections.some(c => c.platform === 'google_drive')
              ? api.listDriveFolders(brand.id).then(r => r.folder_id && r.folder_id !== 'root' ? (r.folder_name || r.folder_id || null) : null).catch(() => null)
              : Promise.resolve(null),
          ]);
          return {
            brand,
            status,
            connections: brandConnections,
            plugins: pluginResult.plugins ?? [],
            driveRootName: driveRoot,
          };
        }));

        if (!cancelled) setRows(data);
      } catch (e: unknown) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Could not load client readiness.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => { cancelled = true; };
  }, []);

  const summary = useMemo(() => {
    const ready = rows.filter(row => readinessBlockers(row).length === 0).length;
    const blocked = rows.length - ready;
    const approvals = rows.filter(row => row.status?.brand_profile_configured && !row.status?.campaign_brand_kit_approved).length;
    const integrationDebt = rows.filter(row => !connected(row.connections, 'google_drive') || (connected(row.connections, 'google_drive') && !row.driveRootName)).length;
    return { ready, blocked, approvals, integrationDebt };
  }, [rows]);

  function goToNext(row: ReadinessRow) {
    const blockers = readinessBlockers(row);
    if (blockers[0]?.includes('brief') || blockers[0]?.includes('kit')) {
      navigate('/admin/onboarding', { state: { brand_id: row.brand.id, brand_name: row.brand.name } });
      return;
    }
    if (blockers[0]?.includes('Drive')) {
      navigate(`/admin/brands/${row.brand.id}?tab=integrations`);
      return;
    }
    if (blockers[0]?.includes('capabilities')) {
      navigate('/admin/modules');
      return;
    }
    navigate(`/admin/brands/${row.brand.id}`);
  }

  if (loading) return <div className="admin-page"><div className="loading-full"><span className="spinner" /></div></div>;

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">Client Readiness</div>
          <div className="admin-page-subtitle">One place to see which brands can safely use the CMO, store assets, and publish.</div>
        </div>
        <button className="btn btn-dark btn-sm" onClick={() => navigate('/admin/brands')}>+ Add / manage brands</button>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="admin-stat-grid">
        <div className="admin-stat-card"><div className="admin-stat-label">Ready Clients</div><div className="admin-stat-value">{summary.ready}</div></div>
        <div className="admin-stat-card"><div className="admin-stat-label">Blocked Clients</div><div className="admin-stat-value" style={{ color: summary.blocked ? 'var(--accent)' : undefined }}>{summary.blocked}</div></div>
        <div className="admin-stat-card"><div className="admin-stat-label">Brand Kits Pending</div><div className="admin-stat-value">{summary.approvals}</div></div>
        <div className="admin-stat-card"><div className="admin-stat-label">Drive Setup Debt</div><div className="admin-stat-value">{summary.integrationDebt}</div></div>
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Readiness matrix</div>
        {rows.length === 0 ? (
          <div className="empty-state" style={{ padding: '36px 0' }}>
            <div className="empty-state-title">No clients yet</div>
            <div className="empty-state-text">Create a brand/client first, then import its brief and connect publishing accounts.</div>
            <button className="btn btn-dark btn-sm" style={{ marginTop: 12 }} onClick={() => navigate('/admin/brands')}>Create first brand →</button>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Client / Brand</th>
                  <th>Brief</th>
                  <th>Brand Kit</th>
                  <th>Drive</th>
                  <th>Publish Channels</th>
                  <th>Capabilities</th>
                  <th>Next action</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(row => {
                  const blockers = readinessBlockers(row);
                  const profileDone = Boolean(row.status?.brand_profile_configured || row.brand.voice || row.brand.tone || row.brand.values?.length);
                  const kitDone = Boolean(row.status?.campaign_brand_kit_approved);
                  const driveConnected = connected(row.connections, 'google_drive');
                  const driveReady = driveConnected && Boolean(row.driveRootName);
                  const channels = ['facebook', 'youtube', 'tiktok', 'google_business'].filter(platform => connected(row.connections, platform));
                  const installed = row.plugins.filter(p => p.status === 'installed' && !p.plugin_id.toLowerCase().includes('test_stub'));
                  const active = installed.filter(p => isActive(p, row.brand.id));
                  return (
                    <tr key={row.brand.id}>
                      <td>
                        <button className="btn btn-ghost btn-sm" style={{ padding: 0, fontWeight: 700 }} onClick={() => navigate(`/admin/brands/${row.brand.id}`)}>
                          {row.brand.name}
                        </button>
                        {row.brand.domain && <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 2 }}>{row.brand.domain}</div>}
                      </td>
                      <td><StatusCell ok={profileDone} label="Imported" /></td>
                      <td><StatusCell ok={kitDone} label="Approved" warnLabel={profileDone ? 'Needs approval' : 'Missing'} /></td>
                      <td>
                        <StatusCell ok={driveReady} label={row.driveRootName ? `Root: ${row.driveRootName}` : 'Ready'} warnLabel={driveConnected ? 'Choose folder' : 'Not connected'} />
                      </td>
                      <td style={{ fontSize: 12, color: channels.length ? 'var(--text)' : 'var(--text2)' }}>
                        {channels.length ? channels.map(p => p.replace('google_business', 'GBP')).join(', ') : 'No publish channel'}
                      </td>
                      <td>
                        <span className={`badge badge-${active.length ? 'success' : installed.length ? 'warning' : 'muted'}`}>
                          {active.length ? `${active.length} active` : installed.length ? 'Inactive' : 'None installed'}
                        </span>
                      </td>
                      <td>
                        {blockers.length === 0 ? (
                          <button className="btn btn-secondary btn-sm" onClick={() => navigate('/cmo')}>Go to CMO →</button>
                        ) : (
                          <button className="btn btn-dark btn-sm" onClick={() => goToNext(row)}>{blockers[0]} →</button>
                        )}
                        {blockers.length > 1 && <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 4 }}>+ {blockers.length - 1} more blocker{blockers.length > 2 ? 's' : ''}</div>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
