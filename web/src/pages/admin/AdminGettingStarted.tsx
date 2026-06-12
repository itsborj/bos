import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import type { BrandResponse, OnboardingStatus, ProviderInfo } from '../../api/types';

type BrandReadiness = {
  brand: BrandResponse;
  status: OnboardingStatus | null;
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

function BrandReadinessCard({ item }: { item: BrandReadiness }) {
  const navigate = useNavigate();
  const { brand, status } = item;

  const briefDone   = status?.brand_profile_configured ?? false;
  const kitDone     = status?.campaign_brand_kit_approved ?? false;
  const readyCount  = [briefDone, kitDone].filter(Boolean).length;
  const fullyReady  = briefDone && kitDone;

  function nextAction() {
    if (!briefDone) return navigate('/admin/onboarding', { state: { brand_id: brand.id, brand_name: brand.name } });
    if (!kitDone)   return navigate('/admin/onboarding', { state: { brand_id: brand.id, brand_name: brand.name } });
    navigate(`/admin/brands/${brand.id}`);
  }

  function nextLabel() {
    if (!briefDone) return 'Import Brief →';
    if (!kitDone)   return 'Approve Brand Kit →';
    return 'View Brand →';
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
          {!fullyReady && <span className="badge badge-warning" style={{ fontSize: 10 }}>{readyCount}/2 steps</span>}
        </div>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <StatusDot done={briefDone} label="Brief imported" />
          <StatusDot done={kitDone}   label="Brand kit approved" />
        </div>
      </div>
      <button
        className={`btn btn-sm ${fullyReady ? 'btn-secondary' : 'btn-dark'}`}
        style={{ flexShrink: 0 }}
        onClick={nextAction}
      >
        {nextLabel()}
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
      const statuses = await Promise.all(
        brands.map(b => api.getOnboardingStatus(b.id).catch(() => null))
      );
      setBrandItems(brands.map((b, i) => ({ brand: b, status: statuses[i] })));
    }).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="admin-page">
        <div className="loading-full"><span className="spinner" /></div>
      </div>
    );
  }

  const aiConnected = providers.some(p => p.connected);
  const allBrandsReady = brandItems.length > 0 && brandItems.every(
    item => item.status?.brand_profile_configured && item.status?.campaign_brand_kit_approved
  );

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">Setup</div>
          <div className="admin-page-subtitle">Platform configuration and per-brand readiness</div>
        </div>
      </div>

      {/* ── Section 1: Platform setup ─────────────────────────────────────── */}
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
                ? `${providers.filter(p => p.connected).length} provider${providers.filter(p => p.connected).length !== 1 ? 's' : ''} connected`
                : 'Connect an AI provider or add a BYOK key to activate the CMO'}
            </div>
          </div>
          <button className="btn btn-sm btn-secondary" onClick={() => navigate('/admin/providers')}>
            Manage →
          </button>
        </div>
      </div>

      {/* ── Section 2: Brand readiness ────────────────────────────────────── */}
      <div className="admin-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
          <div className="admin-card-title" style={{ marginBottom: 0 }}>Brand readiness</div>
          <Link to="/admin/brands" className="btn btn-ghost btn-sm">Manage brands →</Link>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 16 }}>
          Each client brand needs a brief and an approved brand kit before the CMO can run campaigns.
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
    </div>
  );
}
