import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { api } from '../api/client';
import type { ActiveBrand, ActiveCampaign } from './UIContext';
import type { BrandResponse } from '../api/types';

const ACTIVE_BRAND_KEY = 'bos_active_brand';
const ACTIVE_CAMPAIGN_KEY = 'bos_active_campaign';
// A brand selection of "All brands" and "nothing chosen yet" both leave
// ACTIVE_BRAND_KEY absent, so the auto-default-to-first-brand effect below
// can't tell them apart without this separate marker — without it, choosing
// "All brands" always got silently overridden back to the first brand on
// the very next render.
const BRAND_SELECTION_MADE_KEY = 'bos_brand_selection_made';

function readActiveBrand(): ActiveBrand | null {
  try {
    const raw = localStorage.getItem(ACTIVE_BRAND_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    if (parsed && typeof parsed.id === 'string' && typeof parsed.name === 'string') {
      return { id: parsed.id, name: parsed.name };
    }
  } catch {
    return null;
  }
  return null;
}

function readActiveCampaign(): ActiveCampaign | null {
  try {
    const raw = localStorage.getItem(ACTIVE_CAMPAIGN_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    if (parsed && typeof parsed.id === 'string' && typeof parsed.name === 'string') {
      // Campaign is not a durable/global default context. Old localStorage values
      // did not carry status and caused completed campaigns to appear as live CMO
      // context. Only restore an explicitly active campaign selection.
      if (parsed.status !== 'active') return null;
      return {
        id: parsed.id,
        name: parsed.name,
        brand_id: typeof parsed.brand_id === 'string' ? parsed.brand_id : null,
        status: parsed.status,
      };
    }
  } catch {
    return null;
  }
  return null;
}

interface ActiveContextValue {
  activeBrand: ActiveBrand | null;
  setActiveBrand: (brand: ActiveBrand | null) => void;
  activeCampaign: ActiveCampaign | null;
  setActiveCampaign: (campaign: ActiveCampaign | null) => void;
  brands: BrandResponse[];
}

const ActiveContext = createContext<ActiveContextValue | null>(null);

/**
 * Single owner of active brand/campaign selection, shared across the two
 * otherwise-unrelated route trees (`Layout` for CMO/Stream, `AdminLayout`
 * for /admin/*). Previously each tree — and even individual admin pages —
 * kept its own localStorage-backed useState copy, so switching brand in one
 * place did not update an already-mounted page in the other until a full
 * remount. Mount this once above both trees in App.tsx.
 */
export function ActiveProvider({ children }: { children: ReactNode }) {
  const [activeBrand, setActiveBrandState] = useState<ActiveBrand | null>(() => readActiveBrand());
  const [activeCampaign, setActiveCampaign] = useState<ActiveCampaign | null>(() => readActiveCampaign());
  const [brands, setBrands] = useState<BrandResponse[]>([]);

  function setActiveBrand(brand: ActiveBrand | null) {
    localStorage.setItem(BRAND_SELECTION_MADE_KEY, '1');
    setActiveBrandState(brand);
  }

  useEffect(() => {
    if (activeBrand) localStorage.setItem(ACTIVE_BRAND_KEY, JSON.stringify(activeBrand));
    else localStorage.removeItem(ACTIVE_BRAND_KEY);
  }, [activeBrand]);

  useEffect(() => {
    if (activeCampaign) localStorage.setItem(ACTIVE_CAMPAIGN_KEY, JSON.stringify(activeCampaign));
    else localStorage.removeItem(ACTIVE_CAMPAIGN_KEY);
  }, [activeCampaign]);

  useEffect(() => {
    if (!activeCampaign) return;
    if (activeCampaign.status !== 'active') {
      setActiveCampaign(null);
      return;
    }
    if (!activeCampaign.brand_id) {
      setActiveCampaign(null);
      return;
    }
    if (brands.length > 0 && !brands.some(b => b.id === activeCampaign.brand_id)) {
      setActiveCampaign(null);
      return;
    }
    if (!activeBrand?.id && brands.length > 0) {
      const brand = brands.find(b => b.id === activeCampaign.brand_id);
      if (brand) setActiveBrand({ id: brand.id, name: brand.name });
      return;
    }
    if (activeBrand?.id && activeCampaign.brand_id !== activeBrand.id) {
      setActiveCampaign(null);
    }
  }, [activeBrand?.id, activeCampaign, brands]);

  useEffect(() => {
    if (!activeCampaign?.id || !activeCampaign.brand_id) return;
    let cancelled = false;
    api.listCampaigns(activeCampaign.brand_id)
      .then(campaigns => {
        if (cancelled) return;
        const live = campaigns.find(c => c.id === activeCampaign.id && c.brand_id === activeCampaign.brand_id);
        if (!live || live.status !== 'active') {
          setActiveCampaign(null);
          return;
        }
        if (live.name !== activeCampaign.name || live.status !== activeCampaign.status) {
          setActiveCampaign({ id: live.id, name: live.name, brand_id: live.brand_id ?? null, status: live.status });
        }
      })
      .catch(() => {
        // Fail closed: if we cannot verify that a campaign is active, do not keep
        // advertising it as live CMO context. Brand-foundation mode is safer.
        if (!cancelled) setActiveCampaign(null);
      });
    return () => { cancelled = true; };
  }, [activeCampaign?.id, activeCampaign?.brand_id]);

  useEffect(() => {
    let cancelled = false;
    api.getBrands()
      .then(res => { if (!cancelled) setBrands(res.brands || []); })
      .catch(() => { if (!cancelled) setBrands([]); });
    return () => { cancelled = true; };
  }, []);

  // Evict a stale localStorage brand_id once brands load (e.g. after a staging
  // DB reset that changes UUIDs), and default to the first brand only if the
  // operator has never made an explicit choice yet — otherwise an explicit
  // "All brands" selection (also activeBrand === null) would get silently
  // overridden back to the first brand on every render.
  useEffect(() => {
    if (brands.length === 0) return;
    if (activeBrand && !brands.some(b => b.id === activeBrand.id)) {
      setActiveBrand(null);
      setActiveCampaign(null);
      return;
    }
    if (localStorage.getItem(BRAND_SELECTION_MADE_KEY)) return;
    if (activeBrand) return;
    const first = brands[0];
    setActiveBrand({ id: first.id, name: first.name });
  }, [brands, activeBrand]);

  return (
    <ActiveContext.Provider value={{ activeBrand, setActiveBrand, activeCampaign, setActiveCampaign, brands }}>
      {children}
    </ActiveContext.Provider>
  );
}

export function useActiveContext(): ActiveContextValue {
  const ctx = useContext(ActiveContext);
  if (!ctx) throw new Error('useActiveContext must be inside ActiveProvider');
  return ctx;
}
