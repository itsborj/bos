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
    role: 'Ground the strategy in the motorcycle buyer market before brand positioning starts.',
    sections: [
      { label: 'Category reality', text: 'Motorcycles are the primary personal mobility option for the 18–35 segment with medium-to-low budget. The decision is not luxury — it is necessity with anxiety. The buyer has already decided to buy; the question is who they trust to help them choose right.' },
      { label: 'Competitive landscape', text: 'Existing options: branded dealerships (intimidating, sales-pressure reputation), secondhand markets (high risk anxiety), generic online listings (no guidance). None of these address the trust gap for a first-time buyer. MotorMoto\'s gap is the absence of a helpful, non-predatory buying guide that results in a purchase.' },
      { label: 'Demand signal', text: 'First-time buyers are actively researching. The search and social behavior is already present — "best first motorcycle," "reliable beginner motorcycle," "motorcycle for commuting." Demand does not need to be created. It needs to be captured and converted through trust.' },
    ],
    outputs: ['Category demand proof', 'Competitor contrast', 'Buyer search behavior', 'Trust gap location'],
  },
  {
    title: 'Buyer Map',
    status: 'active',
    role: 'Mandatory substrate — defines who moves and what stops them.',
    sections: [
      { label: 'Primary segment', text: 'First-time motorcycle buyers aged 18–35, medium-to-low budget, seeking dependable daily mobility. They are solution-aware: they know they want a motorcycle but are anxious about making the wrong choice (wrong model, bad value, post-purchase regret, safety risk).' },
      { label: 'Blocking forces', text: 'Anxiety is the dominant force. Habit is secondary — they default to researching online indefinitely rather than committing. Low perceived likelihood: they are not confident they can identify the right motorcycle without expert guidance. Trust gap: reliability and dependability proof does not exist from MotorMoto yet.' },
      { label: 'Push forces', text: 'Rising commute costs, unreliable public transport, peer ownership (friends who already ride), and time savings from motorcycle vs car or transit. The urgency exists — it is not manufactured.' },
      { label: 'Buyer language', text: '"Is this reliable?" / "Will I regret this?" / "What do people actually ride for commuting?" / "I don\'t want to be sold something that breaks." / "My friend said to ask around first."' },
    ],
    outputs: ['Awareness level', 'Dominant blocking force', 'Trust gap', 'Buyer language', 'Decision triggers'],
  },
  {
    title: 'Strategic Thesis',
    status: 'active',
    role: 'Management-alignment layer: motion selected, rationale, what we are not doing.',
    sections: [
      { label: 'GTM motion', text: 'Sales-led primary. Content-led secondary — unlocks after a baseline of customer testimonials and case studies is established. Not founder-led (no personal network signal loaded). Not product-led (product requires human trust before commitment at this price point). Not partner-led (no existing partnerships confirmed). Not community-led (no existing rider community to seed).' },
      { label: 'Strategic decision', text: 'Own "The trusted first motorcycle buying experience." Do not compete on price or selection. Compete on the quality of guidance and the confidence the buyer feels at the end of the process. Every touchpoint should reduce buyer anxiety, not increase excitement about the product.' },
      { label: 'Wedge', text: '"Before you choose a motorcycle, talk to someone who will tell you what fits your situation — not what sells fastest." This positions MotorMoto as the advisor, not the seller.' },
      { label: 'What not to do', text: 'Do not lead with product specs, brand comparisons, or promotional pricing. Do not use excitement-driven copy that increases aspiration before anxiety is addressed. Do not advertise broadly before the conversion path is validated end-to-end.' },
    ],
    outputs: ['GTM motion', 'Strategic decision', 'Wedge', 'Strategic no-list'],
  },
  {
    title: 'Offer Architecture',
    status: 'active',
    role: 'Audience need → resource → micro commitment → macro activation.',
    sections: [
      { label: 'Lead resource', text: '"First Bike Fit Guide" — a short, practical resource that helps the buyer identify what type of riding they will actually do (commute, leisure, mixed), their real budget range including running costs, and the 3 models that fit that profile. No sales pressure. No brand comparison table. Just honest guidance.' },
      { label: 'Micro commitment', text: 'Request the guide or answer 3 questions (riding type, budget, experience level) to get a personalised shortlist. Zero obligation. Collects the buyer\'s stated context for follow-up.' },
      { label: 'Macro activation', text: 'Book a 20-minute consultation: "Tell me about your situation and I\'ll tell you what I would choose if I were you." Human-led. Trust-first. No pitch until the buyer asks for pricing.' },
      { label: 'Offer ladder', text: 'First Bike Fit Guide (zero commitment) → personalised shortlist (micro) → consultation call (low) → test ride or product walkthrough (medium) → purchase decision (full).' },
      { label: 'Proof unlock sequence', text: 'Proof does not exist yet. Stage 1 priority: document the first 3 buyer journeys in buyer language. Even anonymous case narratives ("a 24-year-old commuter in Manila who was choosing between X and Y") are credible proof at this stage.' },
    ],
    outputs: ['Lead magnet', 'Micro goal', 'Macro goal', 'Offer ladder', 'Proof build sequence'],
  },
  {
    title: 'Channel Stack',
    status: 'active',
    role: 'Where to show up now, what to hold, and what to avoid — mapped to the buyer map.',
    sections: [
      { label: 'Do now', text: 'Landing page (conversion hub — clear guide offer, consultation CTA, 3-question shortlist). Direct consultation (phone or Messenger — primary trust surface for anxious first-time buyers). Google / organic search (intent capture — buyers are already searching; a helpful first result earns the conversation).' },
      { label: 'Hold', text: 'Email marketing — no owned list or CRM loaded. Hold until Stage 1 opt-ins are collected from guide downloads. Paid social — no proof assets. Hold until 3+ testimonials or case narratives exist. Influencer/creator — no partnerships confirmed. Hold until core conversion path is validated.' },
      { label: 'Avoid for now', text: 'Mass brand awareness campaigns — wrong stage, no proof to back credibility claims. Generic product listing sites — commoditises the offer and removes the trust-building surface. Price-comparison angles — attracts the wrong buyer segment (price-first vs trust-first).' },
    ],
    outputs: ['Do-now stack', 'Hold conditions', 'Avoid rationale', 'Channel-to-buyer-map mapping'],
  },
  {
    title: 'Tactical Funnel (REAP)',
    status: 'active',
    role: 'Flexible execution layer after strategic approval.',
    sections: [
      { label: 'Reach', text: 'Organic search content targeting first-time buyer queries. Targeted landing page for "first motorcycle" and "beginner motorcycle [city]" intent. Direct outreach to warm personal or professional contacts who fit the buyer profile.' },
      { label: 'Engage', text: 'First Bike Fit Guide download. 3-question shortlist tool. Short content pieces that name common first-time buyer anxieties and answer them honestly ("The 4 mistakes first-time buyers make when choosing a commuter motorcycle").' },
      { label: 'Action', text: 'Guide download → personalised shortlist → consultation booking. Primary CTA at every touchpoint is the consultation, not the purchase. Buying is the outcome of the consultation, not the destination of the ad.' },
      { label: 'Patronage / Learning', text: 'After first 3 purchases: capture buyer language from the consultation notes. Document the journey (what they feared, what they chose, what happened). Build the proof archive that unlocks Stage 2 channels. Track which guide questions predicted the consultation conversion.' },
    ],
    outputs: ['Reach tactic', 'Engagement resource', 'Action step', 'Learning loop'],
  },
  {
    title: 'Measurement Model',
    status: 'active',
    role: 'Leading indicators by stage — no fabricated numeric targets.',
    sections: [
      { label: 'Stage 0 — Foundation', text: 'Landing page live and tracked: yes/no. Guide downloadable and working: yes/no. Consultation booking flow functional: yes/no. At least one ICP-match person confirms the guide sounds useful: yes/no.' },
      { label: 'Stage 1 — First conversations', text: 'Guide downloads per week: baseline required. Consultation requests per week: baseline required. Buyer language captured from consultations: yes/no. First objection documented: yes/no.' },
      { label: 'Stage 2 — Conversion validation', text: 'Guide → consultation rate: requires baseline. Consultation → purchase rate: requires baseline. Time from first touch to purchase decision: requires baseline. First proof asset (even anonymous): exists/not yet.' },
      { label: 'Stage 3+ gates', text: 'Paid social unlocks when: 3+ testimonials or case narratives exist and consultation conversion rate is known. Email unlocks when: opt-in list from guide downloads reaches a workable volume. Influencer/creator unlocks when: core conversion path is validated end-to-end and a proof package exists to give creators.' },
    ],
    outputs: ['Stage-0 readiness checks', 'Stage-1 leading indicators', 'Stage-2 conversion signals', 'Channel unlock gates'],
  },
  {
    title: 'Work Orders',
    status: 'active',
    role: 'Specialist-ready briefs produced from the strategy. Execute after approval.',
    sections: [
      { label: '1. First Bike Fit Guide', text: 'Build a short, honest guide (PDF or web page) that helps the buyer identify their riding type, budget (including running costs), and the 3 models that fit their profile. Tone: helpful expert friend, not salesperson. No brand bias. No promotional language. Outputs: guide asset, download/request CTA, lead capture form.' },
      { label: '2. Landing page', text: 'Single-purpose page: who MotorMoto is for, the guide offer, 3-question shortlist form, consultation booking CTA. No product catalogue. No pricing table. Social proof placeholder (to be replaced when first testimonials exist). Set up source tracking before launch.' },
      { label: '3. Consultation script', text: 'A structured 20-minute call framework: open with their situation (not the product), confirm riding type and budget, surface the anxiety they have not said out loud, recommend 2–3 options with honest trade-offs, close with "what would you like to do next?" Do not pitch. Let the buyer lead to the purchase decision.' },
      { label: '4. Objection response sheet', text: 'Document answers to: "How do I know this is reliable?" / "What if something breaks after I buy?" / "Are you going to push me to buy the most expensive one?" / "Can I see reviews from people like me?" These are the 4 anxieties that will stall every consultation until proof exists.' },
      { label: '5. Proof capture brief', text: 'After first 3 purchases: interview each buyer. Questions: what were you worried about before? What made you choose this? What happened after? Capture in their words. Even anonymous. This is the Stage 2 unlock asset.' },
    ],
    outputs: ['Guide asset', 'Landing page brief', 'Consultation script', 'Objection sheet', 'Proof capture template'],
  },
  {
    title: 'Content Engine',
    status: 'future',
    role: 'Planned capability — activates after Stage 1 proof assets exist.',
    sections: [
      { label: 'Content strategy', text: 'Future: publish short-form content targeting first-time buyer anxieties. Formats: honest "what I wish I knew" posts, model comparison articles written from buyer perspective, rider journey stories. Platform: search-first (Google), then social once proof assets exist.' },
      { label: 'Creator partnerships', text: 'Future: partner with motorcycle riders who already have trust with the 18–35 commuter segment. Not influencers for reach — advisors for credibility. Unlocks after the core conversion path is validated and a proof package exists to give creators.' },
    ],
    outputs: ['Not wired', 'Unlocks at Stage 2', 'Requires proof assets'],
  },
  {
    title: 'Automation Modules',
    status: 'future',
    role: 'Planned capability — not wired in this prototype.',
    sections: [
      { label: 'Lead qualification bot', text: 'Future: qualify inbound inquiries from guide downloads, score buyer urgency and profile, route to human consultation or self-serve shortlist. Frees the consultant from repeat screening.' },
      { label: 'Proof collection system', text: 'Future: automated post-purchase follow-up sequence to capture buyer journey in their words. Turns each purchase into a proof asset with minimal manual effort.' },
    ],
    outputs: ['Not wired', 'Future automation scope'],
  },
];

function badge(status: Status): { label: string; bg: string; fg: string } {
  return status === 'active'
    ? { label: 'active', bg: '#dcfce7', fg: '#166534' }
    : { label: 'not wired', bg: '#f3f4f6', fg: '#6b7280' };
}

export function MotorMotoStrategyWorkflow() {
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
    <div style={{ minHeight: '100%', background: '#f4f6fb', color: '#1f2937', overflowY: 'auto' }}>
      <header style={{ background: '#1a1f36', color: '#fff', padding: '28px 32px', borderBottom: '5px solid #e85d26' }}>
        <div style={{ color: '#a0a8c8', fontSize: 11, fontWeight: 900, letterSpacing: '.12em', textTransform: 'uppercase', marginBottom: 8 }}>
          Strategy Workflow · MotorMoto · Sales-led motion
        </div>
        <h1 style={{ margin: 0, fontSize: 31, letterSpacing: '-.03em' }}>MotorMoto GTM Strategy</h1>
        <p style={{ maxWidth: 980, color: '#c8cde8', lineHeight: 1.55, margin: '10px 0 0' }}>
          Built from brand brief and GTM run data. Sales-led primary motion targeting first-time motorcycle buyers. No chat dump — each component is independently revisable.
        </p>
      </header>

      <main style={{ maxWidth: 1280, margin: '0 auto 80px', padding: 24 }}>
        <div style={{ background: '#fff', border: '1px solid #e2e5f0', borderRadius: 14, padding: 18, marginBottom: 18, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <div style={{ color: '#e85d26', fontSize: 12, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em' }}>Brand brief</div>
            <div style={{ marginTop: 4, fontSize: 17, fontWeight: 800 }}>MotorMoto — The trusted first motorcycle buying experience.</div>
            <div style={{ color: '#6b7280', fontSize: 13, marginTop: 5 }}>
              Voice: helpful motorcycle expert · Values: practicality, reliability, transparency, rider support
            </div>
            <div style={{ marginTop: 8, background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 8, padding: '7px 10px', fontSize: 12, color: '#92400e', maxWidth: 700 }}>
              Motion: sales-led primary — content-led secondary unlocks after first testimonials exist. Not wired modules are planned architecture only.
            </div>
          </div>
          <button
            onClick={trigger}
            style={{ background: '#1a1f36', color: '#fff', border: 0, borderRadius: 10, padding: '12px 16px', fontWeight: 850, cursor: 'pointer' }}
          >
            {started ? 'Re-run workflow' : 'Run workflow'}
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '310px minmax(0, 1fr)', gap: 18, alignItems: 'start' }}>
          <aside style={{ background: '#fff', border: '1px solid #e2e5f0', borderRadius: 16, overflow: 'hidden', position: 'sticky', top: 14 }}>
            <div style={{ background: '#f8f9fc', borderBottom: '1px solid #e2e5f0', padding: '14px 16px', fontWeight: 850 }}>Strategy modules</div>
            <div style={{ padding: 8 }}>
              {(started ? visible : modules).map((mod, idx) => {
                const mb = badge(mod.status);
                const isActive = mod === active;
                return (
                  <button
                    key={mod.title}
                    onClick={() => mod.status === 'active' && setActiveIndex(idx)}
                    disabled={mod.status === 'future'}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      border: `1px solid ${isActive ? '#1a1f36' : '#e8eaf0'}`,
                      background: mod.status === 'future' ? '#f9fafb' : (isActive ? '#f0f2ff' : '#fff'),
                      opacity: mod.status === 'future' ? 0.62 : 1,
                      borderRadius: 10,
                      padding: '10px 11px',
                      marginBottom: 7,
                      cursor: mod.status === 'future' ? 'not-allowed' : 'pointer',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontWeight: 850, fontSize: 13 }}>{idx + 1}. {mod.title}</span>
                      <span style={{ background: mb.bg, color: mb.fg, borderRadius: 999, padding: '2px 7px', fontSize: 10, fontWeight: 850 }}>{mb.label}</span>
                    </div>
                    <div style={{ color: '#6b7280', fontSize: 11, marginTop: 4, lineHeight: 1.35 }}>{mod.role}</div>
                  </button>
                );
              })}
            </div>
          </aside>

          <section style={{ background: '#fff', border: '1px solid #e2e5f0', borderRadius: 16, overflow: 'hidden', boxShadow: '0 12px 28px rgba(26,31,54,.07)' }}>
            <div style={{ background: '#f8f9fc', borderBottom: '1px solid #e2e5f0', padding: '16px 18px', display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <div>
                <div style={{ color: '#e85d26', fontSize: 11, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em' }}>Active module</div>
                <h2 style={{ margin: '4px 0 2px', fontSize: 22 }}>{active.title}</h2>
                <div style={{ color: '#6b7280', fontSize: 13 }}>{active.role}</div>
              </div>
              <span style={{ background: b.bg, color: b.fg, borderRadius: 999, padding: '5px 10px', fontSize: 11, fontWeight: 900, textTransform: 'uppercase' }}>{b.label}</span>
            </div>
            <div style={{ padding: 20 }}>
              <div style={{ display: 'grid', gap: 10 }}>
                {active.sections.map(section => (
                  <div key={section.label} style={{ border: '1px solid #ebedf5', borderRadius: 10, padding: '12px 13px', background: '#fcfcff' }}>
                    <div style={{ fontWeight: 850, marginBottom: 4, color: '#1a1f36' }}>{section.label}</div>
                    <div style={{ fontSize: 14, lineHeight: 1.52, color: '#374151' }}>{section.text}</div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 18 }}>
                <div style={{ color: '#e85d26', fontSize: 11, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 8 }}>Outputs</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {active.outputs.map(output => (
                    <span key={output} style={{ background: '#f4f6fb', border: '1px solid #e2e5f0', borderRadius: 999, padding: '6px 10px', fontSize: 12, fontWeight: 750 }}>{output}</span>
                  ))}
                </div>
              </div>
            </div>
          </section>
        </div>

        <div style={{ background: '#1a1f36', color: '#fff', borderRadius: 16, marginTop: 18, padding: 18 }}>
          <div style={{ color: '#a0a8c8', fontSize: 11, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 8 }}>CMO chat behavior</div>
          <div style={{ lineHeight: 1.55, color: '#c8cde8' }}>
            Chat should reply: "Built the MotorMoto Strategy Workflow — sales-led motion, 8 active modules, 5 work orders ready." then link here. The full strategy lives on this page. Chat only controls and links.
          </div>
        </div>
      </main>
    </div>
  );
}
