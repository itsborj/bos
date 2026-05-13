import React from 'react';
import type { ReactNode } from 'react';
import { SurfaceProvider } from './SurfaceContext';

interface FullScreenSurfaceProps {
  children: ReactNode;
  className?: string;
}

export const FullScreenSurface: React.FC<FullScreenSurfaceProps> = ({ children, className = '' }) => {
  return (
    <SurfaceProvider type="full-screen">
      <div className={`w-full h-full ${className}`}>
        {children}
      </div>
    </SurfaceProvider>
  );
};
