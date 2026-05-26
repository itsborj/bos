import { useState } from 'react';

type WpStatus = 'watching' | 'warning' | 'triggered';

type Watchpoint = {
  id: string;
  metric: string;
  metric_label: string;
  brand: string;
  obj: string;
  condition: 'rises above' | 'falls below';
  trigger_at: number;
  warn_at: number | null;
  unit: string;
  surface: string;
  current: number | null;
  last_checked: string;
  status: WpStatus;
};

const INITIAL_WPS: Watchpoint[] = [
  {
    id: 'wp1',
    metric: 'send_frequency',
    metric_label: 'Send frequency / week',
    brand: 'Klaroha',
    obj: 'Generate $40k pipeline from dormant prospects · Q2',
    condition: 'rises above',
    trigger_at: 4.8,
    warn_at: 4.5,
    unit: '/wk',
    surface: 'signal_update',
    current: 4.2,
    last_checked: '2h ago',
    status: 'watching',
  },
  {
    id: 'wp2',
    metric: 'reply_rate',
    metric_label: 'Reply rate',
    brand: 'Klaroha',
    obj: 'Generate $40k pipeline from dormant prospects · Q2',
    condition: 'falls below',
    trigger_at: 10,
    warn_at: 15,
    unit: '%',
    surface: 'decision_brief',
    current: null,
    last_checked: 'no data yet',
    status: 'watching',
  },
];

type WpForm = {
  metric: string;
  brand: string;
  obj: string;
  condition: 'rises above' | 'falls below';
  trigger_at: string;
  warn_at: string;
  surface: string;
};

const EMPTY_FORM: WpForm = {
  metric: 'send_frequency',
  brand: 'Klaroha',
  obj: '',
  condition: 'rises above',
  trigger_at: '',
  warn_at: '',
  surface: 'signal_update',
};

const METRIC_LABELS: Record<string, string> = {
  send_frequency: 'Send frequency / week',
  reply_rate: 'Reply rate',
  ctr: 'CTR',
  open_rate: 'Open rate',
  bounce_rate: 'Bounce rate',
};

const METRIC_UNITS: Record<string, string> = {
  send_frequency: '/wk',
  reply_rate: '%',
  ctr: '%',
  open_rate: '%',
  bounce_rate: '%',
};

function WpRow({ wp, onEdit }: { wp: Watchpoint; onEdit: () => void }) {
  const currentLine = wp.current !== null
    ? `Current: ${wp.current}${wp.unit} · last checked ${wp.last_checked}`
    : `No data yet · ${wp.last_checked}`;
  const threshLine = `Fires when ${wp.condition} ${wp.trigger_at}${wp.unit}${wp.warn_at ? ` · warn at ${wp.warn_at}${wp.unit}` : ''}`;

  return (
    <div className="settings-row">
      <div className="settings-row-info">
        <div className="settings-row-name" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {wp.metric_label}
          <span className={`wp-state ${wp.status}`}>{wp.status}</span>
        </div>
        <div className="settings-row-desc">{wp.brand} · {wp.obj}</div>
        <div className="settings-row-desc" style={{ marginTop: 3, fontSize: 11, fontFamily: 'SF Mono, Fira Mono, monospace' }}>{threshLine}</div>
        <div className="settings-row-desc" style={{ marginTop: 2 }}>{currentLine}</div>
      </div>
      <div className="settings-row-action">
        <button className="action-link" onClick={onEdit}>Edit →</button>
      </div>
    </div>
  );
}

export function AdminWatchpoints() {
  const [watchpoints, setWatchpoints] = useState<Watchpoint[]>(INITIAL_WPS);
  const [formOpen, setFormOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<WpForm>(EMPTY_FORM);

  function openAdd() {
    setEditId(null);
    setForm(EMPTY_FORM);
    setFormOpen(true);
  }

  function openEdit(wp: Watchpoint) {
    setEditId(wp.id);
    setForm({
      metric: wp.metric,
      brand: wp.brand,
      obj: wp.obj,
      condition: wp.condition,
      trigger_at: String(wp.trigger_at),
      warn_at: wp.warn_at !== null ? String(wp.warn_at) : '',
      surface: wp.surface,
    });
    setFormOpen(true);
  }

  function save() {
    const unit = METRIC_UNITS[form.metric] || '';
    if (editId) {
      setWatchpoints(prev => prev.map(w =>
        w.id === editId ? {
          ...w,
          metric: form.metric,
          metric_label: METRIC_LABELS[form.metric] || form.metric,
          brand: form.brand,
          obj: form.obj,
          condition: form.condition,
          trigger_at: parseFloat(form.trigger_at) || 0,
          warn_at: form.warn_at ? parseFloat(form.warn_at) : null,
          unit,
          surface: form.surface,
        } : w
      ));
    } else {
      const newWp: Watchpoint = {
        id: `wp${Date.now()}`,
        metric: form.metric,
        metric_label: METRIC_LABELS[form.metric] || form.metric,
        brand: form.brand,
        obj: form.obj,
        condition: form.condition,
        trigger_at: parseFloat(form.trigger_at) || 0,
        warn_at: form.warn_at ? parseFloat(form.warn_at) : null,
        unit,
        surface: form.surface,
        current: null,
        last_checked: 'never',
        status: 'watching',
      };
      setWatchpoints(prev => [...prev, newWp]);
    }
    setFormOpen(false);
    setEditId(null);
  }

  function del() {
    if (editId) setWatchpoints(prev => prev.filter(w => w.id !== editId));
    setFormOpen(false);
    setEditId(null);
  }

  return (
    <div>
      <div className="admin-section-title">Watchpoints</div>
      <div className="admin-section-sub">Configure when BOS is allowed to interrupt Stream. Watchpoints are not an analytics dashboard — they are objective-bound attention rules that turn external signals into Stream cards only when judgment may be needed.</div>

      <div className="hb-card" style={{ marginBottom: 28 }}>
        <div className="hb-row">
          <div className="hb-label">Operator promise</div>
          <div className="hb-body">If a metric is still inside its safe range, BOS keeps watching silently. If it approaches or crosses a threshold, Stream receives a signal_update or decision_brief with why-now, evidence, and a recommended next step.</div>
        </div>
        <div className="hb-row">
          <div className="hb-label">Use watchpoints for</div>
          <div className="hb-body">Objective-critical signals: reply rate drop, send-frequency fatigue, list quality deterioration, bounce risk, or performance thresholds tied to a committed operating goal.</div>
        </div>
        <div className="hb-row">
          <div className="hb-label">Do not use for</div>
          <div className="hb-body">Vanity monitoring, dashboards, curiosity metrics, or alerts that do not create a decision. If there is no likely operator action, it should not become a Watchpoint.</div>
        </div>
      </div>

      <div className="settings-group">
        <div className="settings-group-label">
          <span>Active watchpoints</span>
          {!formOpen && <button className="action-link" onClick={openAdd}>+ Add watchpoint</button>}
        </div>

        {formOpen && (
          <div className="wp-form" style={{ marginTop: 16 }}>
            <div className="wp-form-title">{editId ? 'Edit watchpoint' : 'New watchpoint'}</div>
            <div style={{ fontSize: 12, color: 'var(--muted-stone)', lineHeight: 1.5, marginBottom: 16 }}>
              Define the signal, the safe range, and exactly how it should surface in Stream. Every Watchpoint must attach to an objective.
            </div>
            <div className="wp-form-grid">
              <div className="wp-field">
                <label>Metric</label>
                <select value={form.metric} onChange={e => setForm(f => ({ ...f, metric: e.target.value }))}>
                  <option value="send_frequency">Send frequency / week</option>
                  <option value="reply_rate">Reply rate</option>
                  <option value="ctr">CTR</option>
                  <option value="open_rate">Open rate</option>
                  <option value="bounce_rate">Bounce rate</option>
                </select>
              </div>
              <div className="wp-field">
                <label>Brand</label>
                <input type="text" value={form.brand} placeholder="Brand name" onChange={e => setForm(f => ({ ...f, brand: e.target.value }))} />
              </div>
              <div className="wp-field">
                <label>Condition</label>
                <select value={form.condition} onChange={e => setForm(f => ({ ...f, condition: e.target.value as 'rises above' | 'falls below' }))}>
                  <option value="rises above">Rises above</option>
                  <option value="falls below">Falls below</option>
                </select>
              </div>
              <div className="wp-field">
                <label>Escalation threshold</label>
                <input type="number" step="0.1" placeholder="e.g. 4.8" value={form.trigger_at} onChange={e => setForm(f => ({ ...f, trigger_at: e.target.value }))} />
                <span className="wp-field-hint">Signal update card fires when this is crossed</span>
              </div>
              <div className="wp-field">
                <label>Warning threshold <span style={{ fontWeight: 400, color: 'var(--muted-stone)' }}>(optional)</span></label>
                <input type="number" step="0.1" placeholder="e.g. 4.5" value={form.warn_at} onChange={e => setForm(f => ({ ...f, warn_at: e.target.value }))} />
                <span className="wp-field-hint">Early warning before escalation fires</span>
              </div>
              <div className="wp-field">
                <label>Stream surface rule</label>
                <select value={form.surface} onChange={e => setForm(f => ({ ...f, surface: e.target.value }))}>
                  <option value="signal_update">Surface signal_update card</option>
                  <option value="decision_brief">Escalate to decision_brief</option>
                </select>
                <span className="wp-field-hint">Choose the lightest interruption that creates the right decision</span>
              </div>
              <div className="wp-field full">
                <label>Objective</label>
                <input type="text" placeholder="Attach to an active objective" value={form.obj} onChange={e => setForm(f => ({ ...f, obj: e.target.value }))} />
                <span className="wp-field-hint">Shown as context when the card surfaces in Stream</span>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
              <button className="btn btn-primary" onClick={save}>Save watchpoint</button>
              {editId && (
                <button className="btn btn-ghost" style={{ color: 'var(--oxblood)', borderColor: 'var(--oxblood)' }} onClick={del}>Delete</button>
              )}
              <button className="btn btn-ghost" onClick={() => { setFormOpen(false); setEditId(null); }}>Cancel</button>
            </div>
          </div>
        )}

        {watchpoints.map(wp => (
          <WpRow key={wp.id} wp={wp} onEdit={() => openEdit(wp)} />
        ))}
        {watchpoints.length === 0 && !formOpen && (
          <div style={{ padding: '16px 0', color: 'var(--muted-stone)', fontSize: 13 }}>No watchpoints configured yet.</div>
        )}
      </div>

      <div className="settings-group">
        <div className="settings-group-label">States</div>
        <div style={{ padding: '14px 0', display: 'flex', gap: 28, flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="wp-state watching">watching</span>
            <span style={{ fontSize: 12, color: 'var(--muted-stone)' }}>Safe range · no action needed</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="wp-state warning">warning</span>
            <span style={{ fontSize: 12, color: 'var(--muted-stone)' }}>Approaching threshold</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="wp-state triggered">triggered</span>
            <span style={{ fontSize: 12, color: 'var(--muted-stone)' }}>Threshold crossed — signal_update card in Stream</span>
          </div>
        </div>
      </div>
    </div>
  );
}
