import React from 'react';
import type { ReactNode } from 'react';
import { SurfaceProvider } from './SurfaceContext';

interface MobileCardSurfaceProps {
  children: ReactNode;
  className?: string;
}

export const MobileCardSurface: React.FC<MobileCardSurfaceProps> = ({ children, className = '' }) => {
  return (
    <SurfaceProvider type="mobile-card">
      <div className={`w-full h-full snap-start relative ${className}`}>
        {children}
      </div>
    </SurfaceProvider>
  );
};
