import type { BriefingBlock } from '../../types/stream';
import { FacebookFeedPreview } from './previews/FacebookFeedPreview';

interface Props {
  block: BriefingBlock;
}

export function FacebookCampaignPlan({ block }: Props) {
  const content = block.content || {};
  const preview = content.copy_platform_preview || {};
  const creative = content.creative_concept || {};
  const testing = Array.isArray(content.testing_plan) ? content.testing_plan : [];

  return (
    <div className="approval-bundle chat-inline">
      <div style={{ border: '2px solid #333', borderRadius: 8, background: '#fff', overflow: 'hidden', fontFamily: 'monospace' }}>
        <div style={{ padding: '8px 16px', background: '#f9f9f9', borderBottom: '1px solid #ddd', display: 'flex', justifyContent: 'space-between' }}>
          <span className="status-badge pending">DRAFT PLAN</span>
          <span style={{ fontSize: 10, color: '#777' }}>{content.status || 'Draft Only'}</span>
        </div>
        <div style={{ padding: 16, borderBottom: '1px solid #eee' }}>
          <div style={{ fontSize: 16, fontWeight: 800, marginBottom: 8 }}>{content.title || 'Facebook Campaign Plan'}</div>
          <div style={{ fontSize: 13, lineHeight: 1.5 }}><strong>Objective:</strong> {content.objective}</div>
          <div style={{ fontSize: 13, lineHeight: 1.5 }}><strong>Audience:</strong> {content.audience}</div>
          <div style={{ fontSize: 13, lineHeight: 1.5 }}><strong>Offer angle:</strong> {content.offer_angle}</div>
        </div>
        <div style={{ padding: 20, background: '#f9f9f9', borderBottom: '1px solid #ddd', display: 'flex', justifyContent: 'center' }}>
          <FacebookFeedPreview
            pageName={preview.page_name || 'Brand'}
            adCopy={preview.primary_text || 'Post copy missing'}
            ctaText={preview.cta || 'Learn More'}
          />
        </div>
        <div style={{ padding: 16 }}>
          <div style={{ fontSize: 10, fontWeight: 800, color: '#666', textTransform: 'uppercase', marginBottom: 8 }}>Creative Concept</div>
          <div style={{ fontSize: 13, lineHeight: 1.5 }}>{creative.visual_direction}</div>
          <div style={{ marginTop: 12, fontSize: 10, fontWeight: 800, color: '#666', textTransform: 'uppercase' }}>Testing Plan</div>
          <ul style={{ margin: '8px 0 0 18px', padding: 0, fontSize: 13, lineHeight: 1.5 }}>
            {testing.map((item: string, idx: number) => <li key={idx}>{item}</li>)}
          </ul>
        </div>
      </div>
    </div>
  );
}
