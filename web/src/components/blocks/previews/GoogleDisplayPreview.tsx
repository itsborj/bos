
interface GoogleDisplayPreviewProps {
  dimensions: string;
  headline: string;
  description: string;
  ctaText: string;
}

export function GoogleDisplayPreview({ dimensions, headline, description, ctaText }: GoogleDisplayPreviewProps) {
  // Simple map for common sizes to relative aspect ratios
  const sizeMap: Record<string, { width: number; height: number }> = {
    '300x250': { width: 300, height: 250 },
    '728x90': { width: 728, height: 90 },
    '160x600': { width: 160, height: 600 },
    '336x280': { width: 336, height: 280 },
  };

  const size = sizeMap[dimensions] || { width: 300, height: 250 };

  return (
    <div style={{ 
      width: size.width, 
      height: size.height, 
      border: '1px solid #ddd', 
      backgroundColor: '#fff', 
      boxSizing: 'border-box',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'center',
      textAlign: 'center',
      padding: '16px',
      fontFamily: 'arial, sans-serif',
      position: 'relative'
    }}>
      <div style={{ 
        fontSize: '16px', 
        fontWeight: 'bold', 
        marginBottom: '8px', 
        color: '#333',
        lineHeight: '1.2'
      }}>
        {headline}
      </div>
      <div style={{ 
        fontSize: '12px', 
        color: '#666', 
        marginBottom: '16px', 
        lineHeight: '1.4' 
      }}>
        {description}
      </div>
      <div style={{ 
        backgroundColor: '#1a73e8', 
        color: '#fff', 
        padding: '6px 12px', 
        borderRadius: '4px', 
        fontSize: '12px', 
        fontWeight: '600',
        cursor: 'pointer'
      }}>
        {ctaText}
      </div>
      <div style={{ 
        position: 'absolute', 
        top: '2px', 
        right: '2px', 
        fontSize: '8px', 
        color: '#ccc', 
        textTransform: 'uppercase' 
      }}>
        Ad
      </div>
    </div>
  );
}
