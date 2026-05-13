import React, { createContext, useContext } from 'react';
import type { ReactNode } from 'react';

export type SurfaceType = 'panel' | 'full-screen' | 'chat-inline' | 'mobile-card';

interface SurfaceContextValue {
  type: SurfaceType;
}

const SurfaceContext = createContext<SurfaceContextValue | undefined>(undefined);

export const useSurface = () => {
  const context = useContext(SurfaceContext);
  if (!context) {
    // Default fallback in case a component is rendered outside a surface provider
    // (e.g., during testing or generic layouts)
    return { type: 'full-screen' as SurfaceType }; 
  }
  return context;
};

interface SurfaceProviderProps {
  type: SurfaceType;
  children: ReactNode;
}

export const SurfaceProvider: React.FC<SurfaceProviderProps> = ({ type, children }) => {
  return (
    <SurfaceContext.Provider value={{ type }}>
      {children}
    </SurfaceContext.Provider>
  );
};
