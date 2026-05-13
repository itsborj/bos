import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import type { ModuleInfo } from '../../api/types';

type SpecialistSummary = {
  key: string;
  name: string;
  description: string;
  jobs: string[];
  specialties: string[];
  readiness: 'ready' | 'needs_setup' | 'installed';
  readinessText: string;
  risk: string;
  moduleCount: number;
  nextStep?: string;
};

type SocialConnection = {
  id: string;
  brand_id: string | null;
  platform: string;
  page_name: string | null;
  page_handle: string | null;
  status: string;
};

function titleCase(value: string): string {
  return value
    .replace(/[_.-]/g, ' ')
    .split(' ')
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function implementedJobs(mod: ModuleInfo): string[] {
  const value = `${mod.id} ${mod.capability}`.toLowerCase();
  const jobs = new Set<string>();
  if (/plan|strategy|launch|campaign/.test(value)) jobs.add('marketing.plan');
  if (/copy|draft|send|email|creative|outreach|execute/.test(value)) jobs.add('marketing.execute');
  if (/analytics|tracking|seo|report|receive|inbox|optimi[sz]e|audit/.test(value)) jobs.add('marketing.optimize');
  if (!jobs.size && mod.vertical === 'marketing') jobs.add('marketing.execute');
  return [...jobs];
}

function groupKey(mod: ModuleInfo): string {
  const id = mod.id.toLowerCase();
  if (id.includes('gmail')) return 'email';
  if (id.includes('google_ads')) return 'paid-search';
  if (id.includes('search_console') || id.includes('seo')) return 'seo';
  if (id.includes('analytics') || id.includes('tracking')) return 'analytics';
  return mod.vertical || 'specialist';
}

function summarizeGroup(key: string, modules: ModuleInfo[], connections: SocialConnection[]): SpecialistSummary {
  const jobs = [...new Set(modules.flatMap(implementedJobs))];
  const moduleText = modules.map(m => `${m.id} ${m.platform_hint}`.toLowerCase()).join(' ');
  const gmailConnections = connections.filter(conn => conn.platform === 'gmail' && conn.status !== 'revoked');

  if (key === 'email') {
    const cmoJobs = ['marketing.plan', 'marketing.execute', 'marketing.optimize'];
    const connected = gmailConnections.length > 0;
    return {
      key,
      name: 'Email Specialist',
      description: 'Plans email campaigns, drafts outreach, reads reply context, and prepares approved Gmail send actions.',
      jobs: cmoJobs,
      specialties: ['campaign planning', 'drafting', 'inbox intelligence', 'optimization'],
      readiness: connected ? 'ready' : 'needs_setup',
      readinessText: connected
        ? `${gmailConnections.length} Gmail account${gmailConnections.length !== 1 ? 's' : ''} connected`
        : 'Connect Gmail from Brands / Clients to unlock inbox and send actions',
      risk: moduleText.includes('send') ? 'Draft by default; real sends require explicit owner approval' : 'Draft / review',
      moduleCount: modules.length,
      nextStep: connected ? 'Use the CMO to plan, draft, approve, then send.' : 'Connect Gmail, verify sender identity, then create a test draft.',
    };
  }

  if (key === 'paid-search') {
    return {
      key,
      name: 'Paid Search Specialist',
      description: 'Reviews paid-search performance and prepares optimization or ad-draft artifacts.',
      jobs,
      specialties: ['paid search', 'budget efficiency', 'ad drafts'],
      readiness: 'needs_setup',
      readinessText: 'Needs connector setup',
      risk: 'Read and draft first; spend changes require approval',
      moduleCount: modules.length,
    };
  }

  if (key === 'seo') {
    return {
      key,
      name: 'SEO Specialist',
      description: 'Audits search visibility, content opportunities, and organic growth constraints.',
      jobs,
      specialties: ['SEO', 'content opportunities', 'technical review'],
      readiness: 'installed',
      readinessText: 'Installed',
      risk: 'Diagnostic / recommendation',
      moduleCount: modules.length,
    };
  }

  if (key === 'analytics') {
    return {
      key,
      name: 'Analytics Specialist',
      description: 'Diagnoses measurement, tracking, and performance signals for optimization work.',
      jobs,
      specialties: ['tracking', 'measurement', 'performance signals'],
      readiness: 'installed',
      readinessText: 'Installed',
      risk: 'Read-only / diagnostic',
      moduleCount: modules.length,
    };
  }

  return {
    key,
    name: `${titleCase(key)} Specialist`,
    description: 'Installed specialist implementation available to the CMO when its skill contract applies.',
    jobs,
    specialties: [...new Set(modules.map(m => m.platform_hint).filter(Boolean))],
    readiness: 'installed',
    readinessText: 'Installed',
    risk: 'Draft / review',
    moduleCount: modules.length,
  };
}

export function AdminModules() {
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [connections, setConnections] = useState<SocialConnection[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [{ verticals }, socialConnections] = await Promise.all([
        api.getVerticals(),
        api.listSocialConnections().catch(() => [] as SocialConnection[]),
      ]);
      const results = await Promise.all(
        verticals.map(v => api.getModules(v.vertical).then(r => r.modules).catch(() => [] as ModuleInfo[]))
      );
      setModules(results.flat());
      setConnections(socialConnections as SocialConnection[]);
    }
    load().catch(() => {}).finally(() => setLoading(false));
  }, []);

  const specialists = useMemo(() => {
    const visible = modules.filter(mod => !mod.id.toLowerCase().includes('test_stub'));
    const grouped = new Map<string, ModuleInfo[]>();
    visible.forEach(mod => {
      const key = groupKey(mod);
      grouped.set(key, [...(grouped.get(key) ?? []), mod]);
    });
    return [...grouped.entries()].map(([key, mods]) => summarizeGroup(key, mods, connections));
  }, [modules, connections]);

  if (loading) {
    return <div className="admin-page"><div className="loading-full"><span className="spinner" /></div></div>;
  }

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">Specialists</div>
          <div className="admin-page-subtitle">
            Installed marketing specialists available to the CMO. Internal module IDs, backend routing, and test harnesses are hidden from normal admin workflow.
          </div>
        </div>
      </div>

      {specialists.length === 0 ? (
        <div className="admin-card"><div className="empty-state"><div className="empty-state-icon">◎</div><div className="empty-state-title">No specialists installed</div><div className="empty-state-text">Install capability or plugin packages to see specialists here.</div></div></div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 14 }}>
          {specialists.map(s => (
            <div key={s.key} className="admin-card" style={{ margin: 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', marginBottom: 10 }}>
                <div>
                  <div style={{ fontWeight: 850, fontSize: 16 }}>{s.name}</div>
                  <div style={{ color: 'var(--text2)', fontSize: 12, marginTop: 3 }}>{s.description}</div>
                </div>
                <span className={`badge badge-${s.readiness === 'needs_setup' ? 'warning' : 'success'}`}>{s.readiness === 'needs_setup' ? 'Needs setup' : s.readiness === 'ready' ? 'Ready' : 'Available'}</span>
              </div>

              <div style={{ display: 'grid', gap: 10, marginTop: 14 }}>
                <div>
                  <div className="label" style={{ marginBottom: 5 }}>CMO jobs</div>
                  <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                    {s.jobs.map(job => <span key={job} className="badge badge-info">{job}</span>)}
                  </div>
                </div>
                <div>
                  <div className="label" style={{ marginBottom: 5 }}>Specialty</div>
                  <div style={{ color: 'var(--text2)', fontSize: 13 }}>{s.specialties.join(' · ') || 'General marketing'}</div>
                </div>
                <div>
                  <div className="label" style={{ marginBottom: 5 }}>Risk policy</div>
                  <div style={{ color: 'var(--text2)', fontSize: 13 }}>{s.risk}</div>
                </div>
                <div style={{ paddingTop: 10, borderTop: '1px solid var(--border)', display: 'grid', gap: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
                    <span style={{ color: 'var(--text2)', fontSize: 12 }}>{s.readinessText}</span>
                    <span className="badge badge-muted">{s.moduleCount} tool{s.moduleCount !== 1 ? 's' : ''}</span>
                  </div>
                  {s.nextStep && <div style={{ color: 'var(--text2)', fontSize: 12 }}>{s.nextStep}</div>}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
