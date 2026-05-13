import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import type { ModuleInfo } from '../api/types';

const BRIEF_FIELDS: Array<{ key: string; label: string; placeholder: string }> = [
  { key: 'product_name', label: 'Product Name',    placeholder: 'Auto-resolved from workspace' },
  { key: 'audience',     label: 'Target Audience', placeholder: 'Auto-resolved from workspace' },
  { key: 'tone',         label: 'Tone',            placeholder: 'Auto-resolved from brand' },
  { key: 'tagline',      label: 'Tagline',         placeholder: 'Optional override' },
  { key: 'key_benefit',  label: 'Key Benefit',     placeholder: 'e.g. saves 10 hours per week' },
];

export function RunModule() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [selectedModule, setSelectedModule] = useState(searchParams.get('module') ?? '');
  const [policy, setPolicy] = useState<'cheap' | 'balanced' | 'premium'>('balanced');
  const [brief, setBrief] = useState<Record<string, string>>({
    product_name: '', audience: '', tone: '', tagline: '', key_benefit: '',
  });
  const [loading, setLoading] = useState(false);
  const [loadingModules, setLoadingModules] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getVerticals().then(async ({ verticals }) => {
      const all = await Promise.all(verticals.map(v => api.getModules(v.vertical).then(r => r.modules)));
      setModules(all.flat());
      setLoadingModules(false);
    }).catch(() => setLoadingModules(false));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedModule) return;
    setLoading(true);
    setError(null);
    try {
      const filteredBrief: Record<string, string> = {};
      Object.entries(brief).forEach(([k, v]) => { if (v.trim()) filteredBrief[k] = v.trim(); });
      const run = await api.postRun({ module_id: selectedModule, policy, payload: { brief: filteredBrief } });
      navigate(`/settings/history/${run.run_id}`);
    } catch (e: unknown) {
      setError((e as Error).message ?? 'Run failed');
      setLoading(false);
    }
  }

  const moduleInfo = modules.find(m => m.id === selectedModule);

  return (
    <div>
      <div className="subpage-header">
        <button className="subpage-back" onClick={() => navigate('/settings')}>‹ Settings</button>
        <span className="subpage-title">Run Module</span>
      </div>

      <div className="subpage-body ux-page">
        <div className="ux-hero">
          <div>
            <div className="ux-eyebrow">Manual Transform</div>
            <h1 className="ux-title">Run a specialist module</h1>
            <p className="ux-subtitle">Use this for testing a Transform node directly. In normal operation, the CMO creates the Bridge contract and dispatches modules for you.</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="ux-form-stack">
          <div className="card ux-lift-card">
            <div className="card-title">Module &amp; Policy</div>
            <div className="form-group">
              <label className="label">Module</label>
              <select
                className="select"
                value={selectedModule}
                onChange={e => setSelectedModule(e.target.value)}
                disabled={loadingModules}
              >
                <option value="">{loadingModules ? 'Loading…' : 'Choose a module…'}</option>
                {modules.map(m => <option key={m.id} value={m.id}>{m.id}</option>)}
              </select>
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="label">Policy</label>
              <div className="flex gap-2">
                {(['cheap', 'balanced', 'premium'] as const).map(p => (
                  <button
                    key={p}
                    type="button"
                    className={`btn btn-sm ${policy === p ? 'btn-dark' : 'btn-secondary'}`}
                    onClick={() => setPolicy(p)}
                  >
                    {p.charAt(0).toUpperCase() + p.slice(1)}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {moduleInfo && (
            <div className="alert alert-info">
              <strong>{moduleInfo.id}</strong>
              {moduleInfo.constraints.max_chars > 0 && ` · max ${moduleInfo.constraints.max_chars.toLocaleString()} chars`}
              {moduleInfo.constraints.must_mention.length > 0 && ` · must mention: ${moduleInfo.constraints.must_mention.join(', ')}`}
            </div>
          )}

          <div className="card ux-lift-card">
            <div className="card-title">
              Brief Overrides
              <span className="label-hint"> — all optional, workspace fills gaps</span>
            </div>
            {BRIEF_FIELDS.map(({ key, label, placeholder }) => (
              <div className="form-group" key={key}>
                <label className="label">{label}</label>
                <input
                  className="input"
                  value={brief[key]}
                  onChange={e => setBrief(prev => ({ ...prev, [key]: e.target.value }))}
                  placeholder={placeholder}
                />
              </div>
            ))}
          </div>

          {error && <div className="alert alert-error">{error}</div>}

          <button
            type="submit"
            className="btn btn-dark btn-block"
            disabled={!selectedModule || loading}
          >
            {loading
              ? <><span className="spinner" style={{ width: 16, height: 16 }} /> Running…</>
              : '▶ Run Module'}
          </button>
        </form>
      </div>
    </div>
  );
}
