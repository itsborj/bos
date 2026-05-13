from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "meta_demo.json"


class MockMetaMcpConnector:
    """Fixture-backed stand-in for a local Meta MCP sidecar.

    This intentionally starts read-only: ad account performance, Page posts, and
    unresolved Page comments. Write actions stay behind future native/API or
    explicit approved-action connector paths.
    """

    def __init__(self, fixture_path: Path | None = None) -> None:
        self.fixture_path = fixture_path or _FIXTURE_PATH
        self.data = json.loads(self.fixture_path.read_text())

    def list_ad_accounts(self) -> list[dict[str, Any]]:
        return list(self.data.get("ad_accounts", []))

    def get_campaign_insights(self, account_id: str, date_range: str = "LAST_7_DAYS") -> list[dict[str, Any]]:
        return [
            row for row in self.data.get("campaigns", [])
            if str(row.get("account_id")) == str(account_id)
            and row.get("date_range") == date_range
        ]

    def list_pages(self) -> list[dict[str, Any]]:
        return list(self.data.get("pages", []))

    def list_page_posts(self, page_id: str) -> list[dict[str, Any]]:
        return [row for row in self.data.get("posts", []) if str(row.get("page_id")) == str(page_id)]

    def list_page_comments(self, page_id: str, status: str | None = None) -> list[dict[str, Any]]:
        rows = [row for row in self.data.get("comments", []) if str(row.get("page_id")) == str(page_id)]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return rows


def paid_ads_performance_summary(account_id: str = "act_1122334455") -> dict[str, Any]:
    connector = MockMetaMcpConnector()
    accounts = connector.list_ad_accounts()
    account = next((a for a in accounts if str(a.get("account_id")) == str(account_id)), accounts[0])
    rows = connector.get_campaign_insights(str(account["account_id"]))

    spend = round(sum(float(r.get("spend", 0)) for r in rows), 2)
    impressions = int(sum(int(r.get("impressions", 0)) for r in rows))
    clicks = int(sum(int(r.get("clicks", 0)) for r in rows))
    conversions = int(sum(int(r.get("conversions", 0)) for r in rows))
    ctr = round((clicks / impressions) * 100, 2) if impressions else 0.0
    cpa = round(spend / conversions, 2) if conversions else 0.0

    return {
        "account": account,
        "date_range": "LAST_7_DAYS",
        "metrics": {
            "spend": spend,
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "ctr": ctr,
            "cpa": cpa,
        },
        "campaigns": rows,
        "source": "mock_meta_mcp",
    }


def page_attention_summary(page_id: str = "9988776655") -> dict[str, Any]:
    connector = MockMetaMcpConnector()
    pages = connector.list_pages()
    page = next((p for p in pages if str(p.get("page_id")) == str(page_id)), pages[0])
    posts = connector.list_page_posts(str(page["page_id"]))
    comments = connector.list_page_comments(str(page["page_id"]), status="unresolved")
    counts = Counter(str(row.get("classification", "unknown")) for row in comments)

    return {
        "page": page,
        "date_range": "CURRENT_UNRESOLVED",
        "metrics": {
            "posts_reviewed": len(posts),
            "unresolved_comments": len(comments),
            "buying_intent": counts.get("buying_intent", 0),
            "support_risk": counts.get("support_risk", 0),
            "spam": counts.get("spam", 0),
        },
        "posts": posts,
        "comments": comments,
        "source": "mock_meta_mcp",
    }
