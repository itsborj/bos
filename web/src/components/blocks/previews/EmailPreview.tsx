
interface EmailPreviewProps {
  senderName: string;
  subject: string;
  preheader: string;
  body: string;
}

export function EmailPreview({ senderName, subject, preheader, body }: EmailPreviewProps) {
  return (
    <div style={{ 
      fontFamily: 'Segoe UI, Helvetica, Arial, sans-serif', 
      maxWidth: '600px', 
      border: '1px solid #ddd', 
      borderRadius: '8px', 
      overflow: 'hidden', 
      backgroundColor: '#fff' 
    }}>
      {/* Inbox Row */}
      <div style={{ 
        display: 'flex', 
        padding: '12px', 
        borderBottom: '1px solid #eee', 
        backgroundColor: '#f8f9fa',
        cursor: 'pointer',
        alignItems: 'center',
        gap: '12px'
      }}>
        <div style={{ fontWeight: '600', fontSize: '14px', width: '120px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {senderName}
        </div>
        <div style={{ flex: 1, fontSize: '14px', color: '#202124', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          <span style={{ fontWeight: '600' }}>{subject}</span> 
          <span style={{ color: '#70757a', marginLeft: '4px' }}>— {preheader}</span>
        </div>
      </div>

      {/* Email Body */}
      <div style={{ padding: '24px', minHeight: '200px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
          <div style={{ fontWeight: '600', fontSize: '14px' }}>{senderName}</div>
          <div style={{ fontSize: '12px', color: '#70757a' }}>Today, 10:00 AM</div>
        </div>
        <div style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '16px' }}>{subject}</div>
        <div style={{ 
          fontSize: '14px', 
          lineHeight: '1.6', 
          color: '#3c4043', 
          whiteSpace: 'pre-wrap' 
        }}>
          {body}
        </div>
      </div>
    </div>
  );
}
