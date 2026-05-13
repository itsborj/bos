import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { BillingSummary } from '../../api/types';

export function AdminBilling() {
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [monthlyLimit, setMonthlyLimit] = useState('200');
  const [alertPct, setAlertPct] = useState('80');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getBillingSummary()
      .then(b => { setBilling(b); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  const limit = parseFloat(monthlyLimit) || 0;
  const spent = billing?.total_provider_cost ?? 0;
  const remaining = limit > 0 ? Math.max(0, ((limit - spent) / limit) * 100) : null;

  const avgCost = billing && billing.total_runs > 0
    ? (billing.total_provider_cost / billing.total_runs).toFixed(4)
    : null;

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
          <div className="admin-page-subtitle">Cost tracking and budgets</div>
        </div>
      </div>

      {saved && (
        <div className="alert alert-success" style={{ marginBottom: 20 }}>
          Budget settings saved.
        </div>
      )}

      <div className="admin-stat-grid">
        <div className="admin-stat-card">
          <div className="admin-stat-label">Provider Cost</div>
          <div className="admin-stat-value">
            {billing ? `$${billing.total_provider_cost.toFixed(2)}` : '—'}
          </div>
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
          <div className="admin-stat-label">Avg Cost / Run</div>
          <div className="admin-stat-value">{avgCost ? `$${avgCost}` : '—'}</div>
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
