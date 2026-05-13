import React from 'react';
import type { ReactNode } from 'react';
import { SurfaceProvider } from './SurfaceContext';

interface PanelSurfaceProps {
  children: ReactNode;
  className?: string;
}

export const PanelSurface: React.FC<PanelSurfaceProps> = ({ children, className = '' }) => {
  return (
    <SurfaceProvider type="panel">
      {/* 420px layout constraints for workspace panels */}
      <div className={`w-full max-w-[420px] ${className}`}>
        {children}
      </div>
    </SurfaceProvider>
  );
};
