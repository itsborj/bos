import { useState } from 'react';

type Criterion = { key: string; default: string; override: string; type: 'hard' | 'soft' };

const DEFAULT_CRITERIA: Criterion[] = [
  { key: 'business_objective', default: 'clear outcome', override: 'qualified leads or revenue', type: 'hard' },
  { key: 'success_measure', default: 'observable metric', override: 'cost per qualified lead / booked job / ROAS', type: 'hard' },
  { key: 'brand_fit', default: 'approved brand memory', override: 'follow approved Brand Guidelines', type: 'soft' },
];

export function AdminCampaigns() {
  const [name, setName] = useState('');
  const [objective, setObjective] = useState('');
  const [scope, setScope] = useState('');
  const [offer, setOffer] = useState('');
  const [budget, setBudget] = useState('');
  const [timeline, setTimeline] = useState('');
  const [constraints, setConstraints] = useState('');
  const [criteria, setCriteria] = useState<Criterion[]>(DEFAULT_CRITERIA);
  const [saved, setSaved] = useState(false);

  function updateOverride(idx: number, val: string) {
    setCriteria(prev => prev.map((c, i) => i === idx ? { ...c, override: val } : c));
  }

  function addCriterion() {
    setCriteria(prev => [...prev, { key: '', default: '', override: '', type: 'soft' }]);
  }

  function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">Campaign Plans</div>
          <div className="admin-page-subtitle">Define the business intent for marketing.plan. The CMO recommends specialists and channel mix later.</div>
        </div>
      </div>

      {saved && (
        <div className="alert alert-success" style={{ marginBottom: 20 }}>
          Plan intent prepared. Campaign persistence is pending; use this shape as the marketing.plan contract.
        </div>
      )}

      <form onSubmit={handleCreate}>
        <div className="admin-card">
          <div className="admin-card-title">Business Intent</div>

          <div className="form-group">
            <label className="label">Plan Name</label>
            <input className="input" placeholder="May qualified-lead push" value={name} onChange={e => setName(e.target.value)} />
          </div>

          <div className="form-group">
            <label className="label">Objective</label>
            <textarea className="input" placeholder="What business outcome should marketing create?" value={objective} onChange={e => setObjective(e.target.value)} style={{ minHeight: 80, resize: 'vertical' }} />
          </div>

          <div className="admin-two-col">
            <div className="form-group">
              <label className="label">Scope</label>
              <input className="input" placeholder="Brand, client, location, market, agent, SKU group…" value={scope} onChange={e => setScope(e.target.value)} />
              <div className="hint">Optional market-unit scope. Leave broad if this applies to the whole brand.</div>
            </div>
            <div className="form-group">
              <label className="label">Offer / Product</label>
              <input className="input" placeholder="Offer, service line, product line, or campaign theme" value={offer} onChange={e => setOffer(e.target.value)} />
            </div>
          </div>

          <div className="admin-two-col">
            <div className="form-group">
              <label className="label">Budget Guardrail</label>
              <input className="input" placeholder="e.g. $2,500/month, no spend changes without approval" value={budget} onChange={e => setBudget(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="label">Timeline</label>
              <input className="input" placeholder="e.g. next 30 days, Q3, before launch date" value={timeline} onChange={e => setTimeline(e.target.value)} />
            </div>
          </div>

          <div className="form-group">
            <label className="label">Constraints</label>
            <textarea className="input" placeholder="Compliance, excluded audiences, required claims, locations to avoid, approval rules…" value={constraints} onChange={e => setConstraints(e.target.value)} style={{ minHeight: 70, resize: 'vertical' }} />
          </div>
        </div>

        <div className="admin-card">
          <div className="admin-card-title">Success Criteria</div>
          <div className="form-group">
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Criterion</th>
                    <th>Default</th>
                    <th>Override</th>
                    <th>Type</th>
                  </tr>
                </thead>
                <tbody>
                  {criteria.map((c, i) => (
                    <tr key={i}>
                      <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{c.key || <em style={{ color: 'var(--text2)' }}>new</em>}</td>
                      <td style={{ color: 'var(--text2)', fontSize: 13 }}>{c.default}</td>
                      <td>
                        <input className="input" style={{ minWidth: 220, padding: '4px 8px', fontSize: 13 }} value={c.override} onChange={e => updateOverride(i, e.target.value)} />
                      </td>
                      <td><span className={`badge badge-${c.type === 'hard' ? 'error' : 'warning'}`}>{c.type}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <button type="button" className="btn btn-secondary btn-sm" style={{ marginTop: 10 }} onClick={addCriterion}>+ Add Criterion</button>
          </div>

          <div style={{ display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap' }}>
            <button type="submit" className="btn btn-dark" disabled={!name.trim() || !objective.trim()}>Prepare Plan Intent</button>
            <button type="button" className="btn btn-secondary">Preview Intent Contract</button>
          </div>
        </div>
      </form>
    </div>
  );
}
