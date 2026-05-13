import { buildArtifactRef } from '../utils/artifacts';
import type { RunResponse } from '../api/types';

function assert(condition: boolean, message: string): void {
  if (!condition) throw new Error(message);
}

const run: RunResponse = {
  run_id: 'run_123',
  module_id: 'marketing.channel.gmail.outreach.draft',
  vertical: 'marketing',
  status: 'success',
  approval_status: 'pending',
  created_at: '2026-05-13T00:00:00Z',
  result: {
    content: 'Hi Pat, this body should not be copied into the chat artifact ref.',
    subject: 'Subject should stay in Workspace',
    preheader: 'Preheader should stay in Workspace',
    self_check: 'pass',
    platform: 'email',
  },
};

const ref = buildArtifactRef(run);

assert(ref.artifact_id === 'run_123', 'artifact id should match run id');
assert(ref.title === 'Email Draft', 'title should describe the artifact');
assert(ref.type === 'draft_artifact', 'type should be a draft artifact');
assert(ref.status === 'pending_review', 'pending runs should become pending review refs');
assert(ref.renderer === 'email_preview', 'email runs should select email preview renderer');
assert(ref.workspace_url === '/workspace/artifacts/run_123', 'workspace URL should point to artifact detail');

const serialized = JSON.stringify(ref);
assert(!serialized.includes('Hi Pat'), 'chat artifact refs must not include native artifact body');
assert(!serialized.includes('Subject should stay'), 'chat artifact refs must not include native artifact subject');

console.log('artifactPlane.test.ts passed');
