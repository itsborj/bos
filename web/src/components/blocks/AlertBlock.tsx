import React from 'react';
import type { BriefingBlock } from '../../types/stream';

interface AlertBlockProps {
  block: BriefingBlock;
}

export const AlertBlock: React.FC<AlertBlockProps> = ({ block }) => {
  const content = block.content;
  const message = typeof content === 'string' ? content : content?.message || 'Alert';
  const isUrgent = block.priority === 'urgent';
  
  return (
    <div 
      className="bos-msg-text"
      style={{ 
        borderLeft: `3px solid ${isUrgent ? '#dc2626' : '#e6a817'}`,
        backgroundColor: isUrgent ? '#fef2f2' : '#fffbeb',
        padding: '10px 14px'
      }}>
      ⚠ {message}
    </div>
  );
};
