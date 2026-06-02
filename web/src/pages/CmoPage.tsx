import { Stream } from './Stream';

// CmoChat is kept alive in Layout to preserve in-flight sessions across navigation.
// This component only renders the Stream (right column); Layout provides the shell.
export function CmoPage() {
  return <Stream embedded />;
}
