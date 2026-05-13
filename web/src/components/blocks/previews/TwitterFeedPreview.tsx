interface TwitterFeedPreviewProps {
  username: string;
  tweetText: string;
}

export function TwitterFeedPreview({ username, tweetText }: TwitterFeedPreviewProps) {
  const handle = username.startsWith('@') ? username : `@${username}`;
  const displayName = handle.replace('@', '');
  return (
    <div style={{
      width: '100%',
      maxWidth: '500px',
      border: '1px solid #e1e8ed',
      borderRadius: '12px',
      overflow: 'hidden',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      backgroundColor: '#fff',
    }}>
      <div style={{ padding: '12px 16px' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
          <div style={{
            width: '48px',
            height: '48px',
            borderRadius: '50%',
            backgroundColor: '#1DA1F2',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontSize: '20px',
            fontWeight: 800,
            marginRight: '10px',
          }}>
            {displayName.charAt(0).toUpperCase()}
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '15px', lineHeight: 1.2 }}>{displayName}</div>
            <div style={{ color: '#657786', fontSize: '13px' }}>{handle.toLowerCase().replace(/\s/g, '')}</div>
          </div>
        </div>

        {/* Tweet text */}
        <div style={{ fontSize: '23px', lineHeight: 1.3, marginBottom: '10px', wordBreak: 'break-word' }}>
          {tweetText || 'Tweet text missing'}
        </div>

        {/* Actions */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          maxWidth: '425px',
          marginTop: '12px',
          color: '#657786',
          fontSize: '13px',
        }}>
          <span>💬 Reply</span>
          <span>🔁 Retweet</span>
          <span>❤️ Like</span>
          <span>📤 Share</span>
        </div>
      </div>
    </div>
  );
}
