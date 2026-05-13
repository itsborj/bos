import { useNavigate } from 'react-router-dom';

export function WorkspaceMobile() {
  const navigate = useNavigate();

  return (
    <div style={{ padding: '16px 16px 80px' }}>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>Workspace</h2>

      <div className="section" style={{ marginBottom: 24 }}>
        <div className="section-title" style={{ fontSize: 12, textTransform: 'uppercase', color: '#666', marginBottom: 8, fontWeight: 600 }}>
          Active Campaigns
        </div>
        <div className="stream-empty" style={{ padding: '24px 0', fontSize: 13 }}>
          No active campaigns yet.<br />
          <span className="block-link" onClick={() => navigate('/cmo')}>Ask CMO to start a campaign →</span>
        </div>
      </div>

      <div className="section" style={{ marginBottom: 24 }}>
        <div className="section-title" style={{ fontSize: 12, textTransform: 'uppercase', color: '#666', marginBottom: 8, fontWeight: 600 }}>
          Pinned Assets
        </div>
        <div className="stream-empty" style={{ padding: '12px 0', fontSize: 13 }}>
          No pinned assets yet.
        </div>
      </div>

      <div className="section">
        <div className="section-title" style={{ fontSize: 12, textTransform: 'uppercase', color: '#666', marginBottom: 8, fontWeight: 600 }}>
          Past Campaigns
        </div>
        <div className="campaign-item" style={{ textAlign: 'center' }}>
          <div className="campaign-meta" style={{ color: '#bbb' }}>No past campaigns.</div>
        </div>
      </div>
    </div>
  );
}
