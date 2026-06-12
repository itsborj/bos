import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';

type ComponentStatus = 'complete' | 'stale' | 'pending' | 'not_wired';

type WorkflowComponent = {
  type: string;
  status: ComponentStatus;
  data: Record<string, unknown>;
};

// Shape returned by GET /strategy-workflows/:id
type WorkflowApiResponse = {
  workflow_id: string;
  brand_id?: string;
  brand_name?: string;
  archetype: string;
  request: string;
  status: string;
  run_id?: string;
  components: {
    id: string;
    component_type: string;
    status: ComponentStatus;
    version: number;
    data: Record<string, unknown>;
    summary?: string;
    run_id?: string;
    updated_at: string;
  }[];
  created_at: string;
  updated_at: string;
};

const COMPONENT_META: Record<string, { label: string; role: string }> = {
  buyer_map:             { label: 'Buyer Map',              role: 'Mandatory substrate — who moves and what stops them.' },
  strategic_thesis:      { label: 'Strategic Thesis',       role: 'Motion selected, wedge, and what we are not doing.' },
  offer_architecture:    { label: 'Offer Architecture',     role: 'Audience need → resource → micro commitment → activation.' },
  channel_stack:         { label: 'Channel Stack',          role: 'Do now, hold, and avoid — mapped to buyer signals.' },
  tactical_funnel:       { label: 'Tactical Funnel',        role: 'REAP execution layer: reach, engage, action, patronage.' },
  work_orders:           { label: 'Work Orders',            role: 'Specialist-ready execution briefs.' },
  market_context:        { label: 'Market Context',         role: 'Ground strategy in market facts and demand signals.' },
  framework_lenses:      { label: 'Framework Lenses',       role: 'Optional overlays: StoryBrand, JTBD, Forces, REAP.' },
  channel_content_matrix:{ label: 'Channel / Content Matrix', role: 'One concept repurposed across channels and formats.' },
  measurement_model:     { label: 'Measurement Model',      role: 'Leading indicators and stage gates.' },
};

const ACTIVE_ORDER = [
  'buyer_map', 'strategic_thesis', 'offer_architecture',
  'channel_stack', 'tactical_funnel', 'work_orders',
];

const NOT_WIRED_ORDER = [
  'market_context', 'framework_lenses',
  'channel_content_matrix', 'measurement_model',
];

function statusBadge(status: ComponentStatus): { label: string; bg: string; fg: string } {
  if (status === 'complete')   return { label: 'active',     bg: '#dcfce7', fg: '#166534' };
  if (status === 'stale')      return { label: 'stale',      bg: '#fef3c7', fg: '#92400e' };
  if (status === 'pending')    return { label: 'pending',    bg: '#e0e7ff', fg: '#3730a3' };
  return { label: 'not wired', bg: '#f3f4f6', fg: '#6b7280' };
}

function BuyerMapView({ data }: { data: Record<string, unknown> }) {
  const fields: [string, string][] = [
    ['Awareness level', data.awareness_level as string],
    ['Buyer type', data.buyer_type as string],
    ['Blocking forces', data.blocking_forces as string],
    ['Trust gap', data.trust_gap as string],
    ['Confidence', data.confidence as string],
  ];
  const lists: [string, string[]][] = [
    ['Push forces', (data.push_forces as string[]) || []],
    ['Pull forces', (data.pull_forces as string[]) || []],
    ['Anxiety sources', (data.anxiety_sources as string[]) || []],
    ['Buyer language', (data.buyer_language as string[]) || []],
  ];
  return (
    <div style={{ display: 'grid', gap: 10 }}>
      {fields.filter(([, v]) => v).map(([label, val]) => (
        <Row key={label} label={label} text={val} />
      ))}
      {lists.filter(([, items]) => items.length > 0).map(([label, items]) => (
        <div key={label} style={rowStyle}>
          <div style={labelStyle}>{label}</div>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {items.map((item, i) => <li key={i} style={{ fontSize: 14, lineHeight: 1.5, color: '#374151' }}>{item}</li>)}
          </ul>
        </div>
      ))}
    </div>
  );
}

function StrategicThesisView({ data }: { data: Record<string, unknown> }) {
  const fields: [string, string][] = [
    ['Primary motion', data.primary_motion as string],
    ['Secondary motion', data.secondary_motion as string],
    ['Secondary unlock', data.secondary_unlock as string],
    ['Wedge', data.wedge as string],
    ['Decision', data.decision as string],
    ['Motion rationale', data.motion_rationale as string],
  ];
  return (
    <div style={{ display: 'grid', gap: 10 }}>
      {fields.filter(([, v]) => v && v !== 'none' && v !== 'n/a').map(([label, val]) => (
        <Row key={label} label={label} text={val} />
      ))}
      {((data.not_doing as string[]) || []).length > 0 && (
        <div style={rowStyle}>
          <div style={labelStyle}>Not doing</div>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {(data.not_doing as string[]).map((item, i) => <li key={i} style={{ fontSize: 14, lineHeight: 1.5, color: '#374151' }}>{item}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function OfferArchitectureView({ data }: { data: Record<string, unknown> }) {
  const fields: [string, string][] = [
    ['Audience need', data.audience_need as string],
    ['Resource', data.resource as string],
    ['Micro commitment', data.micro_commitment as string],
    ['Macro activation', data.macro_activation as string],
    ['Anxiety treatment', data.anxiety_treatment as string],
    ['Proof required', data.proof_required as string],
  ];
  return (
    <div style={{ display: 'grid', gap: 10 }}>
      {fields.filter(([, v]) => v).map(([label, val]) => (
        <Row key={label} label={label} text={val} />
      ))}
      {((data.offer_ladder as string[]) || []).length > 0 && (
        <div style={rowStyle}>
          <div style={labelStyle}>Offer ladder</div>
          <ol style={{ margin: 0, paddingLeft: 20 }}>
            {(data.offer_ladder as string[]).map((item, i) => <li key={i} style={{ fontSize: 14, lineHeight: 1.6, color: '#374151' }}>{item}</li>)}
          </ol>
        </div>
      )}
    </div>
  );
}

function ChannelStackView({ data }: { data: Record<string, unknown> }) {
  const doNow = (data.do_now as Record<string, string>[]) || [];
  const hold  = (data.hold as string[]) || [];
  const avoid = (data.avoid as string[]) || [];
  return (
    <div style={{ display: 'grid', gap: 12 }}>
      {doNow.length > 0 && (
        <div>
          <div style={labelStyle}>Do now</div>
          {doNow.map((ch, i) => (
            <div key={i} style={{ ...rowStyle, marginTop: 8 }}>
              <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 4 }}>{ch.channel}</div>
              {ch.role && <div style={{ fontSize: 13, color: '#374151' }}><span style={{ color: '#6b7280' }}>Role:</span> {ch.role}</div>}
              {ch.buyer_map_signal && <div style={{ fontSize: 13, color: '#374151' }}><span style={{ color: '#6b7280' }}>Buyer signal:</span> {ch.buyer_map_signal}</div>}
              {ch.rationale && <div style={{ fontSize: 13, color: '#374151', marginTop: 4 }}>{ch.rationale}</div>}
            </div>
          ))}
        </div>
      )}
      {hold.length > 0 && (
        <div style={rowStyle}>
          <div style={labelStyle}>Hold</div>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {hold.map((item, i) => <li key={i} style={{ fontSize: 14, lineHeight: 1.5, color: '#374151' }}>{item}</li>)}
          </ul>
        </div>
      )}
      {avoid.length > 0 && (
        <div style={rowStyle}>
          <div style={labelStyle}>Avoid</div>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {avoid.map((item, i) => <li key={i} style={{ fontSize: 14, lineHeight: 1.5, color: '#374151' }}>{item}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function TacticalFunnelView({ data }: { data: Record<string, unknown> }) {
  const fields: [string, string][] = [
    ['Reach tactic', data.reach_tactic as string],
    ['Engage resource', data.engage_resource as string],
    ['Action CTA', data.action_cta as string],
    ['Proof capture', data.proof_capture as string],
  ];
  return (
    <div style={{ display: 'grid', gap: 10 }}>
      {fields.filter(([, v]) => v).map(([label, val]) => (
        <Row key={label} label={label} text={val} />
      ))}
      {data.raw ? (
        <div style={{ ...rowStyle, background: '#f9fafb', borderColor: '#e5e7eb' }}>
          <div style={labelStyle}>Full funnel detail</div>
          <pre style={{ fontSize: 12, lineHeight: 1.5, color: '#374151', whiteSpace: 'pre-wrap', margin: 0 }}>{String(data.raw)}</pre>
        </div>
      ) : null}
    </div>
  );
}

function WorkOrdersView({ data }: { data: Record<string, unknown> }) {
  const briefs = (data.briefs as Record<string, unknown>[]) || [];
  if (briefs.length === 0 && data.raw) {
    return <pre style={{ fontSize: 13, lineHeight: 1.55, color: '#374151', whiteSpace: 'pre-wrap', margin: 0 }}>{data.raw as string}</pre>;
  }
  return (
    <div style={{ display: 'grid', gap: 12 }}>
      {briefs.map((brief, i) => (
        <div key={i} style={rowStyle}>
          <div style={{ fontWeight: 800, fontSize: 14, marginBottom: 4 }}>{i + 1}. {brief.title as string}</div>
          {brief.purpose ? <div style={{ fontSize: 13, color: '#374151', marginBottom: 6 }}>{String(brief.purpose)}</div> : null}
          {((brief.contents as string[]) || []).length > 0 && (
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {(brief.contents as string[]).map((item, j) => <li key={j} style={{ fontSize: 13, lineHeight: 1.5, color: '#374151' }}>{item}</li>)}
            </ul>
          )}
          {brief.gate ? <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6, fontStyle: 'italic' }}>Gate: {String(brief.gate)}</div> : null}
        </div>
      ))}
    </div>
  );
}

function RawView({ data }: { data: Record<string, unknown> }) {
  return <pre style={{ fontSize: 12, lineHeight: 1.55, color: '#374151', whiteSpace: 'pre-wrap', margin: 0 }}>{(data.raw as string) || JSON.stringify(data, null, 2)}</pre>;
}

const COMPONENT_VIEWS: Record<string, (props: { data: Record<string, unknown> }) => React.ReactElement> = {
  buyer_map:          BuyerMapView,
  strategic_thesis:   StrategicThesisView,
  offer_architecture: OfferArchitectureView,
  channel_stack:      ChannelStackView,
  tactical_funnel:    TacticalFunnelView,
  work_orders:        WorkOrdersView,
};

const rowStyle: React.CSSProperties = {
  border: '1px solid #f0eadc',
  background: '#fffdf8',
  borderRadius: 10,
  padding: '11px 13px',
};

const labelStyle: React.CSSProperties = {
  fontWeight: 850,
  fontSize: 11,
  color: '#826D40',
  textTransform: 'uppercase',
  letterSpacing: '.06em',
  marginBottom: 4,
};

function Row({ label, text }: { label: string; text: string }) {
  return (
    <div style={rowStyle}>
      <div style={labelStyle}>{label}</div>
      <div style={{ fontSize: 14, lineHeight: 1.5, color: '#374151' }}>{text}</div>
    </div>
  );
}

export function StrategyWorkflowPage() {
  const { workflowId } = useParams<{ workflowId: string }>();
  const [workflow, setWorkflow] = useState<WorkflowApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeType, setActiveType] = useState<string>('buyer_map');

  useEffect(() => {
    if (!workflowId) return;
    setLoading(true);
    api.getStrategyWorkflow(workflowId)
      .then(data => { setWorkflow(data as unknown as WorkflowApiResponse); setLoading(false); })
      .catch(err => { setError(err.message || 'Failed to load workflow'); setLoading(false); });
  }, [workflowId]);

  // Map API component shape to internal view shape
  const components: WorkflowComponent[] = (workflow?.components || []).map(c => ({
    type: c.component_type,
    status: c.status,
    data: c.data,
  }));
  const notWired: string[] = components
    .filter(c => c.status === 'not_wired')
    .map(c => c.type)
    .filter(t => NOT_WIRED_ORDER.includes(t));

  // Derive display fields from component data
  const thesis = components.find(c => c.type === 'strategic_thesis')?.data || {};
  const primaryMotion = (thesis.primary_motion as string) || '';

  const allSidebarItems = [
    ...ACTIVE_ORDER.map(type => {
      const comp = components.find(c => c.type === type);
      return { type, status: comp?.status || 'pending' as ComponentStatus, data: comp?.data || {} };
    }),
    ...notWired.map(type => ({ type, status: 'not_wired' as ComponentStatus, data: {} })),
  ];

  const activeItem = allSidebarItems.find(c => c.type === activeType) || allSidebarItems[0];
  const meta = COMPONENT_META[activeItem?.type] || { label: activeItem?.type, role: '' };
  const badge = statusBadge(activeItem?.status || 'not_wired');
  const ViewComponent = COMPONENT_VIEWS[activeItem?.type] || RawView;

  if (loading) {
    return (
      <div style={{ minHeight: '100%', background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#826D40', fontSize: 15, fontWeight: 700 }}>
        Loading strategy workflow…
      </div>
    );
  }

  if (error || !workflow) {
    return (
      <div style={{ minHeight: '100%', background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 15, color: '#dc2626', fontWeight: 700, marginBottom: 8 }}>{error || 'Strategy workflow not found.'}</div>
          <Link to="/stream" style={{ fontSize: 13, color: '#826D40' }}>← Back to Stream</Link>
        </div>
      </div>
    );
  }

  const archetype = workflow.archetype?.replace(/_/g, ' ') || '';
  const brandName = workflow.brand_name || 'Brand';

  return (
    <div style={{ minHeight: '100%', background: '#fff', color: '#1f2937', overflowY: 'auto' }}>
      <header style={{ background: '#0B3D2E', color: '#fff', padding: '28px 32px', borderBottom: '5px solid #826D40' }}>
        <Link to="/stream" style={{ display: 'inline-block', marginBottom: 14, fontSize: 12, color: '#a8c8b8', textDecoration: 'none', fontWeight: 700, letterSpacing: '.04em' }}>← Back to Stream</Link>
        <div className="strategy-workflow-kicker" style={{ fontSize: 11, fontWeight: 900, letterSpacing: '.12em', textTransform: 'uppercase', marginBottom: 8 }}>
          Strategy Workflow · {archetype}
        </div>
        <h1 className="strategy-workflow-headline" style={{ margin: 0, fontSize: 31, letterSpacing: '-.03em', fontWeight: 900 }}>
          {brandName} Marketing Strategy
        </h1>
      </header>

      <main style={{ maxWidth: 1280, margin: '0 auto 80px', padding: 24, background: '#fff' }}>
        <div style={{ background: '#fff', border: '1px solid #e5dccb', borderRadius: 14, padding: 18, marginBottom: 18, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <div style={{ color: '#826D40', fontSize: 12, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em' }}>Motion</div>
            <div style={{ marginTop: 4, fontSize: 17, fontWeight: 800 }}>{primaryMotion || '—'}</div>
          </div>
          <div style={{ color: '#6b7280', fontSize: 13, maxWidth: 700 }}>Draft strategy — execution artifacts, outreach, publishing, spend, and external platform actions require separate approval.</div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '300px minmax(0, 1fr)', gap: 18, alignItems: 'start' }}>
          <aside style={{ background: '#fff', border: '1px solid #e5dccb', borderRadius: 16, overflow: 'hidden', position: 'sticky', top: 14 }}>
            <div style={{ background: '#fbf8f0', borderBottom: '1px solid #e5dccb', padding: '14px 16px', fontWeight: 850 }}>Workflow components</div>
            <div style={{ padding: 8 }}>
              {allSidebarItems.map((item, idx) => {
                const m = COMPONENT_META[item.type] || { label: item.type, role: '' };
                const b = statusBadge(item.status);
                const isActive = item.type === activeType;
                const canClick = item.status !== 'not_wired';
                return (
                  <button
                    key={item.type}
                    onClick={() => canClick && setActiveType(item.type)}
                    disabled={!canClick}
                    style={{
                      width: '100%', textAlign: 'left',
                      border: `1px solid ${isActive ? '#0B3D2E' : '#eee6d6'}`,
                      background: !canClick ? '#f9fafb' : isActive ? '#f4fbf6' : '#fff',
                      opacity: !canClick ? 0.6 : 1,
                      borderRadius: 10, padding: '10px 11px', marginBottom: 7,
                      cursor: canClick ? 'pointer' : 'not-allowed',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontWeight: 850, fontSize: 13 }}>{idx + 1}. {m.label}</span>
                      <span style={{ background: b.bg, color: b.fg, borderRadius: 999, padding: '2px 7px', fontSize: 10, fontWeight: 850 }}>{b.label}</span>
                    </div>
                    <div style={{ color: '#6b7280', fontSize: 11, marginTop: 4, lineHeight: 1.35 }}>{m.role}</div>
                  </button>
                );
              })}
            </div>
          </aside>

          <section style={{ background: '#fff', border: '1px solid #e5dccb', borderRadius: 16, overflow: 'hidden', boxShadow: '0 12px 28px rgba(11,61,46,.06)' }}>
            <div style={{ background: '#fbf8f0', borderBottom: '1px solid #e5dccb', padding: '16px 18px', display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <div>
                <div style={{ color: '#826D40', fontSize: 11, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em' }}>Active component</div>
                <h2 style={{ margin: '4px 0 2px', fontSize: 22 }}>{meta.label}</h2>
                <div style={{ color: '#6b7280', fontSize: 13 }}>{meta.role}</div>
              </div>
              <span style={{ background: badge.bg, color: badge.fg, borderRadius: 999, padding: '5px 10px', fontSize: 11, fontWeight: 900, textTransform: 'uppercase' }}>{badge.label}</span>
            </div>
            <div style={{ padding: 20 }}>
              {activeItem.status === 'not_wired' ? (
                <div style={{ color: '#9ca3af', fontSize: 14, fontStyle: 'italic', textAlign: 'center', padding: '40px 0' }}>
                  This component is planned architecture — not yet wired. It will be available in a future version.
                </div>
              ) : (
                <ViewComponent data={activeItem.data} />
              )}
            </div>
          </section>
        </div>

        <div style={{ background: '#0B3D2E', color: '#fff', borderRadius: 16, marginTop: 18, padding: 18 }}>
          <div style={{ color: '#d8c9a8', fontSize: 11, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 8 }}>CMO behavior</div>
          <div style={{ lineHeight: 1.55, color: '#f2e8d0' }}>
            Built the Strategy Workflow for <strong>{primaryMotion || archetype}</strong>.
            {' '}Each component is independently revisable. Execution requires separate approval.
          </div>
        </div>
      </main>
    </div>
  );
}
