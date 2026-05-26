import { CmoChat } from './CmoChat';
import { Stream } from './Stream';

export function CmoPage() {
  return (
    <div className="stream-cmo-shell">
      <div className="stream-cmo-chat-col">
        <CmoChat />
      </div>
      <div className="stream-cmo-feed">
        <Stream embedded />
      </div>
    </div>
  );
}
