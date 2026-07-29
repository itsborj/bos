import React from 'react';
import type { BriefingBlock } from '../../types/stream';

interface NarrativeBlockProps {
  block: BriefingBlock;
}

function normalizeStructuredText(text: string): string {
  // Providers sometimes return Markdown-like structure as one long paragraph.
  // This formatter is intentionally generic: it restores line breaks around
  // common Markdown structure (rules, bold labels, numbered headings, bullets)
  // without assuming a specific CMO task such as storyboarding.
  return (text || '')
    .replace(/\r\n/g, '\n')
    .replace(/[ \t]+(---+)[ \t]+/g, '\n\n$1\n\n')
    .replace(/[ \t]+(#{1,6}\s+)/g, '\n\n$1')
    .replace(/[ \t]+(\*\*\s*\d+[.)]\s+[^*]+?\*\*)/g, '\n\n$1')
    .replace(/[ \t]+(\d+[.)]\s+)/g, '\n$1')
    .replace(/[ \t]+(-\s+)/g, '\n$1')
    .replace(/[ \t]+(\*\*[^*\n]{1,80}:\*\*)/g, '\n$1')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

export const NarrativeBlock: React.FC<NarrativeBlockProps> = ({ block }) => {
  const content = block.content;
  const rawText = typeof content === 'string' ? content : content?.text || JSON.stringify(content);
  const text = normalizeStructuredText(rawText);
  
  return (
    <div className="bos-msg-text">
      {text}
    </div>
  );
};
