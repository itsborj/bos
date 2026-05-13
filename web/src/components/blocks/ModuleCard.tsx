import React from 'react';
import type { BriefingBlock } from '../../types/stream';
import { useSurface } from '../../surfaces/SurfaceContext';

interface ModuleCardProps {
  block: BriefingBlock;
}

export const ModuleCard: React.FC<ModuleCardProps> = ({ block }) => {
  const { type } = useSurface();
  const content = block.content || {};
  
  const { 
    module_id = 'unknown.module', 
    health = 'unknown', 
    channels = [], 
    run_count = 0, 
    latency = '0ms', 
    last_run = 'Never' 
  } = content;

  // Surface adaptation
  const isCompact = type === 'panel' || type === 'chat-inline';

  return (
    <div className={`p-4 bg-white border border-gray-200 rounded shadow-sm flex ${isCompact ? 'flex-col gap-2' : 'flex-row items-center justify-between'}`}>
      <div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-semibold text-gray-800">{module_id}</span>
          <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${health === 'ok' || health === 'live' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
            {health}
          </span>
        </div>
        <div className="text-xs text-gray-500 mt-1">
          Channels: {channels.length > 0 ? channels.join(', ') : 'None'}
        </div>
      </div>
      
      <div className={`flex ${isCompact ? 'flex-row justify-between w-full mt-2 pt-2 border-t border-gray-100' : 'flex-row items-center gap-6'}`}>
        <div className="text-center">
          <div className="text-xs text-gray-500 mb-0.5">Runs</div>
          <div className="text-sm font-semibold">{run_count}</div>
        </div>
        <div className="text-center">
          <div className="text-xs text-gray-500 mb-0.5">Latency</div>
          <div className="text-sm font-semibold">{latency}</div>
        </div>
        <div className={isCompact ? "text-right" : "text-right"}>
          <div className="text-xs text-gray-500 mb-0.5">Last Run</div>
          <div className="text-sm font-semibold">{last_run}</div>
        </div>
      </div>
    </div>
  );
};
