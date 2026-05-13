# Sample — Meta MCP Sidecar Read-Only Signal

**User asks:** "Check Meta and tell me what needs attention."

**CMO response:**

Meta spent $612.44 over the last 7 days and produced 39 conversions at a $15.70 CPA. Prospecting is creating volume, but retargeting is the cleaner signal. The Page has 8 unresolved comments: 5 buying-intent questions, 2 support risks, and 1 spam item.

**PerformanceReport block:**

```json
{
  "type": "performance_report",
  "title": "Meta Ads Performance — Last 7 Days",
  "layout_hint": "table",
  "metrics": [
    {"label": "Spend", "value": "$612.44"},
    {"label": "Impressions", "value": "92,410"},
    {"label": "Clicks", "value": "1,984"},
    {"label": "Conversions", "value": "39"},
    {"label": "CPA", "value": "$15.70"},
    {"label": "CTR", "value": "2.15%"}
  ],
  "rows": [
    {
      "campaign": "Retargeting — Demo Request",
      "status": "ACTIVE",
      "spend": "$188.14",
      "clicks": 706,
      "conversions": 19,
      "cpa": "$9.90",
      "recommendation": "Keep live; test a controlled 10-15% budget increase after creative refresh."
    }
  ],
  "source": {
    "connector": "mock_meta_mcp",
    "account_id": "act_1122334455",
    "account_name": "Klaroha Demo Meta Ads"
  }
}
```

**Page/comment monitor block:**

```json
{
  "type": "alert",
  "title": "Meta Page Attention Queue",
  "priority": "medium",
  "summary": "8 unresolved comments need review: 5 buying-intent, 2 support-risk, 1 spam.",
  "items": [
    "Reply to buying-intent questions with approved offer language.",
    "Escalate support-risk comments for manual review.",
    "Hide or ignore the spam item after approval."
  ],
  "source": {
    "connector": "mock_meta_mcp",
    "page_id": "9988776655",
    "page_name": "Klaroha Demo Page"
  }
}
```
