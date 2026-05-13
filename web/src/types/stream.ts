export interface BriefingBlock {
  id: string;
  timestamp: string;

  // Routing/importance
  priority: "urgent" | "high" | "normal" | "low";
  category: "decision_needed" | "performance" | "status" | "recommendation";

  // Rendering hints — drives component selection in BlockRenderer
  layout_hint: "compact" | "media" | "table" | "alert" | "narrative";
  interaction: "passive" | "expandable" | "actionable";

  // Opaque payload (Stream doesn't parse this)
  content: any;

  // Optional workspace linking
  campaign_id?: string;
  asset_id?: string;
}
