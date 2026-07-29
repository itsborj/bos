import { createContext, useContext } from 'react';
import type { RunResponse } from '../api/types';

export type WorkspaceTab = 'campaigns';
export type SettingsTab  = 'byok' | 'usage' | 'history';

export interface ActiveBrand {
  id: string;
  name: string;
}

export interface ActiveCampaign {
  id: string;
  name: string;
  brand_id?: string | null;
  status?: string | null;
}

export interface UIContextValue {
  workspaceOpen: boolean;
  workspaceTab: WorkspaceTab;
  openWorkspace: (tab?: WorkspaceTab) => void;
  closeWorkspace: () => void;
  selectedRun: RunResponse | null;
  openRun: (run: RunResponse) => void;
  closeRun: () => void;
  settingsOpen: boolean;
  settingsTab: SettingsTab;
  openSettings: (tab?: SettingsTab) => void;
  closeSettings: () => void;
  pendingRuns: Set<string>;
  pendingRunItems: RunResponse[];
  addPendingRun: (run: RunResponse) => void;
  removePendingRun: (runId: string) => void;
  activeBrand: ActiveBrand | null;
  setActiveBrand: (brand: ActiveBrand | null) => void;
  activeCampaign: ActiveCampaign | null;
  setActiveCampaign: (campaign: ActiveCampaign | null) => void;
}

export const UIContext = createContext<UIContextValue | null>(null);

export function useUI(): UIContextValue {
  const ctx = useContext(UIContext);
  if (!ctx) throw new Error('useUI must be inside Layout');
  return ctx;
}

export function usePendingCount(): number {
  const ctx = useContext(UIContext);
  if (!ctx) return 0;
  return ctx.pendingRunItems.length;
}
