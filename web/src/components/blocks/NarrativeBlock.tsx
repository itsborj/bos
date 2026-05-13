import React from 'react';
import type { BriefingBlock } from '../../types/stream';

interface NarrativeBlockProps {
  block: BriefingBlock;
}

export const NarrativeBlock: React.FC<NarrativeBlockProps> = ({ block }) => {
  const content = block.content;
  const text = typeof content === 'string' ? content : content?.text || JSON.stringify(content);
  
  return (
    <div className="bos-msg-text">
      {text}
    </div>
  );
};
