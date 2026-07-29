import { Link } from 'react-router-dom';

const sharedProblems = [
  'strategy gets separated from execution',
  'creative drifts from the original objective',
  'approvals create drag instead of momentum',
  'analytics arrive too late or too isolated to guide the next decision',
  'teams spend more time coordinating than advancing the campaign',
];

const inHouseProblems = [
  'slow revisions',
  'delayed approvals',
  'scattered updates across meetings, chats, decks, and folders',
  'reporting that does not translate cleanly into next actions',
  'decisions made with incomplete context',
];

const agencyProblems = [
  'fragmented account knowledge',
  'more time spent coordinating than compounding insight',
  'reduced margin from operational overhead',
  'teams re-explaining campaign context across staff changes',
  'growth creating more complexity instead of more leverage',
];

export function About() {
  return (
    <div className="about-page">
      <section className="about-hero">
        <h1>Most marketing bottlenecks are not idea problems. They are coordination problems.</h1>
        <p>
          A campaign does not move from idea to outcome on inspiration alone. It has to pass through writers, designers, channel specialists, approvals, and analytics before the team can decide what to do next.
        </p>
        <p>
          Every handoff adds delay. Every transition risks context loss. Every disconnected system makes the feedback loop harder to complete.
        </p>
        <p>
          Klaroha is built for teams that need the campaign to stay coherent from idea to execution to feedback to next action.
        </p>
      </section>

      <section className="about-frame-card">
        <div>
          <h2>The real slowdown happens between functions.</h2>
        </div>
        <div>
          <p>
            Before AI, and still today, most marketing teams do not struggle because they lack activity. They struggle because campaign execution depends on too many disconnected steps.
          </p>
          <p>
            Writers shape the message. Designers turn it into creative. Paid and organic specialists adapt it for channels. Then the team waits for analytics to understand performance and decide the next move.
          </p>
          <p>
            The problem is not that these roles exist. The problem is that the work between them is often fragmented.
          </p>
          <ul className="about-problem-list">
            {sharedProblems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p className="about-emphasis">The cost is not just slower work. It is weaker campaign judgment.</p>
        </div>
      </section>

      <section className="about-transition">
        <h2>When the campaign stops being the source of truth, the work gets scattered.</h2>
        <p>
          Most teams can produce activity. What they struggle to preserve is continuity.
        </p>
        <p>
          As work moves from one person to another, one specialist to another, one system to another, the campaign becomes harder to follow. The original objective gets thinner. The context has to be rebuilt. The reasoning behind decisions becomes harder to recover.
        </p>
        <p>
          And every staff-to-staff transition becomes another chance for the campaign to lose coherence.
        </p>
      </section>

      <section className="about-audience-fork">
        <article className="about-audience">
          <div className="about-eyebrow">In-house marketing teams</div>
          <h2>Too much momentum gets lost between idea and execution.</h2>
          <p>
            In-house teams are often not short on effort. They are short on clean movement across the campaign loop.
          </p>
          <p>
            Work gets passed between content, design, channel execution, approvals, and reporting. But instead of building momentum, each stage creates more back-and-forth.
          </p>
          <ul className="about-audience-list">
            {inHouseProblems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p className="about-emphasis">The real cost is not just slower production. It is slower decision-making.</p>
          <p>
            Klaroha is for in-house teams that need less coordination drag between message, execution, feedback, and next move.
          </p>
        </article>

        <article className="about-audience about-audience-dark">
          <div className="about-eyebrow">Agencies</div>
          <h2>Scale gets messy when every brand and channel runs through a different operating rhythm.</h2>
          <p>
            Agencies do not just manage more campaigns. They manage more handoffs, more stakeholders, more brands, and more channel complexity.
          </p>
          <p>
            Every client can become a different workflow. Every channel can become a different reporting language. And every account transition risks losing context that lived in one person, one thread, or one deck.
          </p>
          <ul className="about-audience-list">
            {agencyProblems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p className="about-emphasis">The problem is not volume alone. It is fragmentation at scale.</p>
          <p>
            Klaroha is for agencies that need one coherent operating model across multi-brand, omni-channel campaign work.
          </p>
        </article>
      </section>

      <section className="about-closing">
        <h2>The problem is not making more marketing. The problem is keeping the campaign coherent as work moves.</h2>
        <p>
          Klaroha exists for teams that are tired of losing time and clarity in the gaps between strategy, creative, channels, approvals, analytics, and staff transitions.
        </p>
        <p>
          Because when the campaign remains the source of truth, teams do not just move faster.
        </p>
        <p className="about-emphasis">They make better decisions.</p>
        <div className="about-cta">
          <div>
            <p className="about-cta-line">Bring the campaign back to the center of the work.</p>
          </div>
          <div className="about-actions">
            <Link className="btn btn-dark" to="/cmo">See Klaroha</Link>
            <Link className="btn btn-secondary" to="/admin/campaigns">Start with your campaign</Link>
          </div>
        </div>
      </section>
    </div>
  );
}
