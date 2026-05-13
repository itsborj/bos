import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { ModuleInfo } from '../api/types';

export function Modules() {
  const navigate = useNavigate();
  const [verticals, setVerticals] = useState<Array<{ vertical: string; module_count: number }>>([]);
  const [modulesByVertical, setModulesByVertical] = useState<Record<string, ModuleInfo[]>>({});
  const [activeVertical, setActiveVertical] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getVerticals().then(async ({ verticals: verts }) => {
      setVerticals(verts);
      if (verts.length > 0) {
        setActiveVertical(verts[0].vertical);
        const results = await Promise.all(
          verts.map(v => api.getModules(v.vertical).then(r => [v.vertical, r.modules] as const))
        );
        const map: Record<string, ModuleInfo[]> = {};
        results.forEach(([v, mods]) => { map[v] = mods; });
        setModulesByVertical(map);
      }
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const activeModules = activeVertical ? modulesByVertical[activeVertical] ?? [] : [];
  const totalModules = Object.values(modulesByVertical).reduce((sum, mods) => sum + mods.length, 0);
  const capabilityCount = new Set(Object.values(modulesByVertical).flat().map(m => m.capability)).size;

  function moduleTitle(mod: ModuleInfo): string {
    const parts = mod.id.split('.');
    return parts.slice(1).map(p => p.replace(/_/g, ' ')).join(' / ');
  }

  return (
    <div>
      <div className="subpage-header">
        <button className="subpage-back" onClick={() => navigate('/settings')}>‹ Settings</button>
        <span className="subpage-title">Modules</span>
      </div>

      <div className="subpage-body ux-page">
        <div className="ux-hero">
          <div>
            <div className="ux-eyebrow">Transform registry</div>
            <h1 className="ux-title">Specialist modules</h1>
            <p className="ux-subtitle">Browse the execution arms available to the CMO. Strategy stays with the CMO; these nodes transform precise Bridge payloads.</p>
          </div>
          <div className="ux-stat-row compact">
            <div className="ux-stat"><span>{totalModules}</span><small>modules</small></div>
            <div className="ux-stat"><span>{verticals.length}</span><small>verticals</small></div>
            <div className="ux-stat"><span>{capabilityCount}</span><small>capabilities</small></div>
          </div>
        </div>

        {loading ? (
          <div className="loading-full" style={{ minHeight: 200 }}>
            <span className="spinner" />
          </div>
        ) : verticals.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">◈</div>
            <div className="empty-state-title">No modules registered</div>
            <div className="empty-state-text">Add module files to api/modules/ to see them here.</div>
          </div>
        ) : (
          <>
            <div className="tabs">
              {verticals.map(v => (
                <div
                  key={v.vertical}
                  className={`tab${activeVertical === v.vertical ? ' active' : ''}`}
                  onClick={() => setActiveVertical(v.vertical)}
                >
                  {v.vertical}
                  <span style={{ color: 'var(--text2)', fontSize: 11, marginLeft: 5 }}>({v.module_count})</span>
                </div>
              ))}
            </div>

            <div className="module-grid ux-card-grid">
              {activeModules.map(mod => (
                <div key={mod.id} className="module-card ux-lift-card">
                  <div className="module-card-id">{mod.id}</div>
                  <div className="module-card-title">{moduleTitle(mod)}</div>
                  <div className="module-meta">
                    <span className="badge badge-info">{mod.capability}</span>
                    <span className="badge badge-muted">{mod.policy_default}</span>
                    <span className="badge badge-muted">{mod.platform_hint}</span>
                  </div>
                  {mod.constraints.max_chars > 0 && (
                    <div style={{ fontSize: 12, color: 'var(--text2)' }}>
                      Max {mod.constraints.max_chars.toLocaleString()} chars
                      {mod.constraints.must_mention.length > 0 && ` · must mention: ${mod.constraints.must_mention.join(', ')}`}
                    </div>
                  )}
                  <Link
                    to={`/settings/run?module=${encodeURIComponent(mod.id)}`}
                    className="btn btn-dark btn-sm"
                    style={{ alignSelf: 'flex-start', marginTop: 4 }}
                  >
                    ▶ Run
                  </Link>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
