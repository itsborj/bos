import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import type { BrandResponse, ProviderInfo } from '../../api/types';
import { loadStreamActivationChecklist, type StreamActivationChecklistItem, type StreamActivationChecklistResult } from '../../utils/streamActivationChecklist';

type BrandReadiness = {
  brand: BrandResponse;
  checklist: StreamActivationChecklistResult | null;
};

function StatusDot({ done, label }: { done: boolean; label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span
        style={{
          width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
          background: done ? 'var(--success, #16a34a)' : 'var(--text3, #94a3b8)',
        }}
      />
      <span style={{ fontSize: 12, color: done ? 'var(--text)' : 'var(--text2)' }}>{label}</span>
    </div>
  );
}

function StatusCell({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`badge badge-${ok ? 'success' : 'warning'}`} style={{ whiteSpace: 'nowrap' }}>
      {label}
    </span>
  );
}

function brandChecks(item: BrandReadiness): StreamActivationChecklistItem[] {
  return (item.checklist?.items || []).filter(check => check.key !== 'ai-provider' && check.key !== 'brand-selected');
}

function getCheck(item: BrandReadiness, key: string): StreamActivationChecklistItem | undefined {
  return item.checklist?.items.find(check => check.key === key);
}

function firstTodo(item: BrandReadiness): StreamActivationChecklistItem | undefined {
  return brandChecks(item).find(check => !check.ok);
}

function isBrandReady(item: BrandReadiness): boolean {
  const checks = brandChecks(item);
  return checks.length > 0 && checks.every(check => check.ok);
}

function nextActionLabel(item: BrandReadiness): string {
  const todo = firstTodo(item);
  if (!item.checklist) return 'Review Setup →';
  if (!todo) return 'Go to CMO →';
  if (todo.key === 'brand-profile') return 'Import Brand Profile →';
  if (todo.key === 'live-campaign') return 'Create Live Campaign →';
  if (todo.key === 'brand-kit') return 'Approve Brand Kit →';
  if (todo.key === 'drive-connected') return 'Connect Drive →';
  if (todo.key === 'drive-folder') return 'Choose Drive Folder →';
  if (todo.key === 'brand-logo') return 'Add Logo →';
  if (todo.key === 'publish-channel') return 'Connect Publish Channel →';
  if (todo.key === 'capabilities') return 'Activate Capability →';
  if (todo.key === 'capability-prerequisites') return 'Configure Capability →';
  return 'Fix Setup →';
}

function driveStatus(item: BrandReadiness): { ok: boolean; label: string } {
  if (!item.checklist) return { ok: false, label: 'Unknown' };
  const connected = getCheck(item, 'drive-connected');
  if (!connected?.ok) return { ok: false, label: connected ? 'Connect Drive' : 'Not connected' };
  const folder = getCheck(item, 'drive-folder');
  if (folder && !folder.ok) return { ok: false, label: 'Choose folder' };
  const logo = getCheck(item, 'brand-logo');
  if (logo && !logo.ok) return { ok: false, label: 'Add logo' };
  return { ok: true, label: 'Ready' };
}

function publishChannelLabel(item: BrandReadiness): string {
  if (!item.checklist) return 'Unknown';
  const publish = getCheck(item, 'publish-channel');
  if (!publish?.ok) return 'No publish channel';
  return publish.detail.replace(/^Connected:\s*/i, '').replace(/\.$/, '') || 'Connected';
}

function capabilityStatus(item: BrandReadiness): { ok: boolean; label: string } {
  if (!item.checklist) return { ok: false, label: 'Unknown' };
  const capabilities = getCheck(item, 'capabilities');
  const prerequisites = getCheck(item, 'capability-prerequisites');
  if (!capabilities) return { ok: true, label: 'None required' };
  if (!capabilities.ok) return { ok: false, label: 'Activate' };
  if (prerequisites && !prerequisites.ok) return { ok: false, label: 'Configure' };
  return { ok: true, label: 'Ready' };
}

function BrandReadinessCard({ item }: { item: BrandReadiness }) {
  const navigate = useNavigate();
  const { brand } = item;
  const checks = brandChecks(item);
  const readyCount = checks.filter(check => check.ok).length;
  const fullyReady = checks.length > 0 && readyCount === checks.length;
  const todo = firstTodo(item);
  const visibleChecks = checks.filter(check => !check.ok || ['brand-profile', 'live-campaign', 'brand-kit', 'drive-folder', 'brand-logo'].includes(check.key)).slice(0, 8);

  function goNext() {
    if (todo) return navigate(todo.to, { state: todo.state });
    if (!item.checklist) return navigate(`/admin/brands/${brand.id}`);
    navigate('/cmo');
  }

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '14px 0',
        borderBottom: '1px solid var(--border)',
        gap: 16,
        flexWrap: 'wrap',
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <span style={{ fontWeight: 700, fontSize: 14 }}>{brand.name}</span>
          {brand.domain && <span style={{ fontSize: 11, color: 'var(--text2)' }}>{brand.domain}</span>}
          {fullyReady && <span className="badge badge-success" style={{ fontSize: 10 }}>Ready</span>}
          {!fullyReady && <span className="badge badge-warning" style={{ fontSize: 10 }}>{readyCount}/{checks.length || 0} steps</span>}
        </div>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          {visibleChecks.map(check => <StatusDot key={check.key} done={check.ok} label={check.label} />)}
        </div>
      </div>
      <button
        className={`btn btn-sm ${fullyReady ? 'btn-secondary' : 'btn-dark'}`}
        style={{ flexShrink: 0 }}
        onClick={goNext}
      >
        {nextActionLabel(item)}
      </button>
    </div>
  );
}

export function AdminGettingStarted() {
  const navigate = useNavigate();
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [brandItems, setBrandItems] = useState<BrandReadiness[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getProviders().catch(() => ({ providers: [] as ProviderInfo[] })),
      api.getBrands().catch(() => ({ brands: [] as BrandResponse[], total: 0 })),
    ]).then(async ([provResult, brandResult]) => {
      setProviders(provResult.providers ?? []);

      const brands = brandResult.brands ?? [];
      const checklists = await Promise.all(
        brands.map(b => loadStreamActivationChecklist(b.id, b.name).catch(() => null))
      );
      setBrandItems(brands.map((b, i) => ({ brand: b, checklist: checklists[i] })));
    }).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="admin-page">
        <div className="loading-full"><span className="spinner" /></div>
      </div>
    );
  }

  const connectedProviders = providers.filter(p => p.connected || p.has_platform_key || p.has_byok_key);
  const aiConnected = connectedProviders.length > 0;
  const readyClients = brandItems.filter(isBrandReady).length;
  const blockedClients = brandItems.length - readyClients;
  const brandKitsPending = brandItems.filter(item => !getCheck(item, 'brand-kit')?.ok).length;
  const driveSetupDebt = brandItems.filter(item => !driveStatus(item).ok).length;
  const onboardingDebt = brandItems.filter(item => !getCheck(item, 'brand-profile')?.ok || !getCheck(item, 'live-campaign')?.ok || !getCheck(item, 'brand-kit')?.ok).length;
  const allBrandsReady = brandItems.length > 0 && brandItems.every(isBrandReady);

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">Setup &amp; Readiness</div>
          <div className="admin-page-subtitle">Platform configuration and per-brand readiness in one place.</div>
        </div>
      </div>

      <div className="admin-card" style={{ marginBottom: 16 }}>
        <div className="admin-card-title" style={{ marginBottom: 4 }}>Platform setup</div>
        <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 16 }}>
          Done once for this deployment. Applies to all brands.
        </div>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '12px 0',
            gap: 12,
            flexWrap: 'wrap',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ fontWeight: 600, fontSize: 14 }}>AI Provider</span>
              <span className={`badge badge-${aiConnected ? 'success' : 'warning'}`} style={{ fontSize: 10 }}>
                {aiConnected ? 'Connected' : 'Not connected'}
              </span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text2)' }}>
              {aiConnected
                ? `${connectedProviders.length} provider${connectedProviders.length !== 1 ? 's' : ''} available`
                : 'Connect an AI provider or add a BYOK key to activate the CMO'}
            </div>
          </div>
          <button className="btn btn-sm btn-secondary" onClick={() => navigate('/admin/providers')}>
            Manage →
          </button>
        </div>
      </div>

      <div className="admin-stat-grid">
        <div className="admin-stat-card"><div className="admin-stat-label">Ready Clients</div><div className="admin-stat-value">{readyClients}</div></div>
        <div className="admin-stat-card"><div className="admin-stat-label">Blocked Clients</div><div className="admin-stat-value" style={{ color: blockedClients ? 'var(--accent)' : undefined }}>{blockedClients}</div></div>
        <div className="admin-stat-card"><div className="admin-stat-label">Brand Kits Pending</div><div className="admin-stat-value">{brandKitsPending}</div></div>
        <div className="admin-stat-card"><div className="admin-stat-label">Drive Setup Debt</div><div className="admin-stat-value">{driveSetupDebt}</div></div>
      </div>

      <div className="admin-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 4 }}>
          <div className="admin-card-title" style={{ marginBottom: 0 }}>Brand onboarding</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button className="btn btn-dark btn-sm" onClick={() => navigate('/admin/onboarding')}>
              Import / update brief →
            </button>
            <Link to="/admin/brands" className="btn btn-ghost btn-sm">Manage brands →</Link>
          </div>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 12 }}>
          Onboarding is the write surface for setup. Use it to import or update a brand brief, extract the live campaign, and generate the Brand Creative Brief. This page stays the single aggregate view for readiness.
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <span className={`badge badge-${onboardingDebt ? 'warning' : 'success'}`}>{onboardingDebt ? `${onboardingDebt} brand${onboardingDebt !== 1 ? 's' : ''} need onboarding work` : 'Onboarding clear'}</span>
          <span className={`badge badge-${brandKitsPending ? 'warning' : 'success'}`}>{brandKitsPending ? `${brandKitsPending} brand kit${brandKitsPending !== 1 ? 's' : ''} pending` : 'Brand kits approved'}</span>
        </div>
      </div>

      <div className="admin-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
          <div className="admin-card-title" style={{ marginBottom: 0 }}>Brand readiness</div>
          <Link to="/admin/brands" className="btn btn-ghost btn-sm">Manage brands →</Link>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 16 }}>
          Each client brand needs profile and campaign context, an approved Brand Creative Brief, Drive asset storage, and required channel integrations before Stream and campaign execution are unblocked.
        </div>

        {brandItems.length === 0 ? (
          <div className="empty-state" style={{ padding: '24px 0' }}>
            <div className="empty-state-text">No brands yet.</div>
            <button
              className="btn btn-dark btn-sm"
              style={{ marginTop: 8 }}
              onClick={() => navigate('/admin/brands')}
            >
              Add first brand →
            </button>
          </div>
        ) : (
          <>
            <div>
              {brandItems.map(item => (
                <BrandReadinessCard key={item.brand.id} item={item} />
              ))}
            </div>
            {allBrandsReady && (
              <div
                style={{
                  marginTop: 16,
                  padding: '12px 16px',
                  background: 'var(--success-bg, #f0fdf4)',
                  borderRadius: 8,
                  fontSize: 13,
                  color: 'var(--success-text, #15803d)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 12,
                  flexWrap: 'wrap',
                }}
              >
                <span>All brands ready — the CMO is fully configured.</span>
                <button className="btn btn-dark btn-sm" onClick={() => navigate('/cmo')}>
                  Go to CMO →
                </button>
              </div>
            )}
          </>
        )}
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Readiness matrix</div>
        <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 16 }}>
          Same setup truth, shown as a per-client matrix with the next action for each brand.
        </div>
        {brandItems.length === 0 ? (
          <div className="empty-state" style={{ padding: '24px 0' }}>
            <div className="empty-state-text">Create a brand first, then complete setup here.</div>
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
                {brandItems.map(item => {
                  const brief = getCheck(item, 'brand-profile');
                  const brandKit = getCheck(item, 'brand-kit');
                  const drive = driveStatus(item);
                  const capabilities = capabilityStatus(item);
                  const todo = firstTodo(item);
                  return (
                    <tr key={item.brand.id}>
                      <td>
                        <button className="btn btn-ghost btn-sm" style={{ padding: 0, fontWeight: 700 }} onClick={() => navigate(`/admin/brands/${item.brand.id}`)}>
                          {item.brand.name}
                        </button>
                        {item.brand.domain && <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 2 }}>{item.brand.domain}</div>}
                      </td>
                      <td><StatusCell ok={Boolean(brief?.ok)} label={brief ? (brief.ok ? 'Imported' : 'Missing') : 'Unknown'} /></td>
                      <td><StatusCell ok={Boolean(brandKit?.ok)} label={brandKit ? (brandKit.ok ? 'Approved' : 'Pending') : 'Unknown'} /></td>
                      <td><StatusCell ok={drive.ok} label={drive.label} /></td>
                      <td style={{ fontSize: 12, color: getCheck(item, 'publish-channel')?.ok ? 'var(--text)' : 'var(--text2)' }}>
                        {publishChannelLabel(item)}
                      </td>
                      <td><StatusCell ok={capabilities.ok} label={capabilities.label} /></td>
                      <td>
                        {todo ? (
                          <button className="btn btn-dark btn-sm" onClick={() => navigate(todo.to, { state: todo.state })}>{nextActionLabel(item)}</button>
                        ) : item.checklist ? (
                          <button className="btn btn-secondary btn-sm" onClick={() => navigate('/cmo')}>Go to CMO →</button>
                        ) : (
                          <button className="btn btn-dark btn-sm" onClick={() => navigate(`/admin/brands/${item.brand.id}`)}>Review Setup →</button>
                        )}
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
