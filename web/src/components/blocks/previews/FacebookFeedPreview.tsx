
interface FacebookFeedPreviewProps {
  pageName: string;
  adCopy: string;
  imageUrl?: string;
  ctaText: string;
}

export function FacebookFeedPreview({ pageName, adCopy, imageUrl, ctaText }: FacebookFeedPreviewProps) {
  return (
    <div style={{ 
      fontFamily: 'Segoe UI, Helvetica, Arial, sans-serif', 
      maxWidth: '500px', 
      border: '1px solid #ddd', 
      borderRadius: '8px', 
      overflow: 'hidden', 
      backgroundColor: '#fff' 
    }}>
      {/* Header */}
      <div style={{ display: 'flex', padding: '12px', alignItems: 'center', gap: '10px' }}>
        <div style={{ 
          width: '40px', height: '40px', 
          borderRadius: '50%', 
          backgroundColor: '#eee', 
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '14px', fontWeight: 'bold', color: '#888'
        }}>
          {pageName[0]}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ fontSize: '14px', fontWeight: '600', color: '#050505' }}>{pageName}</div>
          <div style={{ fontSize: '12px', color: '#65676b' }}>Sponsored · <span style={{ cursor: 'pointer' }}>🌐</span></div>
        </div>
      </div>

      {/* Copy */}
      <div style={{ padding: '0 12px 12px', fontSize: '14px', color: '#050505', lineHeight: '1.4' }}>
        {adCopy}
      </div>

      {/* Image */}
      {imageUrl ? (
        <img src={imageUrl} alt="Ad" style={{ width: '100%', height: 'auto', display: 'block' }} />
      ) : (
        <div style={{ 
          width: '100%', height: '250px', 
          backgroundColor: '#f0f2f5', 
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#bcc0c4', fontSize: '14px'
        }}>
          Creative Placeholder
        </div>
      )}

      {/* Footer/CTA */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        padding: '10px 12px', 
        borderTop: '1px solid #ddd', 
        backgroundColor: '#f0f2f5' 
      }}>
        <div style={{ fontSize: '14px', fontWeight: '600', color: '#050505' }}>{pageName}</div>
        <button style={{ 
          backgroundColor: '#e4e6eb', 
          border: 'none', 
          borderRadius: '6px', 
          padding: '6px 12px', 
          fontSize: '13px', 
          fontWeight: '600', 
          color: '#050505', 
          cursor: 'pointer' 
        }}>
          {ctaText}
        </button>
      </div>
    </div>
  );
}
