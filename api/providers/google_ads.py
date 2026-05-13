from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

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

_SEARCH_TERMS_QUERY = """
SELECT
  campaign.id,
  campaign.name,
  search_term_view.search_term,
  search_term_view.status,
  metrics.cost_micros,
  metrics.clicks,
  metrics.impressions,
  metrics.conversions,
  metrics.ctr
FROM search_term_view
WHERE segments.date DURING LAST_7_DAYS
  AND metrics.impressions > 0
ORDER BY metrics.cost_micros DESC
LIMIT 200
""".strip()

_KEYWORD_QUERY = """
SELECT
  campaign.id,
  campaign.name,
  ad_group.name,
  ad_group_criterion.criterion_id,
  ad_group_criterion.keyword.text,
  ad_group_criterion.keyword.match_type,
  ad_group_criterion.status,
  ad_group_criterion.quality_info.quality_score,
  metrics.cost_micros,
  metrics.clicks,
  metrics.impressions,
  metrics.conversions,
  metrics.ctr
FROM keyword_view
WHERE segments.date DURING LAST_7_DAYS
  AND ad_group_criterion.status != 'REMOVED'
ORDER BY metrics.cost_micros DESC
LIMIT 500
""".strip()

_CAMPAIGN_LIST_QUERY = """
SELECT
  campaign.id,
  campaign.name,
  campaign.status,
  campaign.advertising_channel_type,
  campaign_budget.amount_micros,
  metrics.cost_micros,
  metrics.impressions,
  metrics.clicks,
  metrics.conversions
FROM campaign
WHERE segments.date DURING LAST_7_DAYS
  AND campaign.status != 'REMOVED'
ORDER BY metrics.cost_micros DESC
""".strip()

_BUDGET_HEALTH_QUERY = """
SELECT
  campaign.id,
  campaign.name,
  campaign.status,
  campaign_budget.id,
  campaign_budget.name,
  campaign_budget.amount_micros,
  campaign_budget.total_amount_micros,
  campaign_budget.status,
  metrics.cost_micros
FROM campaign
WHERE segments.date DURING TODAY
  AND campaign.status = 'ENABLED'
""".strip()


@dataclass(frozen=True)
class GoogleAdsConfig:
    developer_token: str
    client_id: str
    client_secret: str
    refresh_token: str
    login_customer_id: str | None = None

    @classmethod
    def from_env(cls) -> "GoogleAdsConfig | None":
        developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "").strip()
        client_id = os.getenv("GOOGLE_ADS_CLIENT_ID", "").strip()
        client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET", "").strip()
        refresh_token = os.getenv("GOOGLE_ADS_REFRESH_TOKEN", "").strip()
        login_customer_id = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "").strip() or None
        if not all([developer_token, client_id, client_secret, refresh_token]):
            return None
        return cls(
            developer_token=developer_token,
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            login_customer_id=login_customer_id,
        )


class LiveGoogleAdsConnector:
    def __init__(self, config: GoogleAdsConfig | None = None) -> None:
        self.config = config or GoogleAdsConfig.from_env()
        if self.config is None:
            raise RuntimeError("Google Ads credentials are not configured")

        from google.ads.googleads.client import GoogleAdsClient

        payload: dict[str, Any] = {
            "developer_token": self.config.developer_token,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "refresh_token": self.config.refresh_token,
            "use_proto_plus": True,
        }
        if self.config.login_customer_id:
            payload["login_customer_id"] = self.config.login_customer_id
        self.client = GoogleAdsClient.load_from_dict(payload)

    def _service(self) -> Any:
        return self.client.get_service("GoogleAdsService")

    def list_accessible_customers(self) -> list[str]:
        service = self.client.get_service("CustomerService")
        response = service.list_accessible_customers()
        return [name.split("/")[-1] for name in response.resource_names]

    def list_manager_clients(self, customer_id: str) -> list[dict[str, Any]]:
        query = """
        SELECT
          customer_client.id,
          customer_client.descriptive_name,
          customer_client.manager,
          customer_client.status,
          customer_client.test_account,
          customer_client.currency_code,
          customer_client.time_zone
        FROM customer_client
        WHERE customer_client.level <= 1
        """
        rows = self._service().search(customer_id=customer_id.replace("-", ""), query=query)
        clients: list[dict[str, Any]] = []
        for row in rows:
            client = row.customer_client
            clients.append(
                {
                    "customer_id": str(client.id),
                    "name": client.descriptive_name,
                    "manager": bool(client.manager),
                    "test_account": bool(client.test_account),
                    "status": client.status.name,
                    "currency_code": client.currency_code,
                    "time_zone": client.time_zone,
                }
            )
        return clients

    def weekly_performance_summary(self, customer_id: str) -> dict[str, Any]:
        rows = self._service().search(customer_id=customer_id.replace("-", ""), query=_WEEKLY_QUERY)
        campaigns: list[dict[str, Any]] = []
        for row in rows:
            spend = float(row.metrics.cost_micros or 0) / 1_000_000
            conversions = float(row.metrics.conversions or 0)
            clicks = int(row.metrics.clicks or 0)
            impressions = int(row.metrics.impressions or 0)
            cpa = round(spend / conversions, 2) if conversions else 0.0
            campaigns.append(
                {
                    "campaign": row.campaign.name,
                    "status": row.campaign.status.name,
                    "spend": round(spend, 2),
                    "impressions": impressions,
                    "clicks": clicks,
                    "conversions": int(conversions),
                    "cpa": cpa,
                    "ctr": round(float(row.metrics.ctr or 0) * 100, 2),
                    "recommendation": "Review performance before changing budget." if clicks else "No recent traffic detected.",
                }
            )

        spend = round(sum(float(r["spend"]) for r in campaigns), 2)
        impressions = sum(int(r["impressions"]) for r in campaigns)
        clicks = sum(int(r["clicks"]) for r in campaigns)
        conversions = sum(int(r["conversions"]) for r in campaigns)
        ctr = round((clicks / impressions) * 100, 2) if impressions else 0.0
        cpa = round(spend / conversions, 2) if conversions else 0.0

        return {
            "customer": {"customer_id": customer_id.replace("-", ""), "name": customer_id.replace("-", "")},
            "date_range": "LAST_7_DAYS",
            "metrics": {"spend": spend, "impressions": impressions, "clicks": clicks, "conversions": conversions, "ctr": ctr, "cpa": cpa},
            "campaigns": campaigns,
            "query": _WEEKLY_QUERY,
            "source": "live_google_ads_api",
        }

    def search_terms(self, customer_id: str, campaign_id: str | None = None) -> dict[str, Any]:
        query = _SEARCH_TERMS_QUERY
        if campaign_id:
            query += f"\n  AND campaign.id = {campaign_id}"
        rows = self._service().search(customer_id=customer_id.replace("-", ""), query=query)
        terms: list[dict[str, Any]] = []
        for row in rows:
            spend = float(row.metrics.cost_micros or 0) / 1_000_000
            conversions = float(row.metrics.conversions or 0)
            clicks = int(row.metrics.clicks or 0)
            impressions = int(row.metrics.impressions or 0)
            terms.append(
                {
                    "campaign": row.campaign.name,
                    "campaign_id": str(row.campaign.id),
                    "term": row.search_term_view.search_term,
                    "status": row.search_term_view.status.name,
                    "spend": round(spend, 2),
                    "clicks": clicks,
                    "impressions": impressions,
                    "conversions": int(conversions),
                    "ctr": round(float(row.metrics.ctr or 0) * 100, 2),
                    "cpa": round(spend / conversions, 2) if conversions else None,
                }
            )
        return {"terms": terms, "query": query, "source": "live_google_ads_api"}

    def keyword_performance(self, customer_id: str, campaign_id: str | None = None) -> dict[str, Any]:
        query = _KEYWORD_QUERY
        if campaign_id:
            query += f"\n  AND campaign.id = {campaign_id}"
        rows = self._service().search(customer_id=customer_id.replace("-", ""), query=query)
        keywords: list[dict[str, Any]] = []
        for row in rows:
            spend = float(row.metrics.cost_micros or 0) / 1_000_000
            conversions = float(row.metrics.conversions or 0)
            clicks = int(row.metrics.clicks or 0)
            impressions = int(row.metrics.impressions or 0)
            quality_score = int(row.ad_group_criterion.quality_info.quality_score or 0)
            keywords.append(
                {
                    "campaign": row.campaign.name,
                    "campaign_id": str(row.campaign.id),
                    "ad_group": row.ad_group.name,
                    "keyword_id": str(row.ad_group_criterion.criterion_id),
                    "text": row.ad_group_criterion.keyword.text,
                    "match_type": row.ad_group_criterion.keyword.match_type.name,
                    "status": row.ad_group_criterion.status.name,
                    "quality_score": quality_score,
                    "spend": round(spend, 2),
                    "clicks": clicks,
                    "impressions": impressions,
                    "conversions": int(conversions),
                    "cpa": round(spend / conversions, 2) if conversions else None,
                    "ctr": round(float(row.metrics.ctr or 0) * 100, 2),
                }
            )
        return {"keywords": keywords, "query": query, "source": "live_google_ads_api"}

    def optimization_suggestions(self, customer_id: str) -> dict[str, Any]:
        service = self.client.get_service("RecommendationService")
        resource_name = f"customers/{customer_id.replace('-', '')}"
        response = service.list(customer_id=customer_id.replace("-", ""))
        recs: list[dict[str, Any]] = []
        for rec in response:
            recs.append(
                {
                    "type": rec.type_.name,
                    "impact": rec.impact.base_metrics.impressions if hasattr(rec.impact, "base_metrics") else None,
                    "description": rec.dismissed if hasattr(rec, "dismissed") else str(rec.type_.name),
                    "campaign": rec.campaign.split("/")[-1] if rec.campaign else None,
                }
            )
        return {"recommendations": recs, "source": "live_google_ads_api"}

    def budget_health(self, customer_id: str) -> dict[str, Any]:
        rows = self._service().search(customer_id=customer_id.replace("-", ""), query=_BUDGET_HEALTH_QUERY)
        campaigns: list[dict[str, Any]] = []
        for row in rows:
            daily_budget = float(row.campaign_budget.amount_micros or 0) / 1_000_000
            spent_today = float(row.metrics.cost_micros or 0) / 1_000_000
            utilization = round((spent_today / daily_budget) * 100, 1) if daily_budget else 0.0
            campaigns.append(
                {
                    "campaign": row.campaign.name,
                    "campaign_id": str(row.campaign.id),
                    "status": row.campaign.status.name,
                    "daily_budget": round(daily_budget, 2),
                    "spent_today": round(spent_today, 2),
                    "utilization_pct": utilization,
                    "budget_recommendation": "INCREASE" if utilization > 95 else "MAINTAIN" if utilization > 50 else "REVIEW",
                }
            )
        return {"campaigns": campaigns, "query": _BUDGET_HEALTH_QUERY, "source": "live_google_ads_api"}

    def list_campaigns(self, customer_id: str) -> dict[str, Any]:
        rows = self._service().search(customer_id=customer_id.replace("-", ""), query=_CAMPAIGN_LIST_QUERY)
        campaigns: list[dict[str, Any]] = []
        for row in rows:
            spend = float(row.metrics.cost_micros or 0) / 1_000_000
            conversions = float(row.metrics.conversions or 0)
            daily_budget = float(row.campaign_budget.amount_micros or 0) / 1_000_000
            campaigns.append(
                {
                    "campaign_id": str(row.campaign.id),
                    "campaign": row.campaign.name,
                    "status": row.campaign.status.name,
                    "channel_type": row.campaign.advertising_channel_type.name,
                    "daily_budget": round(daily_budget, 2),
                    "spend_last_7d": round(spend, 2),
                    "clicks": int(row.metrics.clicks or 0),
                    "impressions": int(row.metrics.impressions or 0),
                    "conversions": int(conversions),
                }
            )
        return {"campaigns": campaigns, "query": _CAMPAIGN_LIST_QUERY, "source": "live_google_ads_api"}

    def update_campaign_status(self, customer_id: str, campaign_id: str, status: str) -> dict[str, Any]:
        campaign_service = self.client.get_service("CampaignService")
        campaign_operation = self.client.get_type("CampaignOperation")
        campaign = campaign_operation.update
        campaign.resource_name = campaign_service.campaign_path(customer_id.replace("-", ""), campaign_id)
        campaign.status = self.client.enums.CampaignStatusEnum[status]
        field_mask = self.client.get_type("FieldMask")
        field_mask.paths.append("status")
        campaign_operation.update_mask.CopyFrom(field_mask)
        response = campaign_service.mutate_campaigns(
            customer_id=customer_id.replace("-", ""),
            operations=[campaign_operation],
        )
        return {
            "campaign_id": campaign_id,
            "new_status": status,
            "resource_name": response.results[0].resource_name,
            "source": "live_google_ads_api",
        }

    def update_campaign_budget(self, customer_id: str, campaign_id: str, daily_budget_usd: float) -> dict[str, Any]:
        budget_micros = int(daily_budget_usd * 1_000_000)
        gaql = f"""
        SELECT campaign.id, campaign_budget.id
        FROM campaign
        WHERE campaign.id = {campaign_id}
        """
        rows = list(self._service().search(customer_id=customer_id.replace("-", ""), query=gaql))
        if not rows:
            raise ValueError(f"Campaign {campaign_id} not found for customer {customer_id}")
        budget_id = str(rows[0].campaign_budget.id)

        budget_service = self.client.get_service("CampaignBudgetService")
        budget_operation = self.client.get_type("CampaignBudgetOperation")
        budget = budget_operation.update
        budget.resource_name = budget_service.campaign_budget_path(customer_id.replace("-", ""), budget_id)
        budget.amount_micros = budget_micros
        field_mask = self.client.get_type("FieldMask")
        field_mask.paths.append("amount_micros")
        budget_operation.update_mask.CopyFrom(field_mask)
        response = budget_service.mutate_campaign_budgets(
            customer_id=customer_id.replace("-", ""),
            operations=[budget_operation],
        )
        return {
            "campaign_id": campaign_id,
            "budget_id": budget_id,
            "new_daily_budget_usd": daily_budget_usd,
            "resource_name": response.results[0].resource_name,
            "source": "live_google_ads_api",
        }


def live_google_ads_available() -> bool:
    return GoogleAdsConfig.from_env() is not None
