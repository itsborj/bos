interface GoogleSearchPreviewProps {
  headline: string;
  description: string;
  displayUrl: string;
}

function cleanDisplayUrl(value: string): string {
  return value.replace(/^https?:\/\//, '').replace(/\/$/, '') || 'example.com';
}

export function GoogleSearchPreview({ headline, description, displayUrl }: GoogleSearchPreviewProps) {
  const cleanUrl = cleanDisplayUrl(displayUrl);
  const siteName = cleanUrl.split('/')[0];

  return (
    <div
      aria-label="Google Search ad preview"
      style={{
        fontFamily: 'Arial, sans-serif',
        maxWidth: '652px',
        padding: '12px 0 14px',
        background: '#fff',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '6px' }}>
        <div
          style={{
            width: '26px',
            height: '26px',
            borderRadius: '50%',
            background: '#f1f3f4',
            color: '#5f6368',
            display: 'grid',
            placeItems: 'center',
            fontSize: '13px',
            fontWeight: 700,
            flex: '0 0 auto',
          }}
        >
          {siteName.charAt(0).toUpperCase()}
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ color: '#202124', fontSize: '14px', lineHeight: '20px' }}>{siteName}</div>
          <div style={{ color: '#4d5156', fontSize: '12px', lineHeight: '16px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            Sponsored · {cleanUrl}
          </div>
        </div>
      </div>

      <div
        style={{
          color: '#1a0dab',
          fontSize: '20px',
          lineHeight: '26px',
          fontWeight: 400,
          marginBottom: '3px',
        }}
      >
        {headline}
      </div>

      <div style={{ color: '#4d5156', fontSize: '14px', lineHeight: '22px' }}>
        {description}
      </div>
    </div>
  );
}
