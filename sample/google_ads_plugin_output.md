# Sample — Third-Party Google Ads Channel Plugin Output

**Status:** draft sample for human approval  
**BITE stage:** Stage 2 — Sample  
**Target plugin:** `channel.google_ads` installed under `api/plugins/google-ads/`

## Sample CMO turn

**User:** `@klar check brand Klaroha`  
**User:** `@klar run google ads performance summary for the last 7 days`

**CMO visible reply:**

Google Ads is converting, but budget pressure is starting to cap demand capture. I’d keep the lead campaign active, raise the daily budget only on the profitable segment, and cut the zero-conversion search waste first.

## Sample run result block

```json
{
  "run_id": "00000000-0000-4000-8000-000000000001",
  "module_id": "marketing.channel.google_ads.analytics.performance_summary",
  "vertical": "marketing",
  "status": "success",
  "result": {
    "content": "Google Ads performance summary: 128 conversions from $2,418.75 spend at $18.90 CPA. Main risk: 94% budget utilization on Demand Capture Search.",
    "self_check": "pass",
    "platform": "google ads performance",
    "block": {
      "type": "google_ads_performance_summary",
      "status": "succeeded",
      "source": "google_ads_api",
      "customer": {
        "customer_id": "1234567890",
        "name": "Klaroha Ads Account",
        "currency_code": "USD",
        "time_zone": "America/New_York"
      },
      "date_range": "LAST_7_DAYS",
      "metrics": {
        "spend": 2418.75,
        "impressions": 184220,
        "clicks": 7369,
        "conversions": 128,
        "ctr": 4.0,
        "cpa": 18.9
      },
      "campaigns": [
        {
          "campaign_id": "991001",
          "campaign": "Demand Capture Search",
          "status": "ENABLED",
          "daily_budget": 350.0,
          "spend": 1718.4,
          "impressions": 109450,
          "clicks": 4925,
          "conversions": 102,
          "ctr": 4.5,
          "cpa": 16.85,
          "budget_utilization_pct": 94.0,
          "recommendation": "Increase budget 15% only if search-term waste is excluded first."
        },
        {
          "campaign_id": "991002",
          "campaign": "Competitor Capture",
          "status": "ENABLED",
          "daily_budget": 120.0,
          "spend": 700.35,
          "impressions": 74770,
          "clicks": 2444,
          "conversions": 26,
          "ctr": 3.27,
          "cpa": 26.94,
          "budget_utilization_pct": 83.0,
          "recommendation": "Hold budget; review expensive competitor terms before scaling."
        }
      ],
      "alerts": [
        {
          "severity": "high",
          "code": "budget_capped",
          "message": "Demand Capture Search used 94% of available daily budget."
        },
        {
          "severity": "medium",
          "code": "wasted_spend_watch",
          "message": "$184.22 in search-term spend has no conversion in the last 7 days."
        }
      ],
      "recommended_actions": [
        {
          "action": "review_search_terms",
          "module_id": "marketing.channel.google_ads.analytics.search_terms",
          "reason": "Cut zero-conversion waste before raising budget."
        },
        {
          "action": "propose_budget_change",
          "module_id": "marketing.channel.google_ads.campaigns.update_budget",
          "campaign_id": "991001",
          "new_daily_budget": 402.5,
          "requires_confirmation": true,
          "reason": "15% increase on the highest-efficiency campaign after exclusions."
        }
      ]
    }
  },
  "execution": {
    "provider": "google_ads",
    "model": "google_ads_api_v18",
    "mode": "tool",
    "attempts": 1,
    "latency_ms": 842,
    "tokens_used": 0,
    "provider_cost": 0.0,
    "sell_price": null
  },
  "trace": {
    "capability": "marketing.analytics",
    "policy": "balanced",
    "candidates_considered": 1,
    "candidates_filtered": 0,
    "winner": "google_ads/google_ads_api_v18",
    "routing_reason": "deterministic tool connector execution"
  }
}
```

## Sample failure block

```json
{
  "content": "Failed to query Google Ads: missing Google Ads OAuth refresh token or customer ID.",
  "self_check": "fail",
  "platform": "google ads performance",
  "block": {
    "type": "google_ads_performance_summary",
    "status": "failed",
    "reason_code": "missing_google_ads_credentials",
    "message": "Connect Google Ads credentials before running performance tools.",
    "details": {
      "missing": ["GOOGLE_ADS_REFRESH_TOKEN", "google_ads_customer_id"]
    }
  }
}
```
