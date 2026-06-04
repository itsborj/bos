import { useMemo, useState } from 'react';

type Status = 'active' | 'future';

type PlanModule = {
  title: string;
  status: Status;
  role: string;
  sections: { label: string; text: string }[];
  outputs: string[];
};

const modules: PlanModule[] = [
  {
    title: 'Market Context',
    status: 'active',
    role: 'Ground the plan in local demand, scarcity, and competitive reality.',
    sections: [
      { label: 'Local market', text: 'Daanbantayan has 20 barangays, 22K+ households, and 93K+ residents. Key barangays: Bagay, Malbago, Calape, Tibubdan. Golden Gate is positioned in Calape with a narrow premium inventory ceiling: 2,537 lawn lot units.' },
      { label: 'Opportunity', text: 'The premium North Cebu memorial segment has no Tier 1 national memorial park presence. Public cemeteries are the functional competitor but fail on dignity, planning, maintenance, and peace of mind.' },
      { label: 'Demand proof', text: 'All Saints Day visitor volume and local family memorial behavior show existing category demand. The growth problem is not creating the need; it is making families act before grief forces a rushed decision.' },
    ],
    outputs: ['Local TAM', 'Scarcity proof', 'Competitor contrast', 'Demand timing'],
  },
  {
    title: 'Buyer Map',
    status: 'active',
    role: 'Identify the highest-hunger buyers and the emotional triggers that move them.',
    sections: [
      { label: 'Highest hunger segment', text: 'OFWs / seafarers with aging parents, Northern Cebu roots, remittance income, absence guilt, and monthly-payment behavior.' },
      { label: 'Secondary segments', text: 'Life plan holders, adult children/family stewards, local business owners/investors, balikbayans, and affluent family heads.' },
      { label: 'Primary trigger', text: 'Aging parents + OFW absence + no existing memorial property. This creates urgency before death occurs without requiring scare tactics.' },
      { label: 'Buyer blockers', text: 'Avoidance, discomfort discussing death, no urgency until crisis, sibling decision friction, and fear of being sold something morbid or exploitative.' },
    ],
    outputs: ['Hungry segments', 'Buying triggers', 'Blocking forces', 'Decision psychology'],
  },
  {
    title: 'Strategy Draft',
    status: 'active',
    role: 'Management-alignment layer: what we lead with and why.',
    sections: [
      { label: 'GTM archetype', text: 'Local-market emotional urgency + broker distribution + lead magnet conversion.' },
      { label: 'Strategic decision', text: 'Own the category of “Family Legacy Planning for Northern Cebu Families.” Do not lead as a cemetery or lot seller. Lead as the family decision that prevents loved ones from carrying cost, confusion, and shame during grief.' },
      { label: 'Core message', text: '“I already handled it.” Every campaign should create the path to that statement.' },
      { label: 'Positioning', text: 'Golden Gate is the premium, planned, dignified memorial home for Northern Cebu families who want peace of mind before the family needs it.' },
      { label: 'What not to do', text: 'Do not make the first strategy a generic price-list blast. Price matters, but the category is won through family duty, dignity, scarcity, and readiness.' },
    ],
    outputs: ['Category to own', 'Core message', 'Positioning', 'Strategic no-list'],
  },
  {
    title: 'StoryBrand Lens',
    status: 'active',
    role: 'Narrative lens for clearer messaging. This strengthens the Strategy Draft; it is not the whole workflow.',
    sections: [
      { label: 'Character', text: 'The family steward, OFW, or adult child who wants to protect the family from painful last-minute decisions.' },
      { label: 'Problem', text: 'External: no reserved memorial property. Emotional: guilt and anxiety. Philosophical: the worst moment to decide where someone rests is when the family is already grieving.' },
      { label: 'Guide', text: 'Golden Gate gives the family a dignified, maintained, accessible place and a simple payment path.' },
      { label: 'Plan', text: 'Take readiness checklist → choose care fund or lot path → visit/site consult → reserve → tell siblings the plan is handled.' },
      { label: 'CTA', text: 'Get your Family Memorial Readiness Score. Secondary CTA: schedule a site visit or talk to a family planning advisor.' },
      { label: 'Success', text: '“Nung pumanaw si Tatay, alam namin lahat. Hindi na kami nagmadali. May lugar na siya.”' },
    ],
    outputs: ['Character', 'Problem', 'Guide', 'Plan', 'CTA', 'Success stakes'],
  },
  {
    title: 'Offer Architecture',
    status: 'active',
    role: 'Turn emotional urgency into a practical buying path.',
    sections: [
      { label: 'Lead magnet', text: 'Family Memorial Readiness Checklist: “Get Your Family Readiness Score.” This exposes the pain without immediately selling a lot.' },
      { label: 'Entry offer', text: 'Memorial Care Fund ₱50–500/mo. Lowest-barrier step that creates a relationship and makes dignity feel immediately affordable.' },
      { label: 'Core product', text: 'Lawn Lot from ₱2,500/mo, 2,537 units only, 10% spot cash discount. This is the main reservation path.' },
      { label: 'Upsell/cross-sell', text: 'Life plan holder discounts, Garden Lot, Family Villa, Ossuary/Columbary, and qualifying-lot columbary promo.' },
      { label: 'Offer risk', text: 'Promos must never cheapen the emotional promise. Discounts should be framed as planning rewards, not bargain cemetery sales.' },
    ],
    outputs: ['Lead magnet', 'Entry offer', 'Core path', 'Upsell path', 'Promo guardrails'],
  },
  {
    title: 'Distribution System',
    status: 'active',
    role: 'Define how leads are created, qualified, routed, and closed.',
    sections: [
      { label: 'Do now', text: 'Facebook/Instagram local demand, Google Business Profile, broker/agent network, QR-coded local materials, readiness checklist landing page, site-visit booking page.' },
      { label: 'Broker pools', text: 'Insurance agents, real estate brokers, cooperative officers, teachers/government employees, church/community leaders.' },
      { label: 'Broker positioning', text: 'You are not recruiting sellers. You are offering a community legacy business with recurring local demand and emotional importance.' },
      { label: 'Hold', text: 'Mass media and broad brand campaigns until attribution, frontline response, and broker routing are stable.' },
    ],
    outputs: ['Channel roles', 'Broker pools', 'Lead routing', 'Hold/avoid logic'],
  },
  {
    title: 'Tactical Funnel',
    status: 'active',
    role: 'Flexible execution layer. Specific audience need → resource → micro commitment → activation.',
    sections: [
      { label: 'Reach', text: 'Barangay-focused Facebook/IG content, broker referrals, QR codes near site/events, Google Business Profile/search, life-plan/insurance partner audiences.' },
      { label: 'Engage', text: 'Family Readiness Score, emergency-vs-planned cost education, construction progress, behind-the-scenes care/maintenance, family planning stories.' },
      { label: 'Action', text: 'Checklist completion, Messenger/WhatsApp consult, site visit booking, Memorial Care Fund start, lot reservation.' },
      { label: 'Patronage', text: 'Testimonials, family referrals, broker success stories, annual care reminders, All Saints Day proof moments.' },
    ],
    outputs: ['Reach plan', 'Engagement resources', 'Activation steps', 'Advocacy loop'],
  },
  {
    title: 'Measurement Model',
    status: 'active',
    role: 'Track learning and frontline execution, not vanity activity.',
    sections: [
      { label: 'Reach', text: 'Barangay reach, QR scans by source, GBP views/actions, paid reach, broker-sourced lead volume.' },
      { label: 'Engagement', text: 'Checklist starts/completions, Messenger conversations, content saves/shares, video watch quality, landing page time.' },
      { label: 'Action', text: 'Qualified consults, site visits booked, site visits attended, care fund starts, lot reservations, payment plan selection.' },
      { label: 'Patronage', text: 'Family referrals, broker repeat sales, testimonial permissions, review volume, repeat product/cross-sell movement.' },
    ],
    outputs: ['REAP metrics', 'Source attribution', 'Broker metrics', 'Conversion gates'],
  },
  {
    title: '30-Day Activation Work Orders',
    status: 'active',
    role: 'Specialist-ready briefs generated from the strategy.',
    sections: [
      { label: 'Week 1 — Foundation', text: 'Assign approval owner and frontline responder; collect final price/product source of truth; verify Google Business Profile; set up Meta, Google Workspace, QR links, and source tracking.' },
      { label: 'Week 2 — Offer architecture', text: 'Build Family Readiness Checklist, promo landing page, life plan holder page, broker recruitment page, site visit booking flow, and master offer matrix.' },
      { label: 'Week 3 — Distribution launch', text: 'Launch broker recruitment to five pools, publish content pillars, activate Memorial Care Fund, run barangay-focused social/QR campaigns.' },
      { label: 'Week 4 — Optimize', text: 'Review lead source quality, broker activity, site visit conversion, readiness-score answers, and frontline response time; choose Month 2 focus.' },
    ],
    outputs: ['Landing pages', 'Lead magnet', 'Broker pack', 'Content calendar', 'Attribution setup'],
  },
  {
    title: 'Automation Modules',
    status: 'future',
    role: 'Planned capability, not wired in this prototype.',
    sections: [
      { label: 'AI Sales Concierge', text: 'Future module: qualify Messenger/WhatsApp/QR/website leads, score urgency, capture family context, and route to human responder.' },
      { label: 'Broker OS', text: 'Future module: recruitment, onboarding, training assistant, activation tracking, and broker performance.' },
      { label: 'Attribution Dashboard', text: 'Future module: source tags, QR attribution, broker metrics, booking conversion, and campaign reporting.' },
    ],
    outputs: ['Not wired', 'Future automation scope', 'Connector requirements'],
  },
];

function badge(status: Status): { label: string; bg: string; fg: string } {
  return status === 'active'
    ? { label: 'active sample', bg: '#dcfce7', fg: '#166534' }
    : { label: 'not wired', bg: '#f3f4f6', fg: '#6b7280' };
}

export function GoldenGateStrategyWorkflow() {
  const [started, setStarted] = useState(false);
  const [visibleCount, setVisibleCount] = useState(0);
  const [activeIndex, setActiveIndex] = useState(0);
  const visible = useMemo(() => modules.slice(0, visibleCount), [visibleCount]);
  const active = (started ? visible[activeIndex] : modules[activeIndex]) || modules[0];
  const b = badge(active.status);

  function trigger() {
    setStarted(true);
    setVisibleCount(0);
    setActiveIndex(0);
    modules.forEach((_, idx) => {
      window.setTimeout(() => {
        setVisibleCount(idx + 1);
        setActiveIndex(idx);
      }, 250 + idx * 220);
    });
  }

  return (
    <div style={{ minHeight: '100%', background: '#f7f2e8', color: '#1f2937', overflowY: 'auto' }}>
      <header style={{ background: '#0B3D2E', color: '#fff', padding: '28px 32px', borderBottom: '5px solid #826D40' }}>
        <div style={{ color: '#d8c9a8', fontSize: 11, fontWeight: 900, letterSpacing: '.12em', textTransform: 'uppercase', marginBottom: 8 }}>Externalized Strategy Workflow · Golden Gate sample</div>
        <h1 style={{ margin: 0, fontSize: 31, letterSpacing: '-.03em' }}>Golden Gate Marketing Plan</h1>
        <p style={{ maxWidth: 980, color: '#f2e8d0', lineHeight: 1.55, margin: '10px 0 0' }}>
          A modular marketing strategy built from market context, buyer map, StoryBrand lens, offer architecture, distribution, tactical funnel, measurement, and work orders. No CMO chat dump. No Stream card.
        </p>
      </header>

      <main style={{ maxWidth: 1280, margin: '0 auto 80px', padding: 24 }}>
        <div style={{ background: '#fff', border: '1px solid #e5dccb', borderRadius: 14, padding: 18, marginBottom: 18, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <div style={{ color: '#826D40', fontSize: 12, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em' }}>Plan objective</div>
            <div style={{ marginTop: 4, fontSize: 17, fontWeight: 800 }}>Own “Family Legacy Planning for Northern Cebu Families.”</div>
            <div style={{ color: '#6b7280', fontSize: 13, marginTop: 5 }}>Lead with readiness, dignity, family duty, scarcity, and broker/community distribution.</div>
          </div>
          <button onClick={trigger} style={{ background: '#0B3D2E', color: '#fff', border: 0, borderRadius: 10, padding: '12px 16px', fontWeight: 850, cursor: 'pointer' }}>{started ? 'Re-run plan workflow' : 'Run plan workflow'}</button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '310px minmax(0, 1fr)', gap: 18, alignItems: 'start' }}>
          <aside style={{ background: '#fff', border: '1px solid #e5dccb', borderRadius: 16, overflow: 'hidden', position: 'sticky', top: 14 }}>
            <div style={{ background: '#fbf8f0', borderBottom: '1px solid #e5dccb', padding: '14px 16px', fontWeight: 850 }}>Plan modules</div>
            <div style={{ padding: 8 }}>
              {(started ? visible : modules).map((module, idx) => {
                const mb = badge(module.status);
                const isActive = module === active;
                return (
                  <button key={module.title} onClick={() => module.status === 'active' && setActiveIndex(idx)} disabled={module.status === 'future'} style={{ width: '100%', textAlign: 'left', border: `1px solid ${isActive ? '#0B3D2E' : '#eee6d6'}`, background: module.status === 'future' ? '#f9fafb' : (isActive ? '#f4fbf6' : '#fff'), opacity: module.status === 'future' ? 0.62 : 1, borderRadius: 10, padding: '10px 11px', marginBottom: 7, cursor: module.status === 'future' ? 'not-allowed' : 'pointer' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontWeight: 850, fontSize: 13 }}>{idx + 1}. {module.title}</span>
                      <span style={{ background: mb.bg, color: mb.fg, borderRadius: 999, padding: '2px 7px', fontSize: 10, fontWeight: 850 }}>{mb.label}</span>
                    </div>
                    <div style={{ color: '#6b7280', fontSize: 11, marginTop: 4, lineHeight: 1.35 }}>{module.role}</div>
                  </button>
                );
              })}
            </div>
          </aside>

          <section style={{ background: '#fff', border: '1px solid #e5dccb', borderRadius: 16, overflow: 'hidden', boxShadow: '0 12px 28px rgba(11,61,46,.06)' }}>
            <div style={{ background: '#fbf8f0', borderBottom: '1px solid #e5dccb', padding: '16px 18px', display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <div>
                <div style={{ color: '#826D40', fontSize: 11, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em' }}>Active module</div>
                <h2 style={{ margin: '4px 0 2px', fontSize: 22 }}>{active.title}</h2>
                <div style={{ color: '#6b7280', fontSize: 13 }}>{active.role}</div>
              </div>
              <span style={{ background: b.bg, color: b.fg, borderRadius: 999, padding: '5px 10px', fontSize: 11, fontWeight: 900, textTransform: 'uppercase' }}>{b.label}</span>
            </div>
            <div style={{ padding: 20 }}>
              <div style={{ display: 'grid', gap: 10 }}>
                {active.sections.map(section => (
                  <div key={section.label} style={{ border: '1px solid #f0eadc', borderRadius: 10, padding: '12px 13px', background: '#fffdf8' }}>
                    <div style={{ fontWeight: 850, marginBottom: 4 }}>{section.label}</div>
                    <div style={{ fontSize: 14, lineHeight: 1.5, color: '#374151' }}>{section.text}</div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 18 }}>
                <div style={{ color: '#826D40', fontSize: 11, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 8 }}>Outputs</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {active.outputs.map(output => <span key={output} style={{ background: '#f7f2e8', border: '1px solid #e5dccb', borderRadius: 999, padding: '6px 10px', fontSize: 12, fontWeight: 750 }}>{output}</span>)}
                </div>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
