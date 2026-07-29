import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';

// ── Types ────────────────────────────────────────────────────────────────────

export interface DriveRootState {
  id: string;
  name: string;
  logoCount: number;
  templateCount: number;
}

export interface DriveFolderPickerState {
  driveRoot: DriveRootState | null;
  driveLoading: boolean;
  driveError: string | null;
  driveNotConnected: boolean;
  driveNeedsReauth: boolean;
  driveReconnecting: boolean;
  logoCount: number;
  templateCount: number;
  refresh: () => Promise<void>;
  reconnect: () => Promise<void>;
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useDriveFolderPicker(brandId: string | null | undefined): DriveFolderPickerState {
  const [driveRoot, setDriveRoot] = useState<DriveRootState | null>(null);
  const [driveLoading, setDriveLoading] = useState(Boolean(brandId));
  const [driveError, setDriveError] = useState<string | null>(null);
  const [driveNotConnected, setDriveNotConnected] = useState(false);
  const [driveNeedsReauth, setDriveNeedsReauth] = useState(false);
  const [driveReconnecting, setDriveReconnecting] = useState(false);
  const [logoCount, setLogoCount] = useState(0);
  const [templateCount, setTemplateCount] = useState(0);
  const requestGeneration = useRef(0);

  const refresh = useCallback(async () => {
    const generation = ++requestGeneration.current;
    if (!brandId) {
      setDriveRoot(null);
      setDriveError(null);
      setDriveNotConnected(false);
      setDriveNeedsReauth(false);
      setLogoCount(0);
      setTemplateCount(0);
      setDriveLoading(false);
      return;
    }
    setDriveLoading(true);
    setDriveError(null);
    setDriveNotConnected(false);
    setDriveNeedsReauth(false);
    try {
      const root = await api.listDriveFolders(brandId);
      if (generation !== requestGeneration.current) return;
      if (!root.folder_id || root.folder_id === 'root') {
        setDriveRoot(null);
        setLogoCount(0);
        setTemplateCount(0);
        setDriveError('Select one Google Drive Brand Kit folder before generating or approving the Brand Creative Brief.');
        return;
      }
      const images = await api.listDriveImages(brandId, root.folder_id, 'image');
      if (generation !== requestGeneration.current) return;
      const logos = (images.files || []).filter(f =>
        /(^|[-_ .])(logo|wordmark|brandmark|mark)([-_ .]|$)/i.test(f.name || '')
      ).length;
      const templates = (images.files || []).filter(f =>
        /(^|[-_ .])(template\d*|template|master|reference|ref)([-_ .]|$)/i.test(f.name || '')
      ).length;
      if (!logos) {
        setDriveRoot(null);
        setLogoCount(0);
        setTemplateCount(templates);
        setDriveError(`Selected folder "${root.folder_name || root.folder_id}" needs at least one image named like *_logo, *_wordmark, or *_brandmark before image/video generators can run.`);
        return;
      }
      setLogoCount(logos);
      setTemplateCount(templates);
      setDriveRoot({ id: root.folder_id, name: root.folder_name || root.folder_id, logoCount: logos, templateCount: templates });
    } catch (err: unknown) {
      if (generation !== requestGeneration.current) return;
      setDriveRoot(null);
      setLogoCount(0);
      setTemplateCount(0);
      const status = err instanceof Error ? (err as Error & { status?: number }).status : undefined;
      const msg = err instanceof Error ? err.message : 'Could not check Google Drive. Retry the request.';
      if (status === 404 || msg.includes('DRIVE_NOT_CONNECTED')) {
        setDriveNotConnected(true);
        setDriveError('Connect Google Drive to link a Brand Kit folder for this brand.');
      } else if (status === 401 || msg.includes('DRIVE_REAUTH_REQUIRED')) {
        setDriveNeedsReauth(true);
        setDriveError('Reconnect Google Drive for this brand. The saved token expired or was revoked.');
      } else {
        setDriveError(msg);
      }
    } finally {
      if (generation === requestGeneration.current) setDriveLoading(false);
    }
  }, [brandId]);

  useEffect(() => {
    void refresh();
    return () => { requestGeneration.current += 1; };
  }, [refresh]);

  const reconnect = useCallback(async () => {
    if (!brandId) return;
    setDriveReconnecting(true);
    try {
      const res = await api.startSocialConnect(brandId, 'google_drive');
      // Store current page so AdminBrands can redirect back after OAuth completes
      // This ensures seamless UX when reconnecting from onboarding or brand detail pages
      localStorage.setItem('bos_drive_return_to', window.location.pathname + window.location.search);
      window.location.href = res.authorize_url;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'check Google OAuth settings';
      setDriveError(`⚠️ Could not start Google Drive connect — ${msg}`);
      localStorage.removeItem('bos_drive_return_to'); // Clean up on error
      setDriveReconnecting(false);
    }
  }, [brandId]);

  return {
    driveRoot,
    driveLoading,
    driveError,
    driveNotConnected,
    driveNeedsReauth,
    driveReconnecting,
    logoCount,
    templateCount,
    refresh,
    reconnect,
  };
}

// ── Modal ────────────────────────────────────────────────────────────────────

interface DriveFolderPickerModalProps {
  brandId: string;
  open: boolean;
  onClose: () => void;
  onValidated: (root: DriveRootState) => void;
}

export function DriveFolderPickerModal({ brandId, open, onClose, onValidated }: DriveFolderPickerModalProps) {
  const [current, setCurrent] = useState<{ id: string; name: string }>({ id: 'root', name: 'My Drive' });
  const [stack, setStack] = useState<{ id: string; name: string }[]>([]);
  const [folders, setFolders] = useState<{ id: string; name: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validating, setValidating] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const requestGeneration = useRef(0);

  async function loadDir(folder: { id: string; name: string }, newStack: { id: string; name: string }[]) {
    const generation = ++requestGeneration.current;
    setLoading(true);
    setFolders([]);
    setError(null);
    try {
      const res = await api.listDriveFolders(brandId, folder.id);
      if (generation !== requestGeneration.current) return;
      setCurrent(folder.id === 'root' ? { id: 'root', name: 'My Drive' } : folder);
      setStack(newStack);
      setFolders(res.folders || []);
    } catch (e) {
      if (generation !== requestGeneration.current) return;
      const errorMsg = e instanceof Error ? e.message : 'Could not load Drive.';
      // Check if this is a connection error that might be resolved by retrying
      if (errorMsg.includes('DRIVE_NOT_CONNECTED') || errorMsg.includes('404')) {
        setError('Google Drive connection not ready. Please wait a moment and try again.');
      } else {
        setError(errorMsg);
      }
    } finally {
      if (generation === requestGeneration.current) setLoading(false);
    }
  }

  useEffect(() => {
    requestGeneration.current += 1;
    if (!open) {
      setLoading(false);
      setValidating(false);
      return;
    }
    setCurrent({ id: 'root', name: 'My Drive' });
    setStack([]);
    setFolders([]);
    setError(null);
    // Small delay to allow OAuth connection to fully establish.
    const timer = setTimeout(() => { void loadDir({ id: 'root', name: 'My Drive' }, []); }, 300);
    window.requestAnimationFrame(() => dialogRef.current?.focus());
    return () => {
      clearTimeout(timer);
      requestGeneration.current += 1;
    };
  }, [open, brandId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !validating) onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, validating, onClose]);

  async function handleSelect() {
    if (!current || current.id === 'root') {
      setError('Open and select a Brand Kit folder inside My Drive.');
      return;
    }
    const generation = ++requestGeneration.current;
    setValidating(true);
    setError(null);
    try {
      const folderPath = stack.map(item => item.name).join(' / ') || current.name;
      await api.setDriveRoot(brandId, current.id, current.name, folderPath);
      const images = await api.listDriveImages(brandId, current.id, 'image');
      if (generation !== requestGeneration.current) return;
      const logos = (images.files || []).filter(f =>
        /(^|[-_ .])(logo|wordmark|brandmark|mark)([-_ .]|$)/i.test(f.name || '')
      ).length;
      const templates = (images.files || []).filter(f =>
        /(^|[-_ .])(template\d*|template|master|reference|ref)([-_ .]|$)/i.test(f.name || '')
      ).length;
      onValidated({ id: current.id, name: current.name, logoCount: logos, templateCount: templates });
      onClose();
    } catch (err: unknown) {
      if (generation === requestGeneration.current) {
        setError(err instanceof Error ? err.message : 'Selected folder must contain at least one *_logo, *_wordmark, or *_brandmark image file.');
      }
    } finally {
      if (generation === requestGeneration.current) setValidating(false);
    }
  }

  if (!open) return null;

  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      onClick={e => { if (e.target === e.currentTarget && !validating) onClose(); }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="drive-folder-picker-title"
        tabIndex={-1}
        style={{ background: '#fff', borderRadius: 14, padding: 24, width: 480, maxWidth: '95vw', maxHeight: '80vh', display: 'flex', flexDirection: 'column', gap: 12 }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div id="drive-folder-picker-title" style={{ fontWeight: 700, fontSize: 15 }}>Choose Brand Kit folder</div>
          <button type="button" aria-label="Close Drive folder picker" disabled={validating} style={{ background: 'none', border: 'none', cursor: validating ? 'not-allowed' : 'pointer', fontSize: 18, color: '#6b7280' }} onClick={onClose}>✕</button>
        </div>
        <div style={{ fontSize: 12, color: '#6b7280' }}>
          The selected folder must include at least one <code>*_logo.*</code>, <code>*_wordmark.*</code>, or <code>*_brandmark.*</code> image file.
        </div>

        {/* Breadcrumb */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap', fontSize: 12, color: '#6b7280', background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: 8, padding: '7px 9px', minHeight: 34 }}>
          {stack.length === 0 ? (
            <span>📁 <strong style={{ color: '#111827' }}>My Drive</strong></span>
          ) : (
            <button type="button" className="btn btn-ghost btn-sm" style={{ padding: '2px 6px', fontSize: 11 }} disabled={loading || validating}
              onClick={() => loadDir({ id: 'root', name: 'My Drive' }, [])}>
              📁 My Drive
            </button>
          )}
          {stack.map((item, i) => (
            <span key={item.id} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ color: '#9ca3af' }}>›</span>
              {i < stack.length - 1 ? (
                <button type="button" className="btn btn-ghost btn-sm" style={{ padding: '2px 6px', fontSize: 11 }} disabled={loading || validating}
                  onClick={() => loadDir(item, stack.slice(0, i + 1))}>
                  {item.name}
                </button>
              ) : (
                <span>📁 <strong style={{ color: '#111827' }}>{item.name}</strong></span>
              )}
            </span>
          ))}
        </div>

        {loading && <div aria-live="polite" style={{ color: '#6b7280', fontSize: 13 }}>Loading…</div>}
        {error && <div role="alert" aria-live="assertive" style={{ color: '#ef4444', fontSize: 13 }}>{error}</div>}
        {!loading && !error && folders.length === 0 && (
          <div style={{ color: '#6b7280', fontSize: 13 }}>No subfolders here.</div>
        )}
        {!loading && folders.length > 0 && (
          <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
            {folders.map(f => (
              <button key={f.id} type="button" disabled={validating}
                style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 7, cursor: validating ? 'not-allowed' : 'pointer', textAlign: 'left', fontSize: 13 }}
                onClick={() => loadDir(f, [...stack, f])}>
                <span style={{ fontSize: 18, flexShrink: 0 }}>📁</span>
                <span style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                <span style={{ marginLeft: 'auto', color: '#9a3412', fontSize: 11, flexShrink: 0 }}>Open →</span>
              </button>
            ))}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, paddingTop: 4, borderTop: '1px solid #e5e7eb' }}>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} disabled={validating}>Cancel</button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={current.id === 'root' || loading || validating}
            onClick={handleSelect}
            title={current.id === 'root' ? 'Open and select a folder inside My Drive.' : undefined}
          >
            {validating ? 'Validating…' : current.id === 'root' ? 'Choose a folder inside My Drive' : `Validate & use "${current.name}"`}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Status card ──────────────────────────────────────────────────────────────

interface DriveAssetRootCardProps {
  brandId: string | null | undefined;
  state: DriveFolderPickerState;
  /** If true, hides the card entirely when there's no brandId (org scope) */
  hideForOrg?: boolean;
  /** Called when the user clicks "Choose folder" or "Change folder" */
  onOpenPicker: () => void;
}

export function DriveAssetRootCard({ brandId, state, hideForOrg, onOpenPicker }: DriveAssetRootCardProps) {
  const { driveRoot, driveLoading, driveError, driveNotConnected, driveNeedsReauth, driveReconnecting, logoCount, templateCount, refresh, reconnect } = state;

  if (hideForOrg && !brandId) return null;

  const statusText = driveLoading
    ? 'Checking Drive…'
    : driveRoot
      ? `${driveRoot.name} · ${logoCount} logo${logoCount !== 1 ? 's' : ''} · ${templateCount} creative reference${templateCount !== 1 ? 's' : ''}`
      : driveError || 'No validated folder selected';

  return (
    <div className="admin-card" style={{ marginBottom: 16 }}>
      <div className="admin-card-title">Step 2 — Connect Google Drive &amp; Select Brand Kit Folder</div>
      <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 12 }}>
        Pick one Google Drive folder for this brand. It must contain at least one image named like{' '}
        <code>*_logo.*</code>, <code>*_wordmark.*</code>, or <code>*_brandmark.*</code>.
        Generated outputs will be saved back to this same folder.
      </div>
      {!brandId ? (
        <div style={{ fontSize: 13, color: 'var(--text2)' }}>Import the brand brief first, then connect Drive and select the Brand Kit folder.</div>
      ) : (
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <span className={driveRoot ? 'badge badge-success' : 'badge badge-warning'}>
            {driveRoot ? 'Validated' : 'Required'}
          </span>
          <span style={{ fontSize: 13, color: (driveError && !driveRoot) ? 'var(--error)' : undefined }}>
            {statusText}
          </span>
          {(driveNotConnected || driveNeedsReauth) ? (
            <button type="button" className="btn btn-dark btn-sm" onClick={reconnect} disabled={driveReconnecting}>
              {driveReconnecting ? 'Redirecting…' : driveNotConnected ? 'Connect Google Drive' : 'Reconnect Google Drive'}
            </button>
          ) : driveError ? (
            <>
              <button type="button" className="btn btn-dark btn-sm" onClick={() => void refresh()} disabled={driveLoading}>
                {driveLoading ? 'Retrying…' : 'Retry Drive check'}
              </button>
              <button type="button" className="btn btn-secondary btn-sm" onClick={onOpenPicker} disabled={driveLoading}>Choose another folder</button>
            </>
          ) : (
            <button type="button" className="btn btn-dark btn-sm" onClick={onOpenPicker} disabled={driveLoading}>
              {driveRoot ? 'Change folder' : 'Choose folder'}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
