import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import type { OnboardingStatus, ProviderInfo, RunListResponse, WorkspaceResponse } from '../../api/types';

type Step = {
  label: string;
  done: boolean;
  hint: string;
};

export function AdminGettingStarted() {
  const navigate = useNavigate();
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null);
  const [runs, setRuns] = useState<RunListResponse | null>(null);
  const [onboarding, setOnboarding] = useState<OnboardingStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getProviders().catch(() => ({ providers: [] as ProviderInfo[] })),
      api.getWorkspace().catch(() => null),
      api.getRuns({ limit: 1 }).catch(() => ({ runs: [], total: 0, limit: 1, offset: 0 })),
      api.getOnboardingStatus().catch(() => null),
    ]).then(([provResult, ws, runResult, onboardingResult]) => {
      setProviders(provResult.providers ?? []);
      setWorkspace(ws);
      setRuns(runResult);
      setOnboarding(onboardingResult);
      setLoading(false);
    });
  }, []);

  const openai = providers.find((p) => p.provider === 'openai') ?? null;
  const brandImported = Boolean(
    workspace?.brand?.voice ||
    workspace?.brand?.tone ||
    workspace?.brand?.values?.length ||
    workspace?.products?.length ||
    workspace?.audiences?.length,
  );
  const brandKitApproved = onboarding?.campaign_brand_kit_approved === true;
  const firstRunDone = (runs?.total ?? 0) > 0;

  const steps = useMemo<Step[]>(() => [
    {
      label: 'Connect OpenAI Chat',
      done: openai?.connected === true,
      hint: openai?.connected ? 'OpenAI login is connected.' : 'Use login auth or an API key to activate BOS.',
    },
    {
      label: 'Import brand brief',
      done: brandImported,
      hint: brandImported ? 'Brand context has been extracted into the workspace.' : 'Paste a brief or company description to build the workspace profile.',
    },
    {
      label: 'Review workspace profile',
      done: brandImported && Boolean(workspace?.name),
      hint: workspace?.name ? `Workspace: ${workspace.name}` : 'Review brand memory before asking the CMO to plan, execute, or optimize.'
    },
    {
      label: 'Approve Campaign Brand Kit',
      done: brandKitApproved,
      hint: brandKitApproved ? 'Campaign Brand Kit is approved.' : 'Required for cohesive multi-platform campaigns before first launch.',
    },
    {
      label: 'Create first CMO artifact',
      done: firstRunDone,
      hint: firstRunDone ? `${runs?.total ?? 0} specialist execution${(runs?.total ?? 0) !== 1 ? 's' : ''} recorded.` : 'Ask the CMO to plan, execute, or optimize once setup is ready.',
    },
  ], [openai?.connected, brandImported, workspace?.name, brandKitApproved, firstRunDone, runs?.total]);

  const nextStep = !steps[0].done
    ? { label: 'Connect provider', action: () => navigate('/admin/providers') }
    : !steps[1].done
      ? { label: 'Import brand brief', action: () => navigate('/admin/onboarding') }
      : !steps[3].done
        ? { label: 'Generate Brand Kit', action: () => navigate('/admin/onboarding') }
        : !steps[4].done
          ? { label: 'Go to CMO', action: () => navigate('/cmo') }
          : { label: 'View workspace', action: () => navigate('/admin/workspace') };

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
          <div className="admin-page-title">Getting Started</div>
          <div className="admin-page-subtitle">Teach BOS the business, approve memory, connect specialists, then operate from the CMO</div>
        </div>
      </div>

      <div className="admin-card" style={{ marginBottom: 16 }}>
        <div className="admin-card-title">Business memory status</div>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 28, fontWeight: 800, marginBottom: 6 }}>
              {steps.every((step) => step.done) ? 'Ready to operate' : 'Needs setup'}
            </div>
            <div style={{ fontSize: 13, color: 'var(--text2)' }}>
              {steps.filter((step) => step.done).length} of {steps.length} setup steps complete
            </div>
          </div>
          <div style={{ minWidth: 240 }}>
            <div className="label" style={{ marginBottom: 6 }}>Next required step</div>
            <button className="btn btn-dark" onClick={nextStep.action}>{nextStep.label} →</button>
          </div>
        </div>
      </div>

      <div className="admin-two-col">
        <div className="admin-card">
          <div className="admin-card-title">Setup checklist</div>
          <div style={{ display: 'grid', gap: 12 }}>
            {steps.map((step) => (
              <div key={step.label} style={{ display: 'flex', gap: 12, alignItems: 'flex-start', paddingBottom: 12, borderBottom: '1px solid var(--border)' }}>
                <span className={`badge badge-${step.done ? 'success' : 'warning'}`} style={{ minWidth: 34, textAlign: 'center' }}>
                  {step.done ? '✓' : '•'}
                </span>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 14 }}>{step.label}</div>
                  <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 3 }}>{step.hint}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="admin-card">
          <div className="admin-card-title">Quick actions</div>
          <div style={{ display: 'grid', gap: 10 }}>
            <button className="btn btn-dark" onClick={() => navigate('/cmo')}>Go to CMO</button>
            <button className="btn btn-secondary" onClick={() => navigate('/admin/onboarding')}>Import Brand Brief</button>
            <button className="btn btn-secondary" onClick={() => navigate('/admin/workspace')}>Review Brand Memory</button>
            <button className="btn btn-secondary" onClick={() => navigate('/admin/providers')}>Manage AI Providers</button>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 14 }}>
            OpenAI Chat is the primary login-auth provider for this deployment. Other providers remain available through API keys.
          </div>
        </div>
      </div>

      <div className="admin-card" style={{ marginTop: 16 }}>
        <div className="admin-card-title">Recent activity</div>
        <div style={{ fontSize: 13, color: 'var(--text2)' }}>
          {firstRunDone ? (
            <>
              {runs?.total ?? 0} specialist execution{(runs?.total ?? 0) !== 1 ? 's' : ''} recorded. <Link to="/admin/runs">View run logs →</Link>
            </>
          ) : (
            <>
              No specialist executions yet. After setup, use the CMO to create the first plan, draft, or optimization artifact.
            </>
          )}
        </div>
      </div>
    </div>
  );
}
