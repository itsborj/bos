import type { BriefingBlock } from '../../types/stream';

interface Props {
  block: BriefingBlock;
}

export function GoogleAdsCampaignDraft({ block }: Props) {
  const content = block.content || {};
  const campaigns = Array.isArray(content.campaigns) ? content.campaigns : [];

  return (
    <div className="google-serp-results">
      {campaigns.flatMap((campaign: any, campaignIndex: number) =>
        (campaign.ad_groups || []).map((adGroup: any, adGroupIndex: number) => {
          const rsa = adGroup.responsive_search_ad || {};
          return (
            <div className="google-serp-preview" key={`${campaign.name}-${campaignIndex}-${adGroup.name}-${adGroupIndex}`}>
              <div className="google-serp-ad-label">Sponsored</div>
              <div className="google-serp-url">{rsa.final_url || 'TBD'} · {rsa.path1 || 'path1'} / {rsa.path2 || 'path2'}</div>
              <div className="google-serp-headline">
                {(rsa.headlines || []).slice(0, 3).map((h: any) => h.text).join(' | ')}
              </div>
              <div className="google-serp-description">
                {(rsa.descriptions || []).slice(0, 2).map((d: any) => d.text).join(' ')}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
