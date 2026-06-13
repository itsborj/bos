import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { BookingResponse, CalendarPageResponse, SocialConnectionResponse } from '../../api/types';

const TIMEZONES = [
  // Africa
  'Africa/Abidjan','Africa/Accra','Africa/Addis_Ababa','Africa/Algiers','Africa/Cairo',
  'Africa/Casablanca','Africa/Johannesburg','Africa/Lagos','Africa/Nairobi','Africa/Tunis',
  // Americas
  'America/Anchorage','America/Argentina/Buenos_Aires','America/Bogota','America/Chicago',
  'America/Denver','America/Halifax','America/Lima','America/Los_Angeles','America/Mexico_City',
  'America/New_York','America/Phoenix','America/Santiago','America/Sao_Paulo','America/Toronto',
  'America/Vancouver',
  // Asia
  'Asia/Almaty','Asia/Baghdad','Asia/Baku','Asia/Bangkok','Asia/Colombo','Asia/Dhaka',
  'Asia/Dubai','Asia/Ho_Chi_Minh','Asia/Hong_Kong','Asia/Jakarta','Asia/Karachi',
  'Asia/Kathmandu','Asia/Kolkata','Asia/Kuala_Lumpur','Asia/Kuwait','Asia/Manila',
  'Asia/Muscat','Asia/Riyadh','Asia/Seoul','Asia/Shanghai','Asia/Singapore',
  'Asia/Taipei','Asia/Tashkent','Asia/Tehran','Asia/Tokyo','Asia/Yangon',
  // Atlantic / Pacific
  'Atlantic/Azores','Atlantic/Cape_Verde','Atlantic/Reykjavik',
  // Australia / Pacific
  'Australia/Adelaide','Australia/Brisbane','Australia/Melbourne','Australia/Perth','Australia/Sydney',
  'Pacific/Auckland','Pacific/Fiji','Pacific/Guam','Pacific/Honolulu','Pacific/Midway',
  // Europe
  'Europe/Amsterdam','Europe/Athens','Europe/Berlin','Europe/Brussels','Europe/Bucharest',
  'Europe/Budapest','Europe/Copenhagen','Europe/Dublin','Europe/Helsinki','Europe/Istanbul',
  'Europe/Kiev','Europe/Lisbon','Europe/London','Europe/Madrid','Europe/Moscow',
  'Europe/Oslo','Europe/Paris','Europe/Prague','Europe/Rome','Europe/Stockholm',
  'Europe/Vienna','Europe/Warsaw','Europe/Zurich',
  // UTC
  'UTC',
];

function browserTz(): string {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone; } catch { return 'UTC'; }
}

function tzLabel(tz: string): string {
  try {
    const now = new Date();
    const offset = new Intl.DateTimeFormat('en-US', { timeZone: tz, timeZoneName: 'shortOffset' })
      .formatToParts(now).find(p => p.type === 'timeZoneName')?.value ?? '';
    return `${tz.replace(/_/g, ' ')} (${offset})`;
  } catch { return tz; }
}

function fmt(iso: string) {
  return new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

type CreateForm = {
  brand_id: string;
  connection_id: string;
  title: string;
  slug: string;
  description: string;
  duration_minutes: number;
  timezone: string;
};

export function AdminCalendar() {
  const [pages, setPages] = useState<CalendarPageResponse[]>([]);
  const [bookings, setBookings] = useState<BookingResponse[]>([]);
  const [connections, setConnections] = useState<SocialConnectionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [expandedPage, setExpandedPage] = useState<string | null>(null);
  const [form, setForm] = useState<CreateForm>({
    brand_id: '',
    connection_id: '',
    title: '',
    slug: '',
    description: '',
    duration_minutes: 30,
    timezone: browserTz(),
  });

  async function load() {
    setLoading(true);
    setError('');
    try {
      const [pg, bk, cn] = await Promise.all([
        api.listCalendarPages(),
        api.listBookings(),
        api.listSocialConnections(),
      ]);
      setPages(pg);
      setBookings(bk);
      setConnections(cn.filter(c => c.platform === 'google_calendar'));
    } catch {
      setError('Could not load calendar data.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function handleFormChange(field: keyof CreateForm, value: string | number) {
    setForm(prev => ({ ...prev, [field]: value }));
    if (field === 'title' && typeof value === 'string') {
      setForm(prev => ({
        ...prev,
        title: value,
        slug: prev.slug || value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
      }));
    }
  }

  async function handleCreate() {
    if (!form.title || !form.slug) return;
    setSaving(true);
    setSaveError('');
    try {
      await api.createCalendarPage({
        brand_id: form.brand_id || undefined,
        connection_id: form.connection_id || undefined,
        slug: form.slug,
        title: form.title,
        description: form.description || undefined,
        duration_minutes: form.duration_minutes,
        timezone: form.timezone,
        is_active: true,
      });
      setCreating(false);
      setForm({ brand_id: '', connection_id: '', title: '', slug: '', description: '', duration_minutes: 30, timezone: 'America/New_York' });
      await load();
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : 'Failed to create page');
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActive(page: CalendarPageResponse) {
    await api.updateCalendarPage(page.id, { is_active: !page.is_active }).catch(() => {});
    await load();
  }

  async function handleDelete(pageId: string, title: string) {
    if (!window.confirm(`Delete booking page "${title}"? All bookings will be kept but the page will be removed.`)) return;
    await api.deleteCalendarPage(pageId).catch(() => {});
    await load();
  }

  async function handleCancelBooking(bookingId: string) {
    if (!window.confirm('Cancel this booking?')) return;
    await api.cancelBooking(bookingId).catch(() => {});
    await load();
  }

  if (loading) {
    return <div className="admin-page"><div className="loading-full"><span className="spinner" /></div></div>;
  }

  const calConnections = connections;

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">Booking Pages</div>
          <div className="admin-page-subtitle">
            Client booking links powered by Google Calendar. Content and publish scheduling will move to the campaign calendar.
          </div>
        </div>
        <button className="btn btn-dark btn-sm" onClick={() => { setCreating(true); setSaveError(''); }}>
          + New booking page
        </button>
      </div>

      {error && (
        <div className="admin-card" style={{ borderColor: 'var(--error)', color: 'var(--error)', fontSize: 13 }}>{error}</div>
      )}

      {calConnections.length === 0 && !error && (
        <div className="admin-card" style={{ background: 'var(--bg2)', borderColor: 'var(--border)', marginBottom: 16 }}>
          <div style={{ fontSize: 13, color: 'var(--text2)' }}>
            No Google Calendar accounts connected. Open a brand's <strong>Integrations</strong> tab and connect Google Calendar to enable live availability checking.
          </div>
        </div>
      )}

      {creating && (
        <div className="admin-card" style={{ marginBottom: 20 }}>
          <div style={{ fontWeight: 800, fontSize: 15, marginBottom: 16 }}>New booking page</div>
          <div style={{ display: 'grid', gap: 14 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>Title</label>
              <input
                className="input"
                placeholder="e.g. 30-min intro call"
                value={form.title}
                onChange={e => handleFormChange('title', e.target.value)}
                style={{ width: '100%' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>Slug (URL path)</label>
              <input
                className="input"
                placeholder="e.g. intro-call"
                value={form.slug}
                onChange={e => handleFormChange('slug', e.target.value)}
                style={{ width: '100%', fontFamily: 'monospace' }}
              />
              <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 4 }}>
                Public URL: /api/calendar/book/{form.slug || 'your-slug'}
              </div>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>Description (optional)</label>
              <input
                className="input"
                placeholder="What is this call for?"
                value={form.description}
                onChange={e => handleFormChange('description', e.target.value)}
                style={{ width: '100%' }}
              />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>Duration (minutes)</label>
                <input
                  className="input"
                  type="number"
                  min={15}
                  step={15}
                  value={form.duration_minutes}
                  onChange={e => handleFormChange('duration_minutes', parseInt(e.target.value) || 30)}
                  style={{ width: '100%' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>Timezone</label>
                <select
                  className="input"
                  value={form.timezone}
                  onChange={e => handleFormChange('timezone', e.target.value)}
                  style={{ width: '100%' }}
                >
                  {[browserTz(), ...TIMEZONES.filter(t => t !== browserTz())]
                    .map(tz => <option key={tz} value={tz}>{tzLabel(tz)}</option>)}
                </select>
              </div>
            </div>
            {calConnections.length > 0 && (
              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>Google Calendar account (for live availability)</label>
                <select
                  className="input"
                  value={form.connection_id}
                  onChange={e => {
                    const conn = calConnections.find(c => c.id === e.target.value);
                    setForm(prev => ({ ...prev, connection_id: e.target.value, brand_id: conn?.brand_id || prev.brand_id }));
                  }}
                  style={{ width: '100%' }}
                >
                  <option value="">None (no live calendar check)</option>
                  {calConnections.map(c => (
                    <option key={c.id} value={c.id}>{c.page_name || c.page_id}</option>
                  ))}
                </select>
              </div>
            )}
          </div>
          {saveError && <div style={{ color: 'var(--error)', fontSize: 13, marginTop: 12 }}>{saveError}</div>}
          <div style={{ display: 'flex', gap: 10, marginTop: 18, justifyContent: 'flex-end' }}>
            <button className="btn btn-ghost" onClick={() => setCreating(false)}>Cancel</button>
            <button className="btn btn-dark" onClick={handleCreate} disabled={saving || !form.title || !form.slug}>
              {saving ? 'Creating…' : 'Create page'}
            </button>
          </div>
        </div>
      )}

      {pages.length === 0 && !creating ? (
        <div className="admin-card">
          <div className="empty-state">
            <div className="empty-state-icon">📅</div>
            <div className="empty-state-title">No booking pages yet</div>
            <div className="empty-state-text">Create a booking page to let clients schedule calls. Connect Google Calendar first for live availability.</div>
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 12 }}>
          {pages.map(page => {
            const upcoming = bookings.filter(b => b.status === 'confirmed' && new Date(b.start_at) > new Date());
            const isExpanded = expandedPage === page.id;
            return (
              <div key={page.id} className="admin-card" style={{ margin: 0 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                      <div style={{ fontWeight: 850, fontSize: 15 }}>{page.title}</div>
                      <span className={`badge badge-${page.is_active ? 'success' : 'muted'}`}>
                        {page.is_active ? 'Active' : 'Inactive'}
                      </span>
                      {page.connection_id && (
                        <span className="badge badge-info">Calendar linked</span>
                      )}
                    </div>
                    {page.description && (
                      <div style={{ color: 'var(--text2)', fontSize: 13, marginBottom: 6 }}>{page.description}</div>
                    )}
                    <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text2)' }}>
                      <span>{page.duration_minutes} min</span>
                      <span>{page.timezone}</span>
                      <span style={{ fontFamily: 'monospace' }}>/book/{page.slug}</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'flex-end' }}>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <a
                        href={page.embed_url}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-secondary"
                        style={{ fontSize: 12 }}
                      >
                        Preview
                      </a>
                      <button
                        className="btn btn-ghost"
                        style={{ fontSize: 12 }}
                        onClick={() => { navigator.clipboard.writeText(page.embed_url); }}
                      >
                        Copy link
                      </button>
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button
                        className="btn btn-ghost"
                        style={{ fontSize: 11 }}
                        onClick={() => handleToggleActive(page)}
                      >
                        {page.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                      <button
                        className="btn btn-ghost"
                        style={{ fontSize: 11, color: '#dc2626' }}
                        onClick={() => handleDelete(page.id, page.title)}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>

                <div
                  style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 10, cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                  onClick={() => setExpandedPage(isExpanded ? null : page.id)}
                >
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text2)' }}>
                    Bookings
                  </span>
                  <span style={{ fontSize: 11, color: 'var(--text2)' }}>{isExpanded ? '▲ hide' : '▼ show'}</span>
                </div>

                {isExpanded && (
                  <div style={{ marginTop: 10 }}>
                    {upcoming.length === 0 ? (
                      <div style={{ fontSize: 13, color: 'var(--text2)', fontStyle: 'italic' }}>No upcoming bookings.</div>
                    ) : (
                      <div style={{ display: 'grid', gap: 8 }}>
                        {upcoming.map(b => (
                          <div key={b.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 13, padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                            <div>
                              <div style={{ fontWeight: 600 }}>{b.attendee_name}</div>
                              <div style={{ color: 'var(--text2)', fontSize: 12 }}>{b.attendee_email} · {fmt(b.start_at)}</div>
                            </div>
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                              <span className={`badge badge-${b.status === 'confirmed' ? 'success' : 'muted'}`}>{b.status}</span>
                              {b.status === 'confirmed' && (
                                <button className="btn btn-ghost btn-sm" style={{ fontSize: 11 }} onClick={() => handleCancelBooking(b.id)}>
                                  Cancel
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
