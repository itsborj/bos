import { useEffect, useState } from 'react';
import { CmoChat } from './CmoChat';
import { Stream } from './Stream';

export function CmoPage() {
  const [mobileStreamActive, setMobileStreamActive] = useState(false);

  useEffect(() => {
    const showStream = () => setMobileStreamActive(true);
    window.addEventListener('bos:focus-artifact', showStream);
    return () => window.removeEventListener('bos:focus-artifact', showStream);
  }, []);

  return (
    <div className={`stream-cmo-shell${mobileStreamActive ? ' mobile-stream-active' : ''}`}>
      <div className="stream-cmo-chat-col">
        <CmoChat />
      </div>
      <div className="stream-cmo-feed">
        <button className="mobile-back-btn" onClick={() => setMobileStreamActive(false)}>← Chat</button>
        <Stream embedded />
      </div>
    </div>
  );
}
