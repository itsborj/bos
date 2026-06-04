import { useMemo, useState } from 'react';

type ComponentKey =
  | 'market'
  | 'buyer'
  | 'economics'
  | 'thesis'
  | 'storybrand'
  | 'offer'
  | 'funnel'
  | 'matrix'
  | 'measurement'
  | 'workorders';

type WorkflowComponent = {
  key: ComponentKey;
  label: string;
  role: string;
  status: 'ready' | 'draft' | 'needs-input' | 'not-wired';
  body: string[];
  outputs: string[];
};

const components: WorkflowComponent[] = [
  {
    key: 'market',
    label: 'Market context',
    role: 'Ground the strategy in facts before the brand story starts.',
    status: 'not-wired',
    body: [
      'Request context: generate pipeline from dormant prospects through Gmail for Klaroha.',
      'Known market fact: Klaroha sells clarity for fragmented marketing and sales operations; the pain is not just content output, but lost signals, slow approvals, and unclear performance.',
      'Prototype note: this component is thin for Klaroha because we did not load a full market deck. Golden Gate and Teko show this module can be much richer when local market or channel economics data exists.',
    ],
    outputs: ['Market facts used', 'Evidence gaps', 'What facts would materially change the strategy'],
  },
  {
    key: 'buyer',
    label: 'Buyer map',
    role: 'Mandatory substrate. This is the part we keep from the current chain.',
    status: 'ready',
    body: [
      'Buyer: dormant prospects who previously showed interest in Klaroha or in solving fragmented marketing/sales operations, but never converted into an active conversation.',
      'Awareness: problem-aware → solution-aware. They know the symptoms: scattered execution, unclear performance, approval delays, missed follow-up, manual reporting, and too many marketing moving parts.',
      'Buyer type: early majority. They need reassurance, proof of practical implementation, and a low-risk first step.',
      'Blocking forces: anxiety, habit, and low perceived likelihood.',
      'Trust gap: Klaroha must prove operational clarity, not content generation.',
    ],
    outputs: ['Awareness level', 'Buyer type', 'Blocking forces', 'Trust gap', 'Buyer language'],
  },
  {
    key: 'economics',
    label: 'Channel economics',
    role: 'Find the growth trade: what to harvest, what to manufacture, what to avoid.',
    status: 'not-wired',
    body: [
      'Teko shows why this component matters: branded search CPA was dramatically cheaper than generic service search, so the strategy was to manufacture more branded demand rather than blindly scale paid search.',
      'For Klaroha dormant prospects, Gmail is not a cheap-acquisition claim. It is a reactivation surface for known demand.',
      'Needed for a stronger draft: list size, source, consent basis, prior response rate, current booking/demo conversion, and cost of alternative acquisition paths.',
    ],
    outputs: ['Cheap path', 'Expensive path', 'Blended metric trap', 'Demand to manufacture', 'Scaling risk'],
  },
  {
    key: 'thesis',
    label: 'Strategic thesis',
    role: 'The management-alignment layer: what are we choosing and why?',
    status: 'ready',
    body: [
      'GTM archetype: dormant-demand reactivation + diagnostic wedge.',
      'Strategic decision: run a dormant-demand reactivation motion built around a one-leakage-point diagnostic.',
      'Gmail is the first activation surface because the prospects are known and dormant. The strategy is broader than email: convert prior interest into diagnostic conversations, identify the most acute leakage pain, then choose the next channel and proof assets from real response data.',
      'Wedge: “Before adding more marketing activity, find where your current marketing-to-pipeline loop is leaking.”',
    ],
    outputs: ['GTM archetype', 'Strategic decision', 'Wedge', 'What we are not doing'],
  },
  {
    key: 'storybrand',
    label: 'StoryBrand lens',
    role: 'A message lens, not the whole workflow.',
    status: 'not-wired',
    body: [
      'Character: overloaded business operator trying to create pipeline clarity without chasing every tool, specialist, approval, and report.',
      'Problem: external — fragmented marketing-to-pipeline flow; emotional — anxiety that another system will add complexity; philosophical — the business leader should command the system, not be trapped inside the noise.',
      'Guide: Klaroha helps map the operating loop and identify where demand is being lost or slowed.',
      'Plan: map one leakage point → recommend the next operating-loop improvement → turn approved actions into memory.',
      'CTA: “Want me to map one leakage point in your current marketing-to-pipeline flow?”',
      'Success: “I know what is leaking, what needs action, and what should improve next.”',
    ],
    outputs: ['Character', 'Problem', 'Guide', 'Plan', 'CTA', 'Success/failure stakes'],
  },
  {
    key: 'offer',
    label: 'Offer / resource architecture',
    role: 'Specific audience need → specific resource → micro commitment → activation.',
    status: 'ready',
    body: [
      'Audience need: reduce uncertainty without committing to a full platform rollout.',
      'Resource: one-leakage-point diagnostic explainer.',
      'Micro commitment: reply with the least-clear part of the current marketing flow: follow-up, approvals, reporting, or execution.',
      'Macro activation: diagnostic conversation or short guided walkthrough.',
      'Why it fits the buyer map: it lowers anxiety, avoids attacking current habits, and improves perceived likelihood through a concrete first step.',
    ],
    outputs: ['Lead magnet/resource', 'Micro goal', 'Macro goal', 'Offer risk', 'Required proof'],
  },
  {
    key: 'funnel',
    label: 'Tactical funnel',
    role: 'Flexible execution layer after strategic approval.',
    status: 'ready',
    body: [
      'Reach: dormant-prospect Gmail activation to known prior-interest contacts.',
      'Engage: diagnostic explainer + short sequence that reopens the operational pain.',
      'Action: reply with pain category or book/request a diagnostic.',
      'Patronage/learning: categorize replies, capture objections, create proof assets, choose next channel from real data.',
      'This follows the REAP pattern from the source decks: Reach, Engagement, Action, Patronage.',
    ],
    outputs: ['Reach tactic', 'Engagement resource', 'Action step', 'Patronage/learning loop'],
  },
  {
    key: 'matrix',
    label: 'Channel/content matrix',
    role: 'One concept repurposed across channels and formats.',
    status: 'not-wired',
    body: [
      'Core concept: “Find the leakage point before adding more marketing activity.”',
      'Gmail: dormant-prospect reactivation sequence.',
      'Landing page: diagnostic explainer.',
      'LinkedIn/social: short posts showing common leakage points: follow-up, approvals, reporting, execution.',
      'Sales enablement: objection sheet explaining why Klaroha is not a CRM replacement or generic AI tool.',
    ],
    outputs: ['Core concept', 'Channel variants', 'Repurpose plan', 'Assets needed'],
  },
  {
    key: 'measurement',
    label: 'Measurement model',
    role: 'Define what learning matters before optimization starts.',
    status: 'not-wired',
    body: [
      'Reach: delivered emails / reachable dormant contacts.',
      'Engagement: opens/clicks/replies where compliant tracking exists; qualitative reply themes matter more than vanity metrics.',
      'Action: diagnostic requests, booked calls, or qualified replies.',
      'Patronage/learning: dominant pain category, objection frequency, preferred next step, proof asset required for expansion.',
      'No numeric targets are invented in this prototype because baseline data was not loaded.',
    ],
    outputs: ['Reach metric', 'Engagement metric', 'Action metric', 'Learning metric', 'No-fake-target guard'],
  },
  {
    key: 'workorders',
    label: 'Work orders',
    role: 'Specialist-ready briefs produced after the Strategy Draft.',
    status: 'ready',
    body: [
      '1. Diagnostic one-page explainer — explain the one-leakage-point diagnostic before booking or replying.',
      '2. Dormant-prospect Gmail sequence — reactivate prior interest into diagnostic replies or bookings.',
      '3. Reply triage playbook — prevent replies from becoming unmanaged inbox clutter.',
      '4. Objection response sheet — answer CRM, agency, complexity, AI-tool, and manual-process objections.',
      '5. Post-test learning brief — summarize pain language, objections, preferred CTA, and next proof asset.',
    ],
    outputs: ['Execution briefs', 'Next artifact queue', 'Approval boundaries'],
  },
];

const lenses = [
  { name: 'StoryBrand', use: 'Clarifies character, problem, guide, plan, CTA, stakes.' },
  { name: 'Jobs-to-be-Done', use: 'Sharpens the progress the buyer is trying to make.' },
  { name: 'Forces of Progress', use: 'Maps push, pull, anxiety, and habit.' },
  { name: 'Value Equation', use: 'Finds offer weakness: dream outcome, likelihood, time, effort.' },
  { name: 'Category Design', use: 'Defines villain, new category, and strategic contrast.' },
  { name: 'REAP', use: 'Normalizes measurement: Reach, Engagement, Action, Patronage.' },
];

function statusColor(status: WorkflowComponent['status']): { bg: string; fg: string; label: string } {
  if (status === 'ready') return { bg: '#dcfce7', fg: '#166534', label: 'active' };
  if (status === 'not-wired') return { bg: '#f3f4f6', fg: '#6b7280', label: 'not wired' };
  if (status === 'needs-input') return { bg: '#fef3c7', fg: '#92400e', label: 'needs input' };
  return { bg: '#e0e7ff', fg: '#3730a3', label: 'draft' };
}

export function StrategyDraftPrototype() {
  const [started, setStarted] = useState(false);
  const [visibleCount, setVisibleCount] = useState(0);
  const [activeKey, setActiveKey] = useState<ComponentKey>('buyer');

  const visibleComponents = useMemo(() => components.slice(0, visibleCount), [visibleCount]);
  const active = components.find(component => component.key === activeKey) || components[1];
  const visibleActive = visibleComponents.some(component => component.key === active.key) ? active : visibleComponents[0];

  function triggerPrototype() {
    setStarted(true);
    setVisibleCount(0);
    setActiveKey('buyer');
    components.forEach((component, idx) => {
      window.setTimeout(() => {
        setVisibleCount(idx + 1);
        if (component.status !== 'not-wired') setActiveKey(component.key);
      }, 350 + idx * 240);
    });
  }

  const sidebarItems = started ? visibleComponents : components;
  const renderedActive = visibleActive || active;
  const badge = statusColor(renderedActive.status);

  return (
    <div style={{ minHeight: '100%', background: '#f7f2e8', color: '#1f2937', overflowY: 'auto' }}>
      <div style={{ background: '#0B3D2E', color: '#fff', padding: '28px 32px', borderBottom: '5px solid #826D40' }}>
        <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: '.12em', textTransform: 'uppercase', color: '#d8c9a8', marginBottom: 8 }}>Externalized workflow prototype · no existing BOS piping</div>
        <h1 style={{ margin: 0, fontSize: 30, letterSpacing: '-.03em' }}>Modular Strategy Workflow</h1>
        <p style={{ maxWidth: 930, color: '#f2e8d0', lineHeight: 1.55, margin: '10px 0 0' }}>
          CMO chat should link here instead of dumping the plan. Each component can become an independent skill: buyer map, strategy draft, framework lenses, funnel, measurement, and work orders.
        </p>
      </div>

      <main style={{ padding: 24, maxWidth: 1280, margin: '0 auto 80px' }}>
        <div style={{ background: '#fff', border: '1px solid #e5dccb', borderRadius: 14, padding: 18, marginBottom: 18, display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 12, color: '#826D40', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '.08em' }}>Prototype request</div>
            <div style={{ fontSize: 17, fontWeight: 750, marginTop: 4 }}>Generate pipeline from dormant prospects through Gmail.</div>
            <div style={{ color: '#6b7280', fontSize: 13, marginTop: 4 }}>Gmail is one activation surface inside the GTM motion — not the strategy itself.</div>
            <div style={{ color: '#92400e', fontSize: 12, marginTop: 8, background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: '7px 9px', maxWidth: 760 }}>Locked/grey modules are planned structure only. They are intentionally disabled until their skills/connectors are built.</div>
          </div>
          <button onClick={triggerPrototype} style={{ background: '#0B3D2E', color: '#fff', border: 0, borderRadius: 10, padding: '12px 16px', fontWeight: 800, cursor: 'pointer' }}>
            {started ? 'Re-trigger workflow' : 'Trigger workflow'}
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '300px minmax(0, 1fr)', gap: 18, alignItems: 'start' }}>
          <aside style={{ background: '#fff', border: '1px solid #e5dccb', borderRadius: 16, overflow: 'hidden', position: 'sticky', top: 14 }}>
            <div style={{ background: '#fbf8f0', borderBottom: '1px solid #e5dccb', padding: '14px 16px', fontWeight: 850 }}>Workflow components</div>
            <div style={{ padding: 8 }}>
              {sidebarItems.map((component, idx) => {
                const s = statusColor(component.status);
                const isActive = component.key === renderedActive.key;
                return (
                  <button
                    key={component.key}
                    onClick={() => { if (component.status !== 'not-wired') setActiveKey(component.key); }}
                    disabled={component.status === 'not-wired' || (started && idx >= visibleCount)}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      border: `1px solid ${isActive ? '#0B3D2E' : '#eee6d6'}`,
                      background: component.status === 'not-wired' ? '#f9fafb' : (isActive ? '#f4fbf6' : '#fff'),
                      borderRadius: 10,
                      padding: '10px 11px',
                      marginBottom: 7,
                      cursor: component.status === 'not-wired' ? 'not-allowed' : 'pointer',
                      opacity: component.status === 'not-wired' ? 0.62 : 1,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                      <span style={{ fontWeight: 800, fontSize: 13 }}>{idx + 1}. {component.label}</span>
                      <span style={{ background: s.bg, color: s.fg, borderRadius: 99, padding: '2px 7px', fontSize: 10, fontWeight: 800 }}>{s.label}</span>
                    </div>
                    <div style={{ color: '#6b7280', fontSize: 11, marginTop: 4, lineHeight: 1.35 }}>{component.role}</div>
                  </button>
                );
              })}
            </div>
          </aside>

          <div>
            {!started && (
              <div style={{ background: '#fff', border: '1px solid #e5dccb', borderRadius: 16, padding: 18, marginBottom: 16, color: '#6b7280' }}>
                Click <strong>Trigger workflow</strong> to animate the modular strategy build. You can also inspect components from the left rail before triggering.
              </div>
            )}

            <section style={{ background: '#fff', border: '1px solid #e5dccb', borderRadius: 16, overflow: 'hidden', boxShadow: '0 12px 28px rgba(11,61,46,.06)' }}>
              <div style={{ background: '#fbf8f0', borderBottom: '1px solid #e5dccb', padding: '16px 18px' }}>
                <div style={{ display: 'flex', gap: 10, justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap' }}>
                  <div>
                    <div style={{ color: '#826D40', fontSize: 11, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em' }}>Active component</div>
                    <h2 style={{ margin: '4px 0 2px', fontSize: 22 }}>{renderedActive.label}</h2>
                    <div style={{ color: '#6b7280', fontSize: 13 }}>{renderedActive.role}</div>
                  </div>
                  <span style={{ background: badge.bg, color: badge.fg, borderRadius: 99, padding: '5px 10px', fontSize: 11, fontWeight: 900, textTransform: 'uppercase' }}>{badge.label}</span>
                </div>
              </div>

              <div style={{ padding: 20 }}>
                <div style={{ display: 'grid', gap: 10 }}>
                  {renderedActive.body.map((line, idx) => (
                    <div key={idx} style={{ border: '1px solid #f0eadc', background: idx === 0 ? '#fffdf8' : '#fff', borderRadius: 10, padding: '11px 13px', lineHeight: 1.48, fontSize: 14 }}>{line}</div>
                  ))}
                </div>

                <div style={{ marginTop: 18 }}>
                  <div style={{ color: '#826D40', fontSize: 11, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 8 }}>Component outputs</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {renderedActive.outputs.map(output => (
                      <span key={output} style={{ background: '#f7f2e8', border: '1px solid #e5dccb', borderRadius: 999, padding: '6px 10px', fontSize: 12, fontWeight: 700 }}>{output}</span>
                    ))}
                  </div>
                </div>
              </div>
            </section>

            <section style={{ background: '#fff', border: '1px solid #e5dccb', borderRadius: 16, marginTop: 18, padding: 18, opacity: 0.72 }}>
              <div style={{ color: '#826D40', fontSize: 11, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 10 }}>Framework lenses</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: 10 }}>
                {lenses.map(lens => (
                  <div key={lens.name} style={{ border: '1px solid #eee6d6', borderRadius: 12, padding: 12, background: '#fffdf8' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center', marginBottom: 4 }}><span style={{ fontWeight: 850 }}>{lens.name}</span><span style={{ background: '#f3f4f6', color: '#6b7280', borderRadius: 999, padding: '2px 7px', fontSize: 10, fontWeight: 850 }}>not wired</span></div>
                    <div style={{ color: '#6b7280', fontSize: 12, lineHeight: 1.4 }}>{lens.use}</div>
                  </div>
                ))}
              </div>
            </section>

            <section style={{ background: '#0B3D2E', color: '#fff', borderRadius: 16, marginTop: 18, padding: 18 }}>
              <div style={{ color: '#d8c9a8', fontSize: 11, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 8 }}>CMO chat behavior</div>
              <div style={{ lineHeight: 1.55 }}>
                Chat should only say: “I built the Strategy Workflow. Open it here.” The full strategy lives on this page, where each component can be revised or regenerated independently.
              </div>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
