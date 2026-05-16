import { useEffect, useState } from 'react';
import { api } from '../../api/client';

export function AdminCalendar() {
  const [url, setUrl] = useState('');
  const [saved, setSaved] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getWorkspace()
      .then(ws => {
        setUrl(ws.booking_url || '');
        setSaved(ws.booking_url || '');
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true);
    setSaveError('');
    try {
      await api.updateBookingUrl(url.trim() || null);
      setSaved(url.trim());
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  }

  function handleClear() {
    setUrl('');
  }

  if (loading) {
    return <div className="admin-page"><div className="loading-full"><span className="spinner" /></div></div>;
  }

  const embedSnippet = `<div data-klaroha-booking></div>\n<script src="/api/calendar/widget.js" async></script>`;

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="admin-page-title">Scheduling</div>
          <div className="admin-page-subtitle">Connect your booking calendar. It will appear automatically on your public pages.</div>
        </div>
      </div>

      <div className="admin-card">
        <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 8 }}>Booking page URL</div>
        <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 12, lineHeight: 1.6 }}>
          Paste your Google Calendar appointment link, Calendly link, Cal.com link, or any booking URL.
          The calendar will be embedded on your public website automatically — no code changes needed.
        </div>
        <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px', fontSize: 13, color: 'var(--text2)', marginBottom: 16, lineHeight: 1.7 }}>
          <strong style={{ color: 'var(--text1)' }}>Google Calendar:</strong> Open Google Calendar → click{' '}
          <strong>+ Other calendars</strong> → <strong>New appointment schedule</strong> → copy the booking page URL.
        </div>
        <input
          className="input"
          type="url"
          placeholder="https://calendar.google.com/calendar/appointments/..."
          value={url}
          onChange={e => setUrl(e.target.value)}
          style={{ width: '100%', marginBottom: 10 }}
        />
        {saveError && <div style={{ color: 'var(--error)', fontSize: 13, marginBottom: 10 }}>{saveError}</div>}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button
            className="btn btn-dark"
            onClick={handleSave}
            disabled={saving || url.trim() === saved}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
          {url && (
            <button className="btn btn-ghost" onClick={handleClear}>Clear</button>
          )}
          {saved && !saving && url.trim() === saved && (
            <span style={{ fontSize: 12, color: 'var(--success)' }}>Saved</span>
          )}
        </div>
      </div>

      {saved && (
        <div className="admin-card" style={{ marginTop: 16 }}>
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12 }}>Preview</div>
          <iframe
            src={saved}
            title="Booking calendar preview"
            style={{ width: '100%', height: 600, border: '1px solid var(--border)', borderRadius: 8, display: 'block' }}
          />
        </div>
      )}

      <div className="admin-card" style={{ marginTop: 16 }}>
        <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6 }}>Embed on any website</div>
        <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 12 }}>
          WordPress, plain HTML, Webflow — paste this anywhere. The booking URL you set above loads automatically.
        </div>
        <pre style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 6, padding: '10px 14px', fontSize: 12, margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: 'var(--text1)' }}>
          {embedSnippet}
        </pre>
      </div>
    </div>
  );
}
