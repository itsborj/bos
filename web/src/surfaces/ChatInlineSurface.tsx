import React from 'react';
import type { ReactNode } from 'react';
import { SurfaceProvider } from './SurfaceContext';

interface ChatInlineSurfaceProps {
  children: ReactNode;
  className?: string;
}

export const ChatInlineSurface: React.FC<ChatInlineSurfaceProps> = ({ children, className = '' }) => {
  return (
    <SurfaceProvider type="chat-inline">
      {/* Max 640px layout constraints for inline conversation blocks */}
      <div className={`w-full max-w-[640px] mx-auto ${className}`}>
        {children}
      </div>
    </SurfaceProvider>
  );
};
