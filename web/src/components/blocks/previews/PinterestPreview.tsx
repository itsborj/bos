
interface PinterestPreviewProps {
  title: string;
  description: string;
  imageUrl?: string;
}

export function PinterestPreview({ title, description, imageUrl }: PinterestPreviewProps) {
  return (
    <div style={{ 
      width: '236px', 
      border: '1px solid #ddd', 
      borderRadius: '16px', 
      overflow: 'hidden', 
      backgroundColor: '#fff', 
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif' 
    }}>
      {/* Pin Image */}
      {imageUrl ? (
        <img src={imageUrl} alt="Pin" style={{ width: '100%', height: 'auto', display: 'block' }} />
      ) : (
        <div style={{ 
          width: '100%', height: '300px', 
          backgroundColor: '#f0f0f0', 
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#ccc', fontSize: '14px'
        }}>
          Pin Creative
        </div>
      )}

      {/* Info Area */}
      <div style={{ padding: '12px' }}>
        <div style={{ fontSize: '14px', fontWeight: '600', color: '#111', marginBottom: '4px', lineHeight: '1.3' }}>
          {title}
        </div>
        <div style={{ fontSize: '12px', color: '#555', lineHeight: '1.4', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
          {description}
        </div>
      </div>
    </div>
  );
}
