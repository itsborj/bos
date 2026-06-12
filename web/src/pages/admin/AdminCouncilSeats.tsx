import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { CouncilSeat, CouncilSeatUpdate, ProviderModelLive } from '../../api/types';

type SeatDraft = CouncilSeat & {
  dirty: boolean;
  saving: boolean;
  saved: boolean;
  ideologyOpen: boolean;
  error: string | null;
};

type ModelsByProvider = Record<string, ProviderModelLive[]>;

function buildModelsByProvider(models: ProviderModelLive[]): ModelsByProvider {
  const out: ModelsByProvider = {};
  for (const m of models) {
    if (!out[m.provider]) out[m.provider] = [];
    out[m.provider].push(m);
  }
  return out;
}

function SeatCard({
  seat,
  modelsByProvider,
  onChange,
}: {
  seat: SeatDraft;
  modelsByProvider: ModelsByProvider;
  onChange: (s: SeatDraft) => void;
}) {
  const providers = Object.keys(modelsByProvider);
  const modelsForProvider = modelsByProvider[seat.provider] ?? [];
  const freeModels = modelsForProvider.filter(m => m.is_free);
  const paidModels = modelsForProvider.filter(m => !m.is_free);
  const selectedModel = modelsForProvider.find(m => m.model_id === seat.model_id);

  async function save() {
    onChange({ ...seat, saving: true, error: null });
    try {
      const update: CouncilSeatUpdate = {
        display_name: seat.display_name,
        status: seat.status,
        provider: seat.provider,
        model_id: seat.model_id || null,
        ideology: seat.ideology || null,
      };
      await api.putCouncilSeat(seat.seat_id, update);
      onChange({ ...seat, saving: false, dirty: false, saved: true, error: null });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Save failed';
      onChange({ ...seat, saving: false, error: msg });
    }
  }

  function set(patch: Partial<SeatDraft>) {
    onChange({ ...seat, ...patch, dirty: true, saved: false });
  }

  return (
    <div className="seat-card">
      <div className="seat-card-hdr">
        <span className="seat-badge">{seat.seat_id.toUpperCase()}</span>
        <span className={seat.status === 'active' ? 'chip-active' : 'chip-vacant'}>
          {seat.status === 'active' ? 'ACTIVE' : 'VACANT'}
        </span>
      </div>

      <div className="seat-field">
        <span className="seat-field-lbl">Display Name</span>
        <input
          className="seat-input"
          value={seat.display_name}
          placeholder="Recruit a council member"
          onChange={e => set({ display_name: e.target.value })}
        />
      </div>

      <div className="seat-field">
        <span className="seat-field-lbl">Provider</span>
        <select
          className="seat-select"
          value={seat.provider}
          onChange={e => set({ provider: e.target.value, model_id: null })}
        >
          {providers.map(p => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </div>

      <div className="seat-field">
        <span className="seat-field-lbl">
          Model
          {selectedModel && (() => {
            const isOpenRouter = seat.provider === 'openrouter';
            const label = isOpenRouter
              ? (selectedModel.is_free ? 'FREE' : 'PAID')
              : (selectedModel.is_free ? 'platform key' : 'BYOK');
            const color = selectedModel.is_free ? 'var(--green, #22c55e)' : 'var(--amber, #f59e0b)';
            return (
              <span style={{ marginLeft: 6, fontSize: 10, fontFamily: 'monospace', color }}>
                {label}
              </span>
            );
          })()}
        </span>
        <select
          className="seat-select"
          value={seat.model_id ?? ''}
          onChange={e => set({ model_id: e.target.value || null })}
        >
          <option value="">— assign a model —</option>
          {freeModels.length > 0 && (
            <optgroup label={seat.provider === 'openrouter' ? 'Free' : 'Platform key'}>
              {freeModels.map(m => (
                <option key={m.model_id} value={m.model_id}>{m.name || m.model_id}</option>
              ))}
            </optgroup>
          )}
          {paidModels.length > 0 && (
            <optgroup label={seat.provider === 'openrouter' ? 'Paid' : 'BYOK'}>
              {paidModels.map(m => (
                <option key={m.model_id} value={m.model_id}>{m.name || m.model_id}</option>
              ))}
            </optgroup>
          )}
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
            value={seat.ideology ?? ''}
            onChange={e => set({ ideology: e.target.value || null })}
          />
        )}
      </div>

      {seat.config_error && (
        <div style={{ color: '#92400e', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 6, padding: '6px 8px', fontSize: 12, marginBottom: 8 }}>
          Seat config was repaired with safe defaults: {seat.config_error}. Save this seat to overwrite the bad config.
        </div>
      )}

      {seat.error && (
        <div style={{ color: 'var(--red, #ef4444)', fontSize: 12, marginBottom: 8 }}>{seat.error}</div>
      )}

      <div className="seat-footer">
        <div className="status-toggle">
          <button
            className={`stgl-btn${seat.status === 'vacant' ? ' sel-vacant' : ''}`}
            onClick={() => set({ status: 'vacant' })}
          >
            Vacant
          </button>
          <button
            className={`stgl-btn${seat.status === 'active' ? ' sel-active' : ''}`}
            onClick={() => set({ status: 'active' })}
          >
            Active
          </button>
        </div>
        <button
          className="btn-save"
          onClick={save}
          disabled={seat.saving || !seat.dirty}
          style={{ opacity: !seat.dirty && !seat.saving ? 0.5 : 1 }}
        >
          {seat.saving ? 'Saving…' : seat.saved ? 'Saved ✓' : 'Save'}
        </button>
      </div>
    </div>
  );
}

export function AdminCouncilSeats() {
  const [seats, setSeats] = useState<SeatDraft[]>([]);
  const [modelsByProvider, setModelsByProvider] = useState<ModelsByProvider>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.getCouncilSeats(), api.getAvailableModels()])
      .then(([rawSeats, { models }]) => {
        setModelsByProvider(buildModelsByProvider(models));
        setSeats(rawSeats.map(s => ({
          ...s,
          dirty: false,
          saving: false,
          saved: false,
          ideologyOpen: s.status === 'active',
          error: null,
        })));
      })
      .catch(e => setLoadError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false));
  }, []);

  function updateSeat(updated: SeatDraft) {
    setSeats(prev => prev.map(s => s.seat_id === updated.seat_id ? updated : s));
  }

  const activeCount = seats.filter(s => s.status === 'active').length;
  const vacantCount = seats.filter(s => s.status === 'vacant').length;

  return (
    <div>
      <div className="admin-section-title">Council Seats</div>
      <div className="admin-section-sub">
        5 seats · assign a provider, model, and ideology to each. Active seats deliberate when <code>@council</code> is invoked in CMO. Vacant seats are skipped.
      </div>

      {loading && <div style={{ padding: '24px 0', color: 'var(--muted-stone)' }}>Loading seats…</div>}
      {loadError && <div style={{ padding: '12px 0', color: 'var(--red, #ef4444)' }}>{loadError}</div>}

      {!loading && !loadError && (
        <div className="settings-group">
          <div className="settings-group-label">
            <span>Seats</span>
            <span style={{ fontSize: 11, color: 'var(--muted-stone)', fontFamily: 'SF Mono, Fira Mono, monospace', fontWeight: 400 }}>
              {activeCount} active · {vacantCount} vacant
            </span>
          </div>
          <div className="seat-grid" style={{ paddingTop: 16 }}>
            {seats.map(seat => (
              <SeatCard
                key={seat.seat_id}
                seat={seat}
                modelsByProvider={modelsByProvider}
                onChange={updateSeat}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
