
interface InstagramStoryPreviewProps {
  username: string;
  adCopy: string;
  imageUrl?: string;
  ctaText: string;
}

export function InstagramStoryPreview({ username, adCopy, imageUrl, ctaText }: InstagramStoryPreviewProps) {
  const handle = username.startsWith('@') ? username.slice(1) : username;
  return (
    <div style={{ 
      width: '280px', 
      aspectRatio: '9/16', 
      border: '1px solid #dbdbdb', 
      borderRadius: '12px', 
      overflow: 'hidden', 
      backgroundColor: '#000', 
      position: 'relative',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
      color: '#fff'
    }}>
      {/* Image background */}
      {imageUrl ? (
        <img src={imageUrl} alt="Story" style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: 0.8 }} />
      ) : (
        <div style={{ 
          width: '100%', height: '100%', 
          backgroundColor: 'linear-gradient(45deg, #1a1a1a, #333)', 
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#444', fontSize: '14px'
        }}>
          9:16 Creative Placeholder
        </div>
      )}

      {/* Top bar */}
      <div style={{ 
        position: 'absolute', 
        top: '12px', 
        left: '12px', 
        display: 'flex', 
        alignItems: 'center', 
        gap: '8px', 
        zIndex: 1 
      }}>
        <div style={{ 
          width: '32px', height: '32px', 
          borderRadius: '50%', 
          border: '2px solid #fff', 
          backgroundColor: '#eee', 
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#333', fontSize: '10px', fontWeight: 'bold'
        }}>
          {handle[0]}
        </div>
        <span style={{ fontSize: '12px', fontWeight: '600', textShadow: '0 1px 2px rgba(0,0,0,0.5)' }}>{handle}</span>
      </div>

      {/* Bottom Content */}
      <div style={{ 
        position: 'absolute', 
        bottom: '24px', 
        left: '16px', 
        right: '16px', 
        zIndex: 1 
      }}>
        <div style={{ 
          fontSize: '16px', 
          lineHeight: '1.4', 
          marginBottom: '16px', 
          textShadow: '0 1px 3px rgba(0,0,0,0.8)',
          fontWeight: '500'
        }}>
          {adCopy}
        </div>
        <div style={{ 
          backgroundColor: 'rgba(255,255,255,0.2)', 
          backdropFilter: 'blur(10px)', 
          border: '1px solid rgba(255,255,255,0.3)',
          padding: '8px 0', 
          borderRadius: '8px', 
          textAlign: 'center', 
          fontSize: '13px', 
          fontWeight: '600',
          cursor: 'pointer',
          textTransform: 'uppercase'
        }}>
          {ctaText} Swipe Up
        </div>
      </div>
    </div>
  );
}
