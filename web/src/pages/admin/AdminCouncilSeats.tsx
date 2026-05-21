import { useState } from 'react';

const MODELS = [
  'anthropic/claude-opus-4-7',
  'anthropic/claude-sonnet-4-6',
  'openai/gpt-4o',
  'openai/o3',
  'google/gemini-2.5-pro',
  'meta-llama/llama-3.3-70b-instruct',
  'x-ai/grok-3',
];

type Seat = {
  id: string;
  name: string;
  model: string;
  ideology: string;
  status: 'active' | 'vacant';
  ideologyOpen: boolean;
};

const INITIAL_SEATS: Seat[] = [
  { id: 'C1', name: 'Council Member 1', model: 'anthropic/claude-opus-4-7', ideology: 'Growth-first. Revenue and market movement above all else. Bias toward action and bold bets.', status: 'active', ideologyOpen: true },
  { id: 'C2', name: 'Council Member 2', model: 'openai/gpt-4o', ideology: 'Data and attribution first. Every recommendation must be measurable before commitment.', status: 'active', ideologyOpen: false },
  { id: 'C3', name: '', model: '', ideology: '', status: 'vacant', ideologyOpen: false },
  { id: 'C4', name: '', model: '', ideology: '', status: 'vacant', ideologyOpen: false },
  { id: 'C5', name: '', model: '', ideology: '', status: 'vacant', ideologyOpen: false },
];

function SeatCard({ seat, onChange }: { seat: Seat; onChange: (updated: Seat) => void }) {
  const [saved, setSaved] = useState(false);

  function save() {
    setSaved(true);
    setTimeout(() => setSaved(false), 1800);
  }

  return (
    <div className="seat-card">
      <div className="seat-card-hdr">
        <span className="seat-badge">{seat.id}</span>
        <span className={seat.status === 'active' ? 'chip-active' : 'chip-vacant'}>
          {seat.status === 'active' ? 'ACTIVE' : 'VACANT'}
        </span>
      </div>

      <div className="seat-field">
        <span className="seat-field-lbl">Display Name</span>
        <input
          className="seat-input"
          value={seat.name}
          placeholder="Recruit a council member"
          onChange={e => onChange({ ...seat, name: e.target.value })}
        />
      </div>

      <div className="seat-field">
        <span className="seat-field-lbl">Model</span>
        <select
          className="seat-select"
          value={seat.model}
          onChange={e => onChange({ ...seat, model: e.target.value })}
        >
          <option value="">— assign a model —</option>
          {MODELS.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
      </div>

      <div className="seat-field">
        <button
          className="ideology-toggle"
          onClick={() => onChange({ ...seat, ideologyOpen: !seat.ideologyOpen })}
        >
          <span className="seat-field-lbl" style={{ margin: 0 }}>Ideology</span>
          <span style={{ fontSize: 10 }}>{seat.ideologyOpen ? '▲' : '▼'}</span>
        </button>
        {seat.ideologyOpen && (
          <textarea
            className="ideology-area"
            placeholder="Define this member's strategic worldview, priors, and how they frame decisions."
            value={seat.ideology}
            onChange={e => onChange({ ...seat, ideology: e.target.value })}
          />
        )}
      </div>

      <div className="seat-footer">
        <div className="status-toggle">
          <button
            className={`stgl-btn${seat.status === 'vacant' ? ' sel-vacant' : ''}`}
            onClick={() => onChange({ ...seat, status: 'vacant' })}
          >
            Vacant
          </button>
          <button
            className={`stgl-btn${seat.status === 'active' ? ' sel-active' : ''}`}
            onClick={() => onChange({ ...seat, status: 'active' })}
          >
            Active
          </button>
        </div>
        <button className="btn-save" onClick={save}>{saved ? 'Saved' : 'Save'}</button>
      </div>
    </div>
  );
}

export function AdminCouncilSeats() {
  const [seats, setSeats] = useState<Seat[]>(INITIAL_SEATS);

  function updateSeat(updated: Seat) {
    setSeats(prev => prev.map(s => s.id === updated.id ? updated : s));
  }

  const activeCount = seats.filter(s => s.status === 'active').length;
  const vacantCount = seats.filter(s => s.status === 'vacant').length;

  return (
    <div>
      <div className="admin-section-title">Council Seats</div>
      <div className="admin-section-sub">5 seats · assign an LLM and ideology to each. Active seats are called when @council is invoked in CMO. Vacant seats are skipped.</div>

      <div className="settings-group">
        <div className="settings-group-label">
          <span>Seats</span>
          <span style={{ fontSize: 11, color: 'var(--muted-stone)', fontFamily: 'SF Mono, Fira Mono, monospace', fontWeight: 400 }}>
            {activeCount} active · {vacantCount} vacant
          </span>
        </div>
        <div className="seat-grid" style={{ paddingTop: 16 }}>
          {seats.map(seat => (
            <SeatCard key={seat.id} seat={seat} onChange={updateSeat} />
          ))}
        </div>
      </div>
    </div>
  );
}
