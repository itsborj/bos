import { useRef, useState } from 'react';
import { api } from '../api/client';

interface Props {
  context: string;
}

interface Insight {
  type: 'alert' | 'warn' | 'good' | 'info';
  tag: string;
  text: string;
  action?: string;
}

const SCREEN_INSIGHTS: Record<string, Insight[]> = {
  ops: [
    { type: 'info',  tag: 'In progress',     text: 'Modules running now will appear here. Last completed run and self-check result shown below.' },
    { type: 'good',  tag: 'Self-check',       text: 'All completed runs show self-check status. Pass = output met constraints.' },
    { type: 'alert', tag: 'On error',         text: 'If a module fails, the trace link shows the full BITE trace including which provider was tried.' },
  ],
  intelligence: [
    { type: 'good',  tag: 'ROI signal',       text: 'Top-performing modules by pass rate are ranked highest. More runs → more reliable signal.' },
    { type: 'warn',  tag: 'Coverage gap',     text: 'Channel performance and product ROI tables appear here once campaign data is configured.' },
    { type: 'info',  tag: 'Cost trend',       text: 'Avg cost per run is calculated from all completed runs. BYOK runs reduce platform markup.' },
  ],
  workspace: [
    { type: 'warn',  tag: 'Missing context',  text: 'Visual style guide not configured. Banner modules will use generic layouts until added.', action: 'Add style guide →' },
    { type: 'good',  tag: 'Context complete', text: 'Voice, tone, values, and audience segments are auto-resolved on every module run.' },
    { type: 'info',  tag: 'Tip',              text: 'Adding a positioning statement per product helps modules differentiate copy more sharply.' },
  ],
  history: [
    { type: 'info',  tag: 'Filters',          text: 'Filter by status to isolate failures. Click trace ↗ on any row to inspect the full BITE trace.' },
    { type: 'good',  tag: 'Self-check',       text: 'Pass = output met all constraints (char limit, must-mention, banned phrases). Fail = retry candidate.' },
    { type: 'alert', tag: 'On failure',       text: 'Failed runs incur no provider cost. The executor tried all candidates before falling back to mock.' },
  ],
  settings: [
    { type: 'warn',  tag: 'Provider health',  text: 'Degraded providers are deprioritised in routing. Check latency by running POST /providers/check.' },
    { type: 'good',  tag: 'BYOK',             text: 'BYOK keys bypass platform markup. Runs on your own key show provider_cost only, no sell_price.' },
    { type: 'info',  tag: 'Billing mode',     text: 'Platform mode is active for any provider where you have no BYOK key registered.' },
  ],
};

const DEFAULT_INSIGHTS: Insight[] = [
  { type: 'info',  tag: 'Ready',       text: 'Ask CMO anything about your campaigns, modules, or workspace.' },
  { type: 'good',  tag: 'All systems', text: 'No active errors detected.' },
];

export function CmoRail({ context }: Props) {
  const [input, setInput] = useState('');
  const [busy, setBusy]   = useState(false);
  const [reply, setReply] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const screenKey = context.toLowerCase();
  const insights = SCREEN_INSIGHTS[screenKey] ?? DEFAULT_INSIGHTS;

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setBusy(true);
    setInput('');
    setReply(null);
    try {
      const resp = await api.chat(text, [], null, null);
      const content = resp.reply || (resp.runs?.length ? 'I created an artifact for review in the CMO workspace.' : '(no reply)');
      setReply(content.slice(0, 300) + (content.length > 300 ? '…' : ''));
    } catch (e: unknown) {
      setReply(e instanceof Error ? e.message : 'Something went wrong.');
    } finally {
      setBusy(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  }

  return (
    <aside className="cmo-rail">
      <div className="cmo-rail-header">
        <div className="cmo-rail-dot" />
        <span className="cmo-rail-title">CMO AI</span>
        <span className="cmo-rail-context">{context} view</span>
      </div>

      <div className="cmo-rail-feed">
        {reply && (
          <div className="ci info">
            <div className="ci-tag">Reply</div>
            <div className="ci-text">{reply}</div>
          </div>
        )}
        {busy && (
          <div className="ci info">
            <div className="ci-tag">Thinking…</div>
            <div className="ci-text" style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
              <div className="cmo-typing-dot" />
              <div className="cmo-typing-dot" />
              <div className="cmo-typing-dot" />
            </div>
          </div>
        )}
        {!reply && !busy && insights.map((ins, i) => (
          <div key={i} className={`ci ${ins.type}`}>
            <div className="ci-tag">{ins.tag}</div>
            <div className="ci-text">{ins.text}</div>
            {ins.action && <span className="ci-action">{ins.action}</span>}
          </div>
        ))}
      </div>

      <div className="cmo-rail-input-wrap">
        <textarea
          ref={inputRef}
          className="cmo-rail-input"
          rows={2}
          placeholder="Ask CMO anything…"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={busy}
        />
      </div>
    </aside>
  );
}
