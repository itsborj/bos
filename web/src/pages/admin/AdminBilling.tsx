import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { BillingSummary, BrandResponse } from '../../api/types';

export function AdminBilling() {
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [brands, setBrands] = useState<BrandResponse[]>([]);
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [loading, setLoading] = useState(true);
  const [monthlyLimit, setMonthlyLimit] = useState('200');
  const [alertPct, setAlertPct] = useState('80');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.getBillingSummary(selectedBrandId || null),
      api.getBrands().catch(() => ({ brands: [] as BrandResponse[], total: 0 })),
    ])
      .then(([b, brandResult]) => {
        setBilling(b);
        setBrands(brandResult.brands ?? []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selectedBrandId]);

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  const limit = parseFloat(monthlyLimit) || 0;
  const spent = billing?.platform_provider_cost ?? billing?.total_provider_cost ?? 0;
  const remaining = limit > 0 ? Math.max(0, ((limit - spent) / limit) * 100) : null;

  const avgCost = billing && billing.total_runs > 0
    ? (billing.total_provider_cost / billing.total_runs).toFixed(4)
    : null;
  const platformCost = billing?.platform_provider_cost ?? 0;
  const byokCost = billing?.byok_provider_cost ?? 0;
  const oauthCost = billing?.oauth_provider_cost ?? 0;
  const grossMargin = billing?.gross_margin ?? ((billing?.total_sell_price ?? 0) - platformCost);
  const missingSellPriceRuns = billing?.missing_sell_price_runs ?? 0;
  const missingSellPriceCost = billing?.missing_sell_price_provider_cost ?? 0;
  const sellPriceLooksIncomplete = !!billing && missingSellPriceRuns > 0;

  if (loading) {
    return (
      <div className="admin-page">
        <div className="loading-full"><span className="spinner" /></div>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">Billing</div>
          <div className="admin-page-subtitle">Agency/client cost tracking, BYOK attribution, and budgets</div>
        </div>
        <div style={{ minWidth: 220 }}>
          <label className="label" style={{ fontSize: 12 }}>Scope</label>
          <select className="select" value={selectedBrandId} onChange={e => setSelectedBrandId(e.target.value)}>
            <option value="">All brands / workspace</option>
            {brands.map(brand => (
              <option key={brand.id} value={brand.id}>{brand.name}</option>
            ))}
          </select>
        </div>
      </div>

      {saved && (
        <div className="alert alert-success" style={{ marginBottom: 20 }}>
          Budget settings saved.
        </div>
      )}

      {sellPriceLooksIncomplete && (
        <div className="alert alert-warning" style={{ marginBottom: 20 }}>
          Sell price was missing for {missingSellPriceRuns} successful platform run{missingSellPriceRuns !== 1 ? 's' : ''}
          {' '}(${missingSellPriceCost.toFixed(2)} provider cost). Summary revenue includes an estimated markup for these historical rows until they are backfilled.
        </div>
      )}

      <div className="admin-stat-grid">
        <div className="admin-stat-card">
          <div className="admin-stat-label">Platform Spend</div>
          <div className="admin-stat-value">
            {billing ? `$${platformCost.toFixed(2)}` : '—'}
          </div>
          <div className="admin-stat-sub">Paid by Klaroha/operator keys</div>
        </div>
        <div className="admin-stat-card">
          <div className="admin-stat-label">Sell Price</div>
          <div className="admin-stat-value">
            {billing ? `$${billing.total_sell_price.toFixed(2)}` : '—'}
          </div>
          {remaining != null && (
            <div className="admin-stat-sub" style={{ color: 'var(--success)' }}>
              {remaining.toFixed(0)}% of budget remaining
            </div>
          )}
        </div>
        <div className="admin-stat-card">
          <div className="admin-stat-label">Gross Margin</div>
          <div className="admin-stat-value">{billing ? `$${grossMargin.toFixed(2)}` : '—'}</div>
          {avgCost && <div className="admin-stat-sub">Avg tracked cost/run: ${avgCost}</div>}
        </div>
        <div className="admin-stat-card">
          <div className="admin-stat-label">Total Runs</div>
          <div className="admin-stat-value">{billing?.total_runs ?? '—'}</div>
          {billing && (
            <div className="admin-stat-sub">{billing.successful_runs} successful</div>
          )}
        </div>
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Cost Responsibility</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
          <div>
            <div className="admin-stat-label">Platform</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>${platformCost.toFixed(2)}</div>
            <div style={{ fontSize: 12, color: 'var(--text2)' }}>{(billing?.platform_tokens ?? 0).toLocaleString()} tokens</div>
          </div>
          <div>
            <div className="admin-stat-label">Client BYOK</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>${byokCost.toFixed(2)}</div>
            <div style={{ fontSize: 12, color: 'var(--text2)' }}>{(billing?.byok_tokens ?? 0).toLocaleString()} tokens paid outside Klaroha</div>
          </div>
          <div>
            <div className="admin-stat-label">OAuth / Account Login</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>${oauthCost.toFixed(2)}</div>
            <div style={{ fontSize: 12, color: 'var(--text2)' }}>{(billing?.oauth_tokens ?? 0).toLocaleString()} tokens</div>
          </div>
        </div>
        <div style={{ marginTop: 12, color: 'var(--text2)', fontSize: 13 }}>
          BYOK and OAuth are usage estimates for client/brand-owned credentials; Platform is the operator-paid provider cost.
        </div>
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Token Usage</div>
        {billing?.total_tokens != null ? (
          <div style={{ fontSize: 28, fontWeight: 700 }}>
            {billing.total_tokens.toLocaleString()}
            <span style={{ fontSize: 14, fontWeight: 400, color: 'var(--text2)', marginLeft: 8 }}>tokens</span>
          </div>
        ) : (
          <div style={{ color: 'var(--text2)', fontSize: 13 }}>No token data available.</div>
        )}
        <div style={{ marginTop: 16, color: 'var(--text2)', fontSize: 13 }}>
          Per-specialist cost breakdown requires run-level billing data — coming in a future API update.
        </div>
      </div>

      <div className="admin-card">
        <div className="admin-card-title">Budget Settings</div>
        <form onSubmit={handleSave}>
          <div className="form-group">
            <label className="label">Monthly Budget Limit ($)</label>
            <input
              className="input"
              type="number"
              min="0"
              style={{ width: 160 }}
              value={monthlyLimit}
              onChange={e => setMonthlyLimit(e.target.value)}
            />
            <div className="hint">System will warn when limit is reached.</div>
          </div>
          <div className="form-group">
            <label className="label">Alert Threshold (%)</label>
            <input
              className="input"
              type="number"
              min="0"
              max="100"
              style={{ width: 160 }}
              value={alertPct}
              onChange={e => setAlertPct(e.target.value)}
            />
            <div className="hint">Notify when this % of budget is consumed.</div>
          </div>
          <button type="submit" className="btn btn-dark">Save Budget Settings</button>
        </form>
      </div>
    </div>
  );
}
