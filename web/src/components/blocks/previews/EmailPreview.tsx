
interface EmailPreviewProps {
  senderName: string;
  subject: string;
  preheader: string;
  body: string;
}

export function EmailPreview({ senderName, subject, preheader, body }: EmailPreviewProps) {
  return (
    <div style={{ 
      fontFamily: 'Inter, system-ui, sans-serif', 
      maxWidth: '600px', 
      border: '.5px solid var(--border)', 
      borderRadius: 0, 
      overflow: 'hidden', 
      backgroundColor: 'var(--white)',
      color: 'var(--ink-body)'
    }}>
      {/* Inbox Row */}
      <div style={{ 
        display: 'flex', 
        padding: '12px', 
        borderBottom: '.5px solid var(--border)', 
        backgroundColor: 'var(--white)',
        cursor: 'pointer',
        alignItems: 'center',
        gap: '12px'
      }}>
        <div style={{ fontWeight: '600', fontSize: '14px', width: '120px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {senderName}
        </div>
        <div style={{ flex: 1, fontSize: '14px', color: 'var(--ink-body)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          <span style={{ fontWeight: '600', color: 'var(--brand)' }}>{subject}</span> 
          <span style={{ color: 'var(--ink-muted)', marginLeft: '4px' }}>— {preheader}</span>
        </div>
      </div>

      {/* Email Body */}
      <div style={{ padding: '24px', minHeight: '200px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
          <div style={{ fontWeight: '600', fontSize: '14px' }}>{senderName}</div>
          <div style={{ fontSize: '12px', color: 'var(--ink-muted)' }}>Today, 10:00 AM</div>
        </div>
        <div style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '16px', color: 'var(--brand)' }}>{subject}</div>
        <div style={{ 
          fontSize: '14px', 
          lineHeight: '1.6', 
          color: 'var(--ink-body)', 
          whiteSpace: 'pre-wrap' 
        }}>
          {body}
        </div>
      </div>
    </div>
  );
}
