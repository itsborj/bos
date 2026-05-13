
interface InstagramFeedPreviewProps {
  username: string;
  adCopy: string;
  imageUrl?: string;
}

export function InstagramFeedPreview({ username, adCopy, imageUrl }: InstagramFeedPreviewProps) {
  const handle = username.startsWith('@') ? username.slice(1) : username;
  return (
    <div style={{ 
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif', 
      maxWidth: '450px', 
      border: '1px solid #dbdbdb', 
      borderRadius: '8px', 
      overflow: 'hidden', 
      backgroundColor: '#fff' 
    }}>
      {/* Header */}
      <div style={{ display: 'flex', padding: '12px', alignItems: 'center', gap: '10px' }}>
        <div style={{ 
          width: '32px', height: '32px', 
          borderRadius: '50%', 
          backgroundColor: '#fafafa', 
          border: '1px solid #dbdbdb',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '12px', fontWeight: 'bold', color: '#8e8e8e'
        }}>
          {handle[0]}
        </div>
        <div style={{ fontSize: '14px', fontWeight: '600', color: '#262626' }}>{handle} • Sponsored</div>
      </div>

      {/* Image (Square) */}
      {imageUrl ? (
        <img src={imageUrl} alt="Ad" style={{ width: '100%', aspectRatio: '1/1', objectFit: 'cover', display: 'block' }} />
      ) : (
        <div style={{ 
          width: '100%', aspectRatio: '1/1', 
          backgroundColor: '#fafafa', 
          borderBottom: '1px solid #efefef',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#dbdbdb', fontSize: '14px'
        }}>
          1:1 Creative Placeholder
        </div>
      )}

      {/* Interactions */}
      <div style={{ padding: '12px' }}>
        <div style={{ display: 'flex', gap: '12px', marginBottom: '8px' }}>
          <span style={{ fontSize: '20px', cursor: 'pointer' }}>❤️</span>
          <span style={{ fontSize: '20px', cursor: 'pointer' }}>💬</span>
          <span style={{ fontSize: '20px', cursor: 'pointer' }}>✈️</span>
        </div>
        <div style={{ fontSize: '14px', lineHeight: '1.4', color: '#262626' }}>
          <span style={{ fontWeight: '600', marginRight: '5px' }}>{handle}</span>
          {adCopy}
        </div>
      </div>
    </div>
  );
}
