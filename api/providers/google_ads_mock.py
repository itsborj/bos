from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "google_ads_demo.json"


class MockGoogleAdsConnector:
    """Fixture-backed stand-in for the live Google Ads connector.

    Mirrors the full read+write surface used by BOS analytics and campaign
    management modules so every capability can develop and test without live
    Google Ads credentials.
    """

    def __init__(self, fixture_path: Path | None = None) -> None:
        self.fixture_path = fixture_path or _FIXTURE_PATH
        self.data = json.loads(self.fixture_path.read_text())

    def _campaigns_for(self, customer_id: str) -> list[dict[str, Any]]:
        return [
            row for row in self.data.get("campaigns", [])
            if str(row.get("customer_id")) == str(customer_id)
        ]

    def list_accessible_customers(self) -> list[dict[str, Any]]:
        return list(self.data.get("customers", []))

    def search(self, customer_id: str, query: str, login_customer_id: str | None = None) -> list[dict[str, Any]]:
        rows = self._campaigns_for(customer_id)
        if "LAST_7_DAYS" in query.upper():
            rows = [row for row in rows if row.get("date_range") == "LAST_7_DAYS"]
        return rows

    def get_resource_metadata(self, resource_name: str) -> dict[str, Any]:
        if resource_name != "campaign":
            return {"resource": resource_name, "fields": []}
        return {
            "resource": "campaign",
            "fields": [
                "campaign.id", "campaign.name", "campaign.status",
                "metrics.cost_micros", "metrics.impressions",
                "metrics.clicks", "metrics.conversions", "metrics.ctr",
                "segments.device",
            ],
        }

    def search_terms(self, customer_id: str, campaign_id: str | None = None) -> dict[str, Any]:
        campaigns = self._campaigns_for(customer_id)
        if campaign_id:
            campaigns = [c for c in campaigns if str(c.get("campaign_id")) == str(campaign_id)]
        terms: list[dict[str, Any]] = []
        for c in campaigns:
            for t in c.get("search_terms", []):
                terms.append(
                    {
                        "campaign": c["campaign"],
                        "campaign_id": c["campaign_id"],
                        "term": t["term"],
                        "status": t.get("status", "NONE"),
                        "spend": t["spend"],
                        "clicks": t["clicks"],
                        "impressions": t.get("impressions", 0),
                        "conversions": t.get("conversions", 0),
                        "ctr": t.get("ctr", 0.0),
                        "cpa": round(t["spend"] / t["conversions"], 2) if t.get("conversions") else None,
                    }
                )
        terms.sort(key=lambda x: x["spend"], reverse=True)
        return {"terms": terms, "source": "mock_google_ads_mcp"}

    def keyword_performance(self, customer_id: str, campaign_id: str | None = None) -> dict[str, Any]:
        campaigns = self._campaigns_for(customer_id)
        if campaign_id:
            campaigns = [c for c in campaigns if str(c.get("campaign_id")) == str(campaign_id)]
        keywords: list[dict[str, Any]] = []
        for c in campaigns:
            for k in c.get("keywords", []):
                keywords.append(
                    {
                        "campaign": c["campaign"],
                        "campaign_id": c["campaign_id"],
                        "keyword_id": k["keyword_id"],
                        "text": k["text"],
                        "match_type": k["match_type"],
                        "status": k["status"],
                        "quality_score": k.get("quality_score"),
                        "spend": k["spend"],
                        "clicks": k["clicks"],
                        "impressions": k.get("impressions", 0),
                        "conversions": k.get("conversions", 0),
                        "cpa": k.get("cpa"),
                        "ctr": round((k["clicks"] / k["impressions"]) * 100, 2) if k.get("impressions") else 0.0,
                    }
                )
        keywords.sort(key=lambda x: x["spend"], reverse=True)
        return {"keywords": keywords, "source": "mock_google_ads_mcp"}

    def optimization_suggestions(self, customer_id: str) -> dict[str, Any]:
        return {
            "recommendations": list(self.data.get("recommendations", [])),
            "source": "mock_google_ads_mcp",
        }

    def budget_health(self, customer_id: str) -> dict[str, Any]:
        campaigns = self._campaigns_for(customer_id)
        result: list[dict[str, Any]] = []
        for c in campaigns:
            if c.get("status", "").lower() != "enabled":
                continue
            daily_budget = float(c.get("daily_budget", 0))
            utilization = float(c.get("budget_utilization_pct", 0))
            spent_today = round(daily_budget * utilization / 100, 2) if daily_budget else 0.0
            result.append(
                {
                    "campaign": c["campaign"],
                    "campaign_id": c["campaign_id"],
                    "status": c["status"],
                    "daily_budget": daily_budget,
                    "spent_today": spent_today,
                    "utilization_pct": utilization,
                    "budget_recommendation": c.get("budget_recommendation", "MAINTAIN"),
                }
            )
        return {"campaigns": result, "source": "mock_google_ads_mcp"}

    def list_campaigns(self, customer_id: str) -> dict[str, Any]:
        campaigns = self._campaigns_for(customer_id)
        result: list[dict[str, Any]] = []
        for c in campaigns:
            result.append(
                {
                    "campaign_id": c["campaign_id"],
                    "campaign": c["campaign"],
                    "status": c["status"],
                    "channel_type": c.get("channel_type", "SEARCH"),
                    "daily_budget": c.get("daily_budget"),
                    "spend_last_7d": c["spend"],
                    "clicks": c["clicks"],
                    "impressions": c["impressions"],
                    "conversions": c["conversions"],
                }
            )
        return {"campaigns": result, "source": "mock_google_ads_mcp"}

    def update_campaign_status(self, customer_id: str, campaign_id: str, status: str) -> dict[str, Any]:
        return {
            "campaign_id": campaign_id,
            "new_status": status,
            "source": "mock_google_ads_mcp",
            "note": "Mock — no actual change applied",
        }

    def update_campaign_budget(self, customer_id: str, campaign_id: str, daily_budget_usd: float) -> dict[str, Any]:
        return {
            "campaign_id": campaign_id,
            "new_daily_budget_usd": daily_budget_usd,
            "source": "mock_google_ads_mcp",
            "note": "Mock — no actual change applied",
        }


_WEEKLY_QUERY = """
SELECT
  campaign.id,
  campaign.name,
  campaign.status,
  metrics.cost_micros,
  metrics.impressions,
  metrics.clicks,
  metrics.conversions,
  metrics.ctr
FROM campaign
WHERE segments.date DURING LAST_7_DAYS
""".strip()


def _connector() -> MockGoogleAdsConnector:
    return MockGoogleAdsConnector()


def weekly_performance_summary(customer_id: str = "1234567890") -> dict[str, Any]:
    conn = _connector()
    customers = conn.list_accessible_customers()
    customer = next((c for c in customers if str(c.get("customer_id")) == str(customer_id)), customers[0])
    rows = conn.search(str(customer["customer_id"]), _WEEKLY_QUERY)

    spend = round(sum(float(r.get("spend", 0)) for r in rows), 2)
    impressions = int(sum(int(r.get("impressions", 0)) for r in rows))
    clicks = int(sum(int(r.get("clicks", 0)) for r in rows))
    conversions = int(sum(int(r.get("conversions", 0)) for r in rows))
    ctr = round((clicks / impressions) * 100, 2) if impressions else 0.0
    cpa = round(spend / conversions, 2) if conversions else 0.0

    return {
        "customer": customer,
        "date_range": "LAST_7_DAYS",
        "metrics": {"spend": spend, "impressions": impressions, "clicks": clicks, "conversions": conversions, "ctr": ctr, "cpa": cpa},
        "campaigns": rows,
        "query": _WEEKLY_QUERY,
        "source": "mock_google_ads_mcp",
    }


def search_terms(customer_id: str = "1234567890", campaign_id: str | None = None) -> dict[str, Any]:
    conn = _connector()
    result = conn.search_terms(customer_id, campaign_id)
    customers = conn.list_accessible_customers()
    customer = next((c for c in customers if str(c.get("customer_id")) == str(customer_id)), customers[0])
    result["customer"] = customer
    return result


def keyword_performance(customer_id: str = "1234567890", campaign_id: str | None = None) -> dict[str, Any]:
    conn = _connector()
    result = conn.keyword_performance(customer_id, campaign_id)
    customers = conn.list_accessible_customers()
    customer = next((c for c in customers if str(c.get("customer_id")) == str(customer_id)), customers[0])
    result["customer"] = customer
    return result


def optimization_suggestions(customer_id: str = "1234567890") -> dict[str, Any]:
    conn = _connector()
    result = conn.optimization_suggestions(customer_id)
    customers = conn.list_accessible_customers()
    customer = next((c for c in customers if str(c.get("customer_id")) == str(customer_id)), customers[0])
    result["customer"] = customer
    return result


def budget_health(customer_id: str = "1234567890") -> dict[str, Any]:
    conn = _connector()
    result = conn.budget_health(customer_id)
    customers = conn.list_accessible_customers()
    customer = next((c for c in customers if str(c.get("customer_id")) == str(customer_id)), customers[0])
    result["customer"] = customer
    return result


def list_campaigns(customer_id: str = "1234567890") -> dict[str, Any]:
    conn = _connector()
    result = conn.list_campaigns(customer_id)
    customers = conn.list_accessible_customers()
    customer = next((c for c in customers if str(c.get("customer_id")) == str(customer_id)), customers[0])
    result["customer"] = customer
    return result
