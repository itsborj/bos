from __future__ import annotations

import httpx

from klaroha_sdk import ArtifactBlock, ChannelModule, RunResult

_ACCOUNTS_URL = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
_INFO_BASE = "https://mybusinessbusinessinformation.googleapis.com/v1"
_READ_MASK = "title,categories,phoneNumbers,regularHours,websiteUri,storefrontAddress,serviceArea,openInfo,metadata"

_TOLL_FREE_PREFIXES = ("800", "888", "877", "866", "855", "844", "833")

_RATINGS = [
    (90, "Excellent"),
    (75, "Good"),
    (50, "Needs Work"),
    (25, "Poor"),
    (0,  "Critical"),
]


async def _get(url: str, token: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        return r.json()


def _api_setup_error(exc: httpx.HTTPStatusError, fallback: str) -> str:
    """Return an operator-actionable setup blocker instead of hiding Google API errors."""
    status_code = exc.response.status_code
    try:
        payload = exc.response.json()
    except Exception:
        payload = {}
    error = payload.get("error") if isinstance(payload, dict) else {}
    details = error.get("details") if isinstance(error, dict) else []
    metadata = {}
    reason = ""
    if isinstance(details, list):
        for item in details:
            if isinstance(item, dict) and item.get("@type", "").endswith("ErrorInfo"):
                metadata = item.get("metadata") or {}
                reason = item.get("reason") or ""
                break

    service = metadata.get("service") or "Google Business Profile API"
    service_title = metadata.get("serviceTitle") or service
    if reason == "SERVICE_DISABLED":
        return f"{service_title} is disabled for this Google Cloud project. Enable {service}, then reconnect Google Business Profile."
    if reason == "RATE_LIMIT_EXCEEDED" and str(metadata.get("quota_limit_value")) == "0":
        return f"{service_title} quota is 0 for this Google Cloud project. Request GBP API access/quota for {service}, then rerun the audit."

    message = error.get("message") if isinstance(error, dict) else ""
    return f"{fallback}: Google API returned HTTP {status_code}. {message}".strip()


async def _find_first_location(token: str) -> tuple[str | None, str | None]:
    try:
        accounts = (await _get(_ACCOUNTS_URL, token)).get("accounts", [])
    except httpx.HTTPStatusError as exc:
        return None, _api_setup_error(exc, "Google Business Profile account lookup failed")

    if not accounts:
        return None, "No Google Business Profile account found for this Google login. Reconnect with an account that manages Klaroha's Business Profile."

    account = accounts[0]["name"]
    try:
        locations = (await _get(f"{_INFO_BASE}/{account}/locations", token, {"readMask": "name"})).get("locations", [])
    except httpx.HTTPStatusError as exc:
        return None, _api_setup_error(exc, "Google Business Profile location lookup failed")

    if not locations:
        return None, "No Google Business Profile location found under the connected GBP account. Confirm this Google account manages a Klaroha Business Profile location."
    return locations[0]["name"], None


def _score_fields(loc: dict) -> list[dict]:
    fields = []

    # 1. Primary category
    primary = (loc.get("categories") or {}).get("primaryCategory")
    if primary:
        fields.append({"name": "Primary category", "status": "present", "points": 1,
                        "note": "Set. Verify it's the most specific subtype for your industry."})
    else:
        fields.append({"name": "Primary category", "status": "missing", "points": 0,
                        "note": "Not set — required for local ranking."})

    # 2. Additional categories
    additional = (loc.get("categories") or {}).get("additionalCategories", [])
    if len(additional) >= 3:
        fields.append({"name": "Additional categories", "status": "optimized", "points": 2,
                        "note": f"{len(additional)} categories set (optimal: 3–5)."})
    elif additional:
        fields.append({"name": "Additional categories", "status": "present", "points": 1,
                        "note": f"{len(additional)} category set. Add {3 - len(additional)} more for full score."})
    else:
        fields.append({"name": "Additional categories", "status": "missing", "points": 0,
                        "note": "No additional categories — add 3–5 relevant ones."})

    # 3. Business name
    title = loc.get("title", "")
    if title:
        fields.append({"name": "Business name", "status": "present", "points": 1,
                        "note": f"\"{title}\" — verify it matches your real-world signage exactly."})
    else:
        fields.append({"name": "Business name", "status": "missing", "points": 0,
                        "note": "No business name found."})

    # 4. Address
    address = loc.get("storefrontAddress") or {}
    address_lines = address.get("addressLines", [])
    has_postal = bool(address.get("postalCode"))
    has_locality = bool(address.get("locality"))
    if address_lines and has_postal and has_locality:
        fields.append({"name": "Physical address", "status": "optimized", "points": 2,
                        "note": "Complete address with street, city, and postal code."})
    elif address_lines:
        fields.append({"name": "Physical address", "status": "present", "points": 1,
                        "note": "Address set but missing city or postal code."})
    else:
        service_area = loc.get("serviceArea")
        if service_area:
            fields.append({"name": "Physical address", "status": "present", "points": 1,
                            "note": "Service-area business — no storefront address (expected)."})
        else:
            fields.append({"name": "Physical address", "status": "missing", "points": 0,
                            "note": "No address or service area set."})

    # 5. Phone number
    phones = loc.get("phoneNumbers") or {}
    primary_phone = phones.get("primaryPhone", "")
    if primary_phone:
        digits = "".join(c for c in primary_phone if c.isdigit())
        is_toll_free = any(digits.startswith(p) or digits.startswith("1" + p) for p in _TOLL_FREE_PREFIXES)
        if is_toll_free:
            fields.append({"name": "Phone number", "status": "present", "points": 1,
                            "note": f"{primary_phone} — toll-free numbers rank lower. Use a local number."})
        else:
            fields.append({"name": "Phone number", "status": "optimized", "points": 2,
                            "note": f"{primary_phone} — local number."})
    else:
        fields.append({"name": "Phone number", "status": "missing", "points": 0,
                        "note": "No phone number set."})

    # 6. Website URL
    website = loc.get("websiteUri", "")
    if website:
        fields.append({"name": "Website URL", "status": "present", "points": 1,
                        "note": f"{website} — verify it points to the most relevant page."})
    else:
        fields.append({"name": "Website URL", "status": "missing", "points": 0,
                        "note": "No website URL set."})

    # 7. Business hours
    periods = (loc.get("regularHours") or {}).get("periods", [])
    days_set = {p.get("openDay") for p in periods if p.get("openDay")}
    all_days = {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"}
    if len(days_set) == 7:
        fields.append({"name": "Business hours", "status": "optimized", "points": 2,
                        "note": "All 7 days configured."})
    elif days_set:
        missing_days = sorted(all_days - days_set)
        fields.append({"name": "Business hours", "status": "present", "points": 1,
                        "note": f"Hours set for {len(days_set)} days. Missing: {', '.join(d.capitalize() for d in missing_days)}."})
    else:
        fields.append({"name": "Business hours", "status": "missing", "points": 0,
                        "note": "No hours set — customers can't see when you're open."})

    # 8. Verified status — not exposed via GBP API
    fields.append({"name": "Verified status", "status": "unknown", "points": 0,
                    "note": "Cannot be determined via API. Check your GBP dashboard for the verified badge."})

    return fields


def _normalize(raw: int, max_pts: int = 16) -> int:
    return round((raw / max_pts) * 100)


def _rating(score: int) -> str:
    for threshold, label in _RATINGS:
        if score >= threshold:
            return label
    return "Critical"


class GbpCompletenessScore(ChannelModule):
    id = "marketing.intelligence.gbp.completeness_score"
    vertical = "marketing"
    capability = "marketing.execute"
    platform_hint = "google_business"

    async def execute(self, brief: dict) -> RunResult:
        creds = brief.get("_channel_credentials", {})
        token = creds.get("page_token") or creds.get("google_business_page_token")
        brand_name = brief.get("brand_name", "Brand")

        if not token:
            block = ArtifactBlock(
                block_type="gbp_completeness_result",
                content={"error": "Google Business Profile not connected. Connect it in Admin → Brands."},
                renderer_hint="setup_blocker",
                allowed_actions=[],
            )
            return RunResult(run_id=brief.get("run_id", ""), status="failed",
                             artifact_blocks=[block], self_check="fail")

        location_name, setup_error = await _find_first_location(token)
        if setup_error or not location_name:
            block = ArtifactBlock(
                block_type="gbp_completeness_result",
                content={"error": setup_error or "No Google Business Profile location found on this account."},
                renderer_hint="setup_blocker",
                allowed_actions=[],
            )
            return RunResult(run_id=brief.get("run_id", ""), status="failed",
                             artifact_blocks=[block], self_check="fail")

        try:
            loc = await _get(f"{_INFO_BASE}/{location_name}", token, {"readMask": _READ_MASK})
        except httpx.HTTPStatusError as exc:
            block = ArtifactBlock(
                block_type="gbp_completeness_result",
                content={"error": _api_setup_error(exc, "Google Business Profile profile read failed")},
                renderer_hint="setup_blocker",
                allowed_actions=[],
            )
            return RunResult(run_id=brief.get("run_id", ""), status="failed",
                             artifact_blocks=[block], self_check="fail")
        except Exception as exc:
            block = ArtifactBlock(
                block_type="gbp_completeness_result",
                content={"error": f"GBP API error: {exc}"},
                renderer_hint="setup_blocker",
                allowed_actions=[],
            )
            return RunResult(run_id=brief.get("run_id", ""), status="failed",
                             artifact_blocks=[block], self_check="fail")

        fields = _score_fields(loc)
        raw = sum(f["points"] for f in fields)
        score = _normalize(raw)
        rating = _rating(score)
        gaps = [f for f in fields if f["status"] in ("missing", "unknown")]

        block = ArtifactBlock(
            block_type="gbp_completeness_result",
            content={
                "brand": brand_name,
                "business_name": loc.get("title", ""),
                "score": score,
                "rating": rating,
                "raw_score": raw,
                "max_score": 16,
                "fields": fields,
                "gap_count": len(gaps),
                "data_source": "Google Business Profile API v1",
                "note": "Scoring covers critical fields only (v0.1). Industry multipliers and supplementary fields not yet included.",
            },
            renderer_hint="approval_bundle",
            allowed_actions=["approve", "dismiss"],
        )

        return RunResult(
            run_id=brief.get("run_id", ""),
            status="pending_review",
            artifact_blocks=[block],
            self_check="pass",
        )
