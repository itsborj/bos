from __future__ import annotations

import importlib.util
from pathlib import Path

from registry import list_all
from skills.router import route_chat_skills


PLUGIN_ROOT = Path(__file__).resolve().parents[1]

OVERVIEW = "marketing.channel.search_console.specialist.overview"
PROPERTIES = "marketing.channel.search_console.properties.list"
PERFORMANCE = "marketing.channel.search_console.performance.query"
URL_INSPECT = "marketing.channel.search_console.url.inspect"
SITEMAPS = "marketing.channel.search_console.sitemaps.read"
OPPORTUNITIES = "marketing.channel.search_console.opportunities.plan"


def _load(path: str, module_name: str, class_name: str):
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)()


def test_search_console_capabilities_load_in_registry():
    modules = {item["id"] for item in list_all()}

    assert OVERVIEW in modules
    assert PROPERTIES in modules
    assert PERFORMANCE in modules
    assert URL_INSPECT in modules
    assert SITEMAPS in modules
    assert OPPORTUNITIES in modules


def test_search_console_specialist_overview_result_is_read_only():
    module = _load(
        "capabilities/marketing/channel/search_console/specialist/overview/module.py",
        "search_console_specialist_overview_module",
        "SearchConsoleSpecialistOverviewModule",
    )
    _attempt, result = module.execute_tool_result({})
    verdict, failures = module.self_check(result["content"], {})

    assert result["block"]["type"] == "search_console_capability_card"
    assert result["block"]["read_only"] is True
    assert "GOOGLE_SEARCH_CONSOLE_DEFAULT_SITE_URL" in result["content"]
    assert verdict == "pass"
    assert failures == []


def test_search_console_property_request_routes_to_properties_only():
    list_all()
    routed = route_chat_skills("check search console properties")

    assert PROPERTIES in routed.module_ids
    assert PERFORMANCE not in routed.module_ids


def test_search_console_performance_request_routes_to_performance():
    list_all()
    routed = route_chat_skills("show search console performance for last 28 days")

    assert PERFORMANCE in routed.module_ids
    assert PROPERTIES not in routed.module_ids


def test_search_console_url_inspection_routes_to_url_inspect():
    list_all()
    routed = route_chat_skills("inspect url https://www.example.com/page in search console")

    assert URL_INSPECT in routed.module_ids


def test_search_console_sitemap_request_routes_to_sitemaps_read():
    list_all()
    routed = route_chat_skills("check my search console sitemaps")

    assert SITEMAPS in routed.module_ids


def test_search_console_opportunity_request_routes_to_opportunity_plan():
    list_all()
    routed = route_chat_skills("find organic search opportunities from search console")

    assert OPPORTUNITIES in routed.module_ids


def test_properties_parser_returns_read_only_inventory():
    module = _load(
        "capabilities/marketing/channel/search_console/properties/list/module.py",
        "search_console_properties_list_module",
        "SearchConsolePropertiesListModule",
    )
    rows = module._properties({"siteEntry": [{"siteUrl": "sc-domain:example.com", "permissionLevel": "siteOwner"}]})
    content = module._content(rows, "sc-domain:example.com")
    verdict, failures = module.self_check(content, {})

    assert rows == [{"site_url": "sc-domain:example.com", "permission_level": "siteOwner", "property_type": "domain"}]
    assert "Read-only note" in content
    assert verdict == "pass"
    assert failures == []


def test_performance_rows_and_totals_shape():
    module = _load(
        "capabilities/marketing/channel/search_console/performance/query/module.py",
        "search_console_performance_query_module",
        "SearchConsolePerformanceQueryModule",
    )
    data = {"rows": [{"keys": ["motorcycle financing"], "clicks": 42, "impressions": 8800, "ctr": 0.0048, "position": 8.9}]}
    rows = module._rows(data, "query")
    totals = module._totals({"rows": [{"clicks": 42, "impressions": 8800, "ctr": 0.0048, "position": 8.9}]}, rows, [])

    assert rows[0]["signal"] == "ctr_opportunity"
    assert rows[0]["ctr"] == 0.48
    assert totals == {"clicks": 42, "impressions": 8800, "ctr": 0.48, "average_position": 8.9}


def test_url_inspection_extracts_url_from_context():
    module = _load(
        "capabilities/marketing/channel/search_console/url/inspect/module.py",
        "search_console_url_inspect_module",
        "SearchConsoleUrlInspectModule",
    )

    assert module._inspection_url({"conversation_context": "inspect https://www.example.com/page, please"}) == "https://www.example.com/page"


def test_sitemap_parser_returns_read_only_report_rows():
    module = _load(
        "capabilities/marketing/channel/search_console/sitemaps/read/module.py",
        "search_console_sitemaps_read_module",
        "SearchConsoleSitemapsReadModule",
    )
    rows = module._sitemaps({"sitemap": [{"path": "https://www.example.com/sitemap.xml", "errors": 0, "warnings": 0, "contents": [{"submitted": 10, "indexed": 9}]}]})
    content = module._content("sc-domain:example.com", rows)
    verdict, failures = module.self_check(content, {})

    assert rows[0]["submitted"] == 10
    assert rows[0]["indexed"] == 9
    assert rows[0]["signal"] == "healthy"
    assert verdict == "pass"
    assert failures == []


def test_opportunity_builder_flags_low_ctr_and_page_two_queries():
    module = _load(
        "capabilities/marketing/channel/search_console/opportunities/plan/module.py",
        "search_console_opportunities_plan_module",
        "SearchConsoleOpportunitiesPlanModule",
    )
    opps = module._opportunities([
        {"query": "motorcycle financing", "clicks": 42, "impressions": 8800, "ctr": 0.48, "position": 8.9},
        {"query": "beginner motorcycles", "clicks": 20, "impressions": 5200, "ctr": 0.38, "position": 13.4},
    ], [])

    assert opps[0]["type"] == "low_ctr_high_impression_query"
    assert opps[0]["auto_apply"] is False
    assert opps[0]["requires_site_change"] is True
