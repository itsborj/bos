import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ApprovalBundle } from '../components/blocks/ApprovalBundle';
import { artifactTitle } from '../utils/artifacts';
import type { RunResponse } from '../api/types';

export function WorkspaceArtifact() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [run, setRun] = useState<RunResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    api.getRun(runId)
      .then(setRun)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Artifact not found'))
      .finally(() => setLoading(false));
  }, [runId]);

  if (loading) return <div className="loading-full"><span className="spinner" /></div>;

  if (error || !run) {
    return (
      <div className="workspace-artifact-page">
        <button className="btn btn-sm" onClick={() => navigate('/workspace')}>← Workspace</button>
        <div className="state-message">{error || 'Artifact not found.'}</div>
      </div>
    );
  }

  return (
    <div className="workspace-artifact-page">
      <div className="workspace-artifact-header">
        <button className="btn btn-sm" onClick={() => navigate('/workspace')}>← Workspace</button>
        <div>
          <div className="artifact-eyebrow">Workspace artifact</div>
          <h2>{artifactTitle(run)}</h2>
        </div>
      </div>
      <ApprovalBundle run={run} surfaceContext="full-screen" />
    </div>
  );
}
