import React from 'react';
import type { BriefingBlock } from '../../types/stream';
import { NarrativeBlock } from './NarrativeBlock';
import { AlertBlock } from './AlertBlock';
import { ModuleCard } from './ModuleCard';
import { PerformanceReport } from './PerformanceReport';
import { ApprovalBundle } from './ApprovalBundle';

interface BlockRendererProps {
  block: BriefingBlock;
}

export const BlockRenderer: React.FC<BlockRendererProps> = ({ block }) => {
  // Reads layout_hint and routes rendering to the correct surface-agnostic component
  switch (block.layout_hint) {
    case 'narrative':
      return <NarrativeBlock block={block} />;
    case 'alert':
      return <AlertBlock block={block} />;
    case 'compact':
      return <ModuleCard block={block} />;
    case 'table':
      return <PerformanceReport block={block} />;
    case 'media':
      return block.content?.run
        ? <ApprovalBundle run={block.content.run} surfaceContext="chat-inline" />
        : <div className="p-2 border border-dashed border-gray-400 text-gray-600 text-sm">Approval bundle unavailable</div>;
    default:
      console.warn(`Unknown layout_hint: ${block.layout_hint}`);
      return <div className="p-2 border border-dashed border-red-500 text-red-500 text-sm">Unknown block type</div>;
  }
};
