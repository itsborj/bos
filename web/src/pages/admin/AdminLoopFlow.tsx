type FlowStep = {
  role: 'operator' | 'system';
  title: string;
  sub: string;
  tags: string[];
  io: [string, string][];
  last?: boolean;
};

const STEPS: FlowStep[] = [
  {
    role: 'system',
    title: 'Stream: decision_brief appears',
    sub: 'BOS reads Gmail, matches April memory, ranks card as highest urgency. Confidence: directional (0.71). Card surfaces with evidence, recommended action, and approval boundary.',
    tags: ['system', 'state: pending operator review'],
    io: [['inputs', 'Gmail replies · April memory · 47 contacts identified'], ['output', 'decision_brief card ranked #1 in Stream']],
  },
  {
    role: 'operator',
    title: 'Operator taps "Ask CMO"',
    sub: 'From the decision_brief card. CMO opens with context pre-loaded: brand, objective, card type. Not a blank chatbot — the brief is already there.',
    tags: ['operator', 'state: CMO surface open'],
    io: [['context loaded', 'Klaroha · $40k pipeline · decision_brief'], ['CMO opens with', 'judgment summary, not blank prompt']],
  },
  {
    role: 'operator',
    title: 'Operator reviews brief, taps "Approve"',
    sub: 'Operator reviews the pending_artifact (sequence v2). Decision: approve. BOS receives the approval signal — this is the only gate before execution.',
    tags: ['operator', 'state: artifact approved'],
    io: [['artifact', 'sequence v2 · status: approved'], ['boundary', 'BOS cannot send without this step']],
  },
  {
    role: 'system',
    title: 'BOS queues Gmail send',
    sub: 'Card moves from pending to queued. BOS schedules delivery for the Thursday window. No further operator action needed until replies arrive.',
    tags: ['system', 'state: queued for send'],
    io: [['action', '47 emails queued · Thursday window · Gmail connector'], ['operator required', 'none until replies arrive']],
  },
  {
    role: 'system',
    title: 'Gmail sends · replies come in',
    sub: 'BOS monitors the Gmail thread. Replies are read, reply rate is tracked, patterns are noted. Memory writing is deferred until operator confirms outcome.',
    tags: ['system', 'state: observing'],
    io: [['monitoring', 'Gmail replies · reply timing patterns'], ['memory writing', 'deferred until operator confirms']],
  },
  {
    role: 'operator',
    title: 'Operator records outcome in CMO or Stream',
    sub: 'After calls conclude, the operator records what happened. BOS uses this to write memory — outcome records are the basis for every future recommendation.',
    tags: ['operator', 'state: outcome recording'],
    io: [['operator inputs', 'calls booked · deal status · notes'], ['BOS writes', 'outcome record to memory']],
  },
  {
    role: 'system',
    title: 'Stream: outcome card appears · memory updated',
    sub: 'Campaign closes. Outcome card shows results and lists what was written to memory. Operator can delete it or ask CMO for interpretation.',
    tags: ['system', 'state: memory written'],
    io: [['written', 'case_study_angle · email_2_response · no_show_pattern'], ['card type', 'outcome · deletable']],
  },
  {
    role: 'system',
    title: 'Next decision_brief is better',
    sub: 'The next recommendation references both April and May data. Confidence increases. Sequence v3 can be proposed with stronger evidence. The loop compounds.',
    tags: ['system', 'state: loop complete · memory compounds'],
    io: [['evidence base', 'April + May outcome records'], ['confidence', 'directional → known as data accumulates'], ['loop', 'observe → interpret → remember → recommend → execute']],
    last: true,
  },
];

function tagClass(t: string) {
  if (t === 'operator') return 'flow-tag-op';
  if (t.startsWith('state')) return 'flow-tag-state';
  return 'flow-tag-sys';
}

export function AdminLoopFlow() {
  return (
    <div>
      <div className="admin-section-title">Stream Flow</div>
      <div className="admin-section-sub">{STEPS.length} steps from first signal to compounding memory. Use this to trace how a decision moved through the system.</div>

      <div className="flow-legend">
        <div className="legend-item">
          <div className="legend-dot" style={{ background: 'var(--active-green)' }}>O</div>
          Operator action
        </div>
        <div className="legend-item">
          <div className="legend-dot" style={{ background: 'var(--muted-stone)' }}>S</div>
          System action
        </div>
      </div>

      {STEPS.map((step, i) => (
        <div className="flow-node" key={i}>
          <div className="flow-spine">
            <div className={`flow-dot ${step.role}`}>{step.role === 'operator' ? 'O' : 'S'}</div>
            {!step.last && <div className="flow-line" />}
          </div>
          <div className="flow-body">
            <div className="flow-node-title">{step.title}</div>
            <div className="flow-node-sub">{step.sub}</div>
            <div className="flow-tags">
              {step.tags.map(t => (
                <span key={t} className={`flow-tag ${tagClass(t)}`}>{t}</span>
              ))}
            </div>
            <div className="flow-io">
              {step.io.map(([k, v], j) => (
                <span key={j}>
                  {j > 0 && <br />}
                  <span className="flow-io-key">{k}: </span>
                  <span className="flow-io-val">{v}</span>
                </span>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
