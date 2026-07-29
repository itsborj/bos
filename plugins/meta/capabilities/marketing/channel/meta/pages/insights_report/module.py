from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule

_GRAPH = "https://graph.facebook.com/v21.0"
_PAGE_FIELDS = "id,name,category,fan_count,followers_count,link,picture.type(normal),instagram_business_account"
_POST_FIELDS = "id,message,story,created_time,permalink_url,likes.summary(true),comments.summary(true),shares"
_DEFAULT_INSIGHT_METRICS = ["page_post_engagements", "page_actions_post_reactions_total", "page_views_total", "page_video_views"]


def _safe_error_body(exc: HTTPError, limit: int = 600) -> str:
    try:
        return exc.read().decode("utf-8", "replace")[:limit]
    except Exception:
        return ""


def _value_number(value) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


class MetaPageInsightsReportModule(ChannelModule):
    id = "marketing.channel.meta.pages.insights.report"
    name = "Meta Page Insights Report"
    vertical = "marketing"
    capability = "marketing.optimize"
    platform_hint = "facebook page insights report"
    policy_default = "read_only"
    template = ""

    max_chars = 0
    must_mention = []
    banned_phrases = []

    def _latency_ms(self, start: float) -> int:
        return round((time.perf_counter() - start) * 1000)

    def _attempt(self, start: float, status: str, error: str | None = None) -> dict:
        return {
            "provider": "meta",
            "model_id": "meta_graph_api_v21",
            "mode": "tool",
            "status": status,
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": self._latency_ms(start),
            "error": error,
        }

    def _failure(self, start: float, reason_code: str, message: str, details: dict | None = None) -> tuple[dict, dict]:
        return self._attempt(start, "failed", reason_code), {
            "content": f"Failed to build Meta page insights report: {message}",
            "sell_price": None,
            "block": {
                "type": "meta_page_insights_report",
                "platform": "facebook",
                "status": "failed",
                "reason_code": reason_code,
                "message": message,
                "details": details or {},
                "read_only": True,
                "changed_resources": [],
            },
        }

    def _creds(self, brief: dict) -> dict:
        raw = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
        return raw if isinstance(raw, dict) else {}

    def _get_json(self, path: str, params: dict) -> dict:
        query = urlencode(params)
        req = Request(f"{_GRAPH}/{path.lstrip('/')}?{query}")
        with urlopen(req, timeout=35) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _optional_get(self, path: str, params: dict, label: str, warnings: list[dict]) -> dict | None:
        try:
            return self._get_json(path, params)
        except HTTPError as exc:
            warnings.append({"scope": label, "http_status": exc.code, "message": _safe_error_body(exc)})
        except URLError as exc:
            warnings.append({"scope": label, "message": f"Network error: {exc}"})
        except Exception as exc:
            warnings.append({"scope": label, "message": str(exc)})
        return None

    def _summarize_insight(self, item: dict) -> dict:
        values = item.get("values") if isinstance(item.get("values"), list) else []
        numeric_values = [_value_number(v.get("value")) for v in values if isinstance(v, dict)]
        numeric_values = [v for v in numeric_values if v is not None]
        latest = values[-1].get("value") if values and isinstance(values[-1], dict) else None
        summary = {
            "name": item.get("name"),
            "title": item.get("title"),
            "description": item.get("description"),
            "period": item.get("period"),
            "value_count": len(values),
            "latest": latest,
        }
        if numeric_values:
            summary["total"] = sum(numeric_values)
            summary["average"] = sum(numeric_values) / len(numeric_values)
        return summary

    def _campaign_candidates(self, brief: dict, intelligence: dict | None = None) -> list[dict]:
        raw = brief.get("_campaign_index") if isinstance(brief.get("_campaign_index"), list) else []
        candidates = []
        terms = " ".join(
            [str(t.get("theme") or "") for t in (intelligence or {}).get("themes", []) if isinstance(t, dict)]
            + [str(a) for a in (intelligence or {}).get("audiences_implied", [])]
        ).lower()
        for item in raw[:12]:
            if not isinstance(item, dict):
                continue
            hay = " ".join(str(item.get(k) or "") for k in ("name", "audience", "message_focus")).lower()
            score = 0
            for token in [t for t in terms.replace("/", " ").replace(",", " ").split() if len(t) >= 5]:
                if token in hay:
                    score += 1
            candidates.append({
                "campaign_id": item.get("campaign_id"),
                "campaign_name": item.get("name"),
                "audience": item.get("audience"),
                "message_focus": item.get("message_focus"),
                "match_score": score,
            })
        return sorted(candidates, key=lambda x: int(x.get("match_score") or 0), reverse=True)

    def _campaign_binding(self, brief: dict, intelligence: dict | None = None) -> dict:
        alignment = brief.get("campaign_alignment") if isinstance(brief.get("campaign_alignment"), dict) else {}
        campaign_id = brief.get("campaign_id") or alignment.get("campaign_id")
        campaign_name = brief.get("campaign_name") or alignment.get("campaign_name")
        candidates = self._campaign_candidates(brief, intelligence)
        if campaign_id:
            return {
                "scope": "campaign_evidence",
                "campaign_id": str(campaign_id),
                "campaign_name": str(campaign_name) if campaign_name else None,
                "candidate_campaigns": candidates[:5],
            }
        if len(candidates) == 1:
            only = candidates[0]
            return {
                "scope": "campaign_candidate",
                "campaign_id": str(only.get("campaign_id")) if only.get("campaign_id") else None,
                "campaign_name": str(only.get("campaign_name")) if only.get("campaign_name") else None,
                "candidate_campaigns": candidates[:5],
            }
        if candidates:
            return {
                "scope": "campaign_candidates",
                "campaign_id": None,
                "campaign_name": None,
                "candidate_campaigns": candidates[:5],
            }
        return {
            "scope": "channel_snapshot",
            "campaign_id": None,
            "campaign_name": None,
            "candidate_campaigns": [],
        }

    def _coverage_summary(
        self,
        *,
        page_data: dict,
        scheduled_posts: list[dict],
        recent_posts: list[dict],
        recent_posts_source: str,
        insight_summaries: list[dict],
        warnings: list[dict],
    ) -> dict:
        warning_scopes = {str(w.get("scope") or "") for w in warnings if isinstance(w, dict)}
        engagement_values = [
            p.get(metric)
            for p in recent_posts
            for metric in ("likes", "comments", "shares")
            if p.get(metric) is not None
        ]
        insights_blocked = any(scope.startswith("insights:") for scope in warning_scopes)
        return {
            "page_profile": {
                "state": "fresh" if page_data else ("blocked" if "page_profile" in warning_scopes else "connected_no_data"),
                "last_read": datetime.now(timezone.utc).isoformat(),
            },
            "scheduled_queue": {
                "state": "blocked" if "scheduled_posts" in warning_scopes else "fresh",
                "count": len(scheduled_posts),
            },
            "recent_post_copy": {
                "state": "fresh" if recent_posts else ("blocked" if "recent_posts_engagement" in warning_scopes else "connected_no_data"),
                "count": len(recent_posts),
                "source": recent_posts_source,
            },
            "recent_posts_engagement": {
                "state": "fresh" if engagement_values else ("blocked" if recent_posts_source == "page_profile_nested_posts_basic" or "recent_posts_engagement" in warning_scopes else "connected_no_data"),
                "metrics_seen": sorted({m for p in recent_posts for m in ("likes", "comments", "shares") if p.get(m) is not None}),
            },
            "page_insights": {
                "state": "fresh" if insight_summaries else ("blocked" if insights_blocked else "connected_no_data"),
                "metrics_seen": [s.get("name") for s in insight_summaries if s.get("name")],
            },
        }

    def _term_matches(self, lowered: str, term: str) -> bool:
        term = term.lower().strip()
        if not term:
            return False
        # Phrases can be matched directly; single words need boundaries so
        # "lead" doesn't fire inside unrelated text and "ai" doesn't fire as
        # two letters inside a longer word.
        if " " in term or "-" in term:
            return term in lowered
        return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", lowered) is not None

    def _text_contains_any(self, text: str, terms: list[str]) -> bool:
        lowered = text.lower()
        return any(self._term_matches(lowered, term) for term in terms)

    def _hits(self, text: str, terms: list[str]) -> int:
        lowered = text.lower()
        return sum(1 for term in terms if self._term_matches(lowered, term))

    def _content_intelligence(self, recent_posts: list[dict], scheduled_posts: list[dict]) -> dict:
        texts = [str(p.get("message") or "") for p in recent_posts if str(p.get("message") or "").strip()]
        # Keep rules broad enough for omni-channel/plugin use, but avoid generic
        # words such as "future" or "plan" creating false vertical-specific
        # readings. The Klaroha page surfaced this: "future of marketing" was
        # incorrectly classified as memorial/family planning.
        theme_rules = [
            ("marketing ops / lead generation", ["marketing", "lead generation", "campaign", "growth", "pipeline", "funnel", "automation", "crm", "conversion"], 1),
            ("intent-to-conversation messaging", ["intent", "conversation", "conversations", "reply", "inbox", "dm"], 1),
            ("family protection / planning ahead", ["family", "families", "loved ones", "protect", "protection", "plan ahead", "planning ahead", "prepared"], 1),
            ("trusted advisor / community connector", ["trusted", "guide", "advisor", "connector", "community", "remember"], 1),
            ("dignity / peace of mind", ["dignity", "peace of mind", "honor", "memorial", "remembered", "respect"], 1),
            ("cost / affordability", ["cost", "afford", "payment", "installment", "budget", "price"], 1),
            ("urgency / availability", ["limited", "today", "now", "reserve", "available"], 1),
        ]
        themes = []
        for label, terms, min_hits in theme_rules:
            count = sum(1 for text in texts if self._hits(text, terms) >= min_hits)
            if count:
                themes.append({"theme": label, "evidence_posts": count})

        audience_rules = [
            ("marketing operators / growth teams", ["marketing", "campaign", "lead generation", "growth", "pipeline", "funnel", "intent", "conversations"]),
            ("family decision-makers", ["family", "families", "parents", "loved ones"]),
            ("community referrers / trusted connectors", ["trusted", "guide", "advisor", "connector", "community"]),
            ("future planners", ["plan ahead", "planning ahead", "prepared", "pre-need"]),
            ("cost-conscious buyers", ["cost", "afford", "payment", "budget", "installment"]),
        ]
        audiences = []
        for label, terms in audience_rules:
            if any(self._text_contains_any(text, terms) for text in texts):
                audiences.append(label)

        cta_terms = ["message", "call", "learn more", "book", "visit", "reserve", "secure", "contact", "inquire", "schedule"]
        cta_posts = sum(1 for text in texts if self._text_contains_any(text, cta_terms))
        if not texts:
            cta_consistency = "No recent readable post copy available."
        elif cta_posts == 0:
            cta_consistency = "No explicit CTA detected in the readable recent post copy."
        elif cta_posts == len(texts):
            cta_consistency = "Most readable posts include an explicit CTA."
        else:
            cta_consistency = f"Mixed CTA usage: {cta_posts} of {len(texts)} readable posts include an explicit CTA."

        return {
            "themes": themes[:5],
            "audiences_implied": audiences[:5],
            "offer_cta_consistency": cta_consistency,
            "scheduled_queue_empty": len(scheduled_posts) == 0,
            "recent_readable_post_count": len(texts),
            "intelligence_type": "content_intelligence_not_performance" if texts else "insufficient_content",
        }

    def _not_available(self, coverage: dict, campaign_binding: dict) -> list[str]:
        missing = []
        if coverage.get("recent_posts_engagement", {}).get("state") != "fresh":
            missing.append("Reliable post-level engagement counts/rates")
        if coverage.get("page_insights", {}).get("state") != "fresh":
            missing.append("Page insights such as reach, impressions, views, or reactions over time")
        missing.append("Lead, message, call, form, or revenue attribution")
        if campaign_binding.get("scope") == "campaign_candidates":
            missing.append("Explicit campaign binding before final campaign evaluation")
        elif campaign_binding.get("scope") not in {"campaign_evidence", "campaign_candidate"}:
            missing.append("Campaign-bound objective/audience/message evaluation")
        return missing

    def _objective_feedback_rows(self, *, campaign_binding: dict, intelligence: dict, coverage: dict, metrics_overview: dict) -> list[dict]:
        objective_anchor = campaign_binding.get("objective_anchor") if isinstance(campaign_binding.get("objective_anchor"), dict) else {}
        if not objective_anchor:
            return []
        reach = "reported" if metrics_overview.get("followers") else "missing"
        engagement_state = coverage.get("recent_posts_engagement", {}).get("state")
        insights_state = coverage.get("page_insights", {}).get("state")
        engagement = "reported" if engagement_state == "fresh" else "missing"
        action = "missing"
        if intelligence.get("scheduled_queue_empty"):
            evaluation = "distribution_gap"
            next_decision = "Queue one objective-aligned Meta post before judging creative strategy."
        elif engagement == "missing" or insights_state != "fresh":
            evaluation = "inconclusive_coverage_missing"
            next_decision = "Refresh Meta insight/engagement permissions so reach, engagement, and action can be evaluated against the objective."
        else:
            evaluation = "partial_support" if reach == "reported" else "inconclusive"
            next_decision = "Persist this signal to the Campaign operating sheet; reserve production changes for weekly synthesis unless the operator approves a draft variant."
        evidence = [
            f"followers={metrics_overview.get('followers', 'not reported')}",
            f"scheduled_posts={metrics_overview.get('scheduled_posts', 'not reported')}",
            f"recent_readable_posts={metrics_overview.get('recent_readable_posts', 'not reported')}",
            f"insight_metrics_reported={metrics_overview.get('insight_metrics_reported', 'not reported')}",
        ]
        return [{
            "objective_anchor": objective_anchor,
            "evidence": evidence,
            "assessment": {
                "reach": reach,
                "engagement": engagement,
                "action": action,
                "objective_evaluation": evaluation,
            },
            "recommended_next_action": next_decision,
            "coverage": "activation_unbound",
            "autopilot": {
                "eligible": True,
                "allowed_without_approval": ["draft_variant", "create_internal_task", "refresh_report"],
                "requires_approval": ["publish", "budget_change", "pause_or_modify_live_campaign"],
            },
        }]

    def _recommended_next_step(self, *, coverage: dict, intelligence: dict, campaign_binding: dict) -> str:
        if coverage.get("page_profile", {}).get("state") == "blocked":
            return "Reconnect Meta or verify page permissions before treating this channel as current Campaign evidence."
        if coverage.get("recent_posts_engagement", {}).get("state") == "blocked" or coverage.get("page_insights", {}).get("state") == "blocked":
            return "Fix Meta insight/engagement permissions, then refresh the report before making performance claims."
        if campaign_binding.get("scope") != "campaign_evidence":
            return "Use this as a channel snapshot; bind the evidence to a campaign before evaluating performance or changing strategy."
        if intelligence.get("scheduled_queue_empty"):
            return "Decide whether Meta should stay quiet today or queue the next approved campaign-bound post."
        return "Persist readable Meta signals to Campaign and reserve creative changes for the weekly production review."

    def _metrics_overview(self, *, page: dict, scheduled_posts: list[dict], recent_posts: list[dict], insight_summaries: list[dict], coverage: dict) -> dict:
        engagement_posts = sum(
            1 for p in recent_posts
            if any(p.get(metric) is not None for metric in ("likes", "comments", "shares"))
        )
        readable_posts = sum(1 for p in recent_posts if str(p.get("message") or "").strip())
        return {
            "followers": page.get("followers"),
            "scheduled_posts": len(scheduled_posts),
            "recent_posts": len(recent_posts),
            "recent_readable_posts": readable_posts,
            "insight_metrics_reported": len(insight_summaries),
            "recent_posts_with_engagement_counts": engagement_posts,
            "coverage_label": "full" if (
                coverage.get("recent_posts_engagement", {}).get("state") == "fresh"
                and coverage.get("page_insights", {}).get("state") == "fresh"
            ) else "partial",
        }

    def _insight_bullets(
        self,
        *,
        campaign_binding: dict,
        intelligence: dict,
        coverage: dict,
        metrics_overview: dict,
        recent_posts: list[dict],
    ) -> list[dict]:
        scope = campaign_binding.get("scope")
        candidates = campaign_binding.get("candidate_campaigns") if isinstance(campaign_binding.get("candidate_campaigns"), list) else []
        candidate_names = [str(c.get("campaign_name")) for c in candidates if isinstance(c, dict) and c.get("campaign_name")]
        campaign_name = campaign_binding.get("campaign_name") or (candidate_names[0] if len(candidate_names) == 1 else " / ".join(candidate_names[:3])) or "the selected campaign"
        anchored = scope in {"campaign_evidence", "campaign_candidate", "campaign_candidates"}
        anchor = campaign_name if anchored else "Unanchored Meta channel snapshot"
        if scope == "campaign_candidates":
            subject = "the candidate campaigns"
            possessive_subject = "The candidate campaigns'"
            prefix = "Before binding this to one campaign,"
        elif anchored:
            subject = campaign_name
            possessive_subject = f"{campaign_name}'s"
            prefix = f"For {campaign_name},"
        else:
            subject = "Meta"
            possessive_subject = "Readable Meta content"
            prefix = ""
        bullets: list[dict] = []

        themes = [t.get("theme") for t in intelligence.get("themes", []) if t.get("theme")]
        if themes:
            bullets.append({
                "insight": (
                    f"Meta copy is clustering around {', '.join(themes[:3])}."
                    if not anchored else
                    f"{prefix} readable Meta copy is clustering around {', '.join(themes[:3])}."
                ),
                "why_it_matters": "This shows message direction and consistency, but not whether the market is responding yet.",
                "evidence": [f"{intelligence.get('recent_readable_post_count', len(recent_posts))} readable recent post(s)"],
                "confidence": "medium" if len(recent_posts) >= 3 else "low",
                "coverage": "post_copy_reported; performance_not_implied",
                "anchor": anchor,
            })

        audiences = intelligence.get("audiences_implied") or []
        if audiences:
            bullets.append({
                "insight": (
                    f"Readable Meta content appears to speak to {', '.join(audiences[:3])}."
                    if not anchored else
                    f"{possessive_subject} readable Meta content appears to speak to {', '.join(audiences[:3])}."
                ),
                "why_it_matters": "Audience-message fit can be reviewed before production, even when engagement metrics are missing.",
                "evidence": ["audience language inferred from recent post copy"],
                "confidence": "medium" if len(audiences) > 1 else "low",
                "coverage": "copy_inference_only",
                "anchor": anchor,
            })

        if intelligence.get("scheduled_queue_empty"):
            bullets.append({
                "insight": (
                    "Meta has no scheduled distribution queued."
                    if not anchored else
                    f"{subject} have no scheduled Meta distribution queued from this page snapshot." if scope == "campaign_candidates" else f"{subject} has no scheduled Meta distribution queued from this page snapshot."
                ),
                "why_it_matters": "If Meta is supposed to maintain presence for this campaign, the next issue is distribution cadence rather than creative strategy.",
                "evidence": ["scheduled_posts: 0"],
                "confidence": "high",
                "coverage": "scheduled_queue_reported",
                "anchor": anchor,
            })

        if metrics_overview.get("insight_metrics_reported", 0) == 0 or coverage.get("recent_posts_engagement", {}).get("state") != "fresh":
            bullets.append({
                "insight": (
                    "This report cannot judge Meta performance yet."
                    if not anchored else
                    f"This report cannot judge the candidate campaigns' Meta performance yet." if scope == "campaign_candidates" else f"This report cannot judge {campaign_name}'s Meta performance yet."
                ),
                "why_it_matters": "Do not call a message, audience, or creative angle a winner/loser until reach, engagement, click, lead, or conversion evidence is present.",
                "evidence": [
                    f"page_insights: {coverage.get('page_insights', {}).get('state')}",
                    f"recent_posts_engagement: {coverage.get('recent_posts_engagement', {}).get('state')}",
                ],
                "confidence": "high",
                "coverage": "performance_coverage_missing_or_partial",
                "anchor": anchor,
            })

        bullets.append({
            "insight": intelligence.get("offer_cta_consistency") or "CTA consistency could not be assessed.",
            "why_it_matters": "CTA consistency affects whether attention can turn into measurable action across channels.",
            "evidence": ["readable recent post copy"],
            "confidence": "medium" if intelligence.get("recent_readable_post_count") else "low",
            "coverage": "copy_reported" if intelligence.get("recent_readable_post_count") else "no_recent_copy",
            "anchor": anchor,
        })

        if scope == "campaign_candidates" and candidate_names:
            bullets.insert(0, {
                "insight": f"This Meta evidence should be reviewed against existing campaigns: {', '.join(candidate_names[:3])}.",
                "why_it_matters": "The report has brand/channel evidence, but the operator should bind it to the campaign whose objective and message focus it is meant to evaluate.",
                "evidence": ["active campaign index available", "campaign_id not explicitly selected"],
                "confidence": "medium",
                "coverage": "campaign_candidates_available_binding_needed",
                "anchor": anchor,
            })
        elif not anchored:
            bullets.insert(0, {
                "insight": "This artifact is not anchored to an existing campaign, so it should not be treated as campaign evaluation.",
                "why_it_matters": "Agency and multi-brand reporting needs campaign binding to connect channel facts to objective, audience, offer, and next decision.",
                "evidence": ["campaign_id: not provided", "no active campaign candidates supplied"],
                "confidence": "high",
                "coverage": "campaign_binding_missing",
                "anchor": anchor,
            })

        return bullets[:6]

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        try:
            if not isinstance(brief, dict):
                return self._failure(start, "invalid_brief", "brief must be a dictionary")
            creds = self._creds(brief)
            token = creds.get("facebook_page_token") or creds.get("page_token") or creds.get("access_token")
            page_id = creds.get("facebook_page_id") or creds.get("page_id")
            page_name = creds.get("facebook_page_name") or creds.get("page_name")
            if not token:
                return self._failure(start, "missing_credentials", "Facebook page token not connected")
            if not page_id:
                return self._failure(start, "missing_credentials", "Facebook page ID not found")

            days = int(brief.get("days") or 28)
            days = max(1, min(days, 90))
            limit = max(1, min(int(brief.get("limit") or 10), 25))
            until_dt = datetime.now(timezone.utc)
            since_dt = until_dt - timedelta(days=days)
            since = int(since_dt.timestamp())
            until = int(until_dt.timestamp())
            warnings: list[dict] = []

            profile_fields = (
                _PAGE_FIELDS
                + f",posts.limit({limit}){{id,message,story,created_time,permalink_url,full_picture}}"
                + f",published_posts.limit({limit}){{id,message,story,created_time,permalink_url,full_picture}}"
            )
            page_data = self._optional_get(page_id, {"fields": profile_fields, "access_token": token}, "page_profile", warnings) or {}
            page = {
                "page_id": page_id,
                "name": page_data.get("name") or page_name,
                "category": page_data.get("category"),
                "followers": page_data.get("fan_count") or page_data.get("followers_count"),
                "url": page_data.get("link") or f"https://www.facebook.com/{page_id}",
                "picture": ((page_data.get("picture") or {}).get("data") or {}).get("url"),
                "ig_business_account_id": (page_data.get("instagram_business_account") or {}).get("id"),
            }

            scheduled_data = self._optional_get(
                f"{page_id}/scheduled_posts",
                {"fields": "id,message,scheduled_publish_time,created_time", "limit": limit, "access_token": token},
                "scheduled_posts",
                warnings,
            ) or {}
            scheduled_posts = [
                {
                    "post_id": p.get("id", ""),
                    "message": p.get("message") or "",
                    "scheduled_publish_time": p.get("scheduled_publish_time"),
                    "created_time": p.get("created_time"),
                }
                for p in scheduled_data.get("data", [])
                if isinstance(p, dict)
            ]

            posts_data = self._optional_get(
                f"{page_id}/posts",
                {"fields": _POST_FIELDS, "limit": limit, "access_token": token},
                "recent_posts_engagement",
                warnings,
            ) or {}
            recent_posts = []
            recent_posts_source = "posts_edge_with_engagement"
            raw_posts = posts_data.get("data", [])
            if not raw_posts:
                # Some connected pages can read Page profile + nested post basics
                # but cannot read the richer /posts engagement edge. Use the
                # readable nested posts so the report still contains real page
                # activity instead of collapsing to "0 recent posts".
                nested_posts = (page_data.get("posts") or {}).get("data") or (page_data.get("published_posts") or {}).get("data") or []
                raw_posts = nested_posts
                recent_posts_source = "page_profile_nested_posts_basic"
            for p in raw_posts:
                if not isinstance(p, dict):
                    continue
                recent_posts.append({
                    "post_id": p.get("id", ""),
                    "message": p.get("message") or p.get("story") or "",
                    "created_time": p.get("created_time", ""),
                    "permalink": p.get("permalink_url"),
                    "image": p.get("full_picture"),
                    "likes": (p.get("likes") or {}).get("summary", {}).get("total_count") if isinstance(p.get("likes"), dict) else None,
                    "comments": (p.get("comments") or {}).get("summary", {}).get("total_count") if isinstance(p.get("comments"), dict) else None,
                    "shares": (p.get("shares") or {}).get("count") if isinstance(p.get("shares"), dict) else None,
                })

            requested_metrics = brief.get("metrics") if isinstance(brief.get("metrics"), list) else _DEFAULT_INSIGHT_METRICS
            insight_summaries = []
            for metric in [str(m).strip() for m in requested_metrics if str(m).strip()][:12]:
                data = self._optional_get(
                    f"{page_id}/insights",
                    {"metric": metric, "period": "day", "since": since, "until": until, "access_token": token},
                    f"insights:{metric}",
                    warnings,
                )
                for item in (data or {}).get("data", []):
                    if isinstance(item, dict):
                        insight_summaries.append(self._summarize_insight(item))

            content_intelligence = self._content_intelligence(recent_posts, scheduled_posts)
            campaign_binding = self._campaign_binding(brief, content_intelligence)
            coverage = self._coverage_summary(
                page_data=page_data,
                scheduled_posts=scheduled_posts,
                recent_posts=recent_posts,
                recent_posts_source=recent_posts_source,
                insight_summaries=insight_summaries,
                warnings=warnings,
            )
            metrics_overview = self._metrics_overview(
                page=page,
                scheduled_posts=scheduled_posts,
                recent_posts=recent_posts,
                insight_summaries=insight_summaries,
                coverage=coverage,
            )
            objective_feedback = self._objective_feedback_rows(
                campaign_binding=campaign_binding,
                intelligence=content_intelligence,
                coverage=coverage,
                metrics_overview=metrics_overview,
            )
            insight_bullets = self._insight_bullets(
                campaign_binding=campaign_binding,
                intelligence=content_intelligence,
                coverage=coverage,
                metrics_overview=metrics_overview,
                recent_posts=recent_posts,
            )
            not_available = self._not_available(coverage, campaign_binding)
            recommended_next_step = self._recommended_next_step(
                coverage=coverage,
                intelligence=content_intelligence,
                campaign_binding=campaign_binding,
            )
            has_blocked = any((v or {}).get("state") == "blocked" for v in coverage.values() if isinstance(v, dict))
            has_full_perf = (
                coverage.get("recent_posts_engagement", {}).get("state") == "fresh"
                and coverage.get("page_insights", {}).get("state") == "fresh"
            )
            coverage_label = "Blocked" if coverage.get("page_profile", {}).get("state") == "blocked" else ("Full" if has_full_perf and not has_blocked else "Partial")

            lines = [f"# Meta Page Insights Report — {page.get('name') or page_id}"]
            lines.append("Read-only report")
            lines.append(f"Coverage: {coverage_label}")
            lines.append(f"Fresh as of: {until_dt.isoformat()}")
            lines.append(f"Scope: {campaign_binding['scope']}")

            lines.append("\nMetrics overview")
            if page.get("followers") is not None:
                lines.append(f"- Followers: {int(page['followers']):,}")
            else:
                lines.append("- Followers: not reported")
            lines.append(f"- Window: last {days} days")
            lines.append(f"- Scheduled posts: {metrics_overview['scheduled_posts']}")
            lines.append(f"- Recent posts available: {metrics_overview['recent_posts']}")
            lines.append(f"- Recent posts with readable copy: {metrics_overview['recent_readable_posts']}")
            lines.append(f"- Insight metrics reported: {metrics_overview['insight_metrics_reported']}")
            lines.append(f"- Posts with engagement counts: {metrics_overview['recent_posts_with_engagement_counts']}")
            lines.append(f"- Recent post source: {recent_posts_source}")
            readable_recent_posts = [p for p in recent_posts if str(p.get("message") or "").strip()]
            if readable_recent_posts:
                lines.append("\nRecent readable activity pulled from Meta:")
                for p in readable_recent_posts[:5]:
                    preview = (p.get("message") or "").replace("\n", " ")
                    lines.append(f"- {(p.get('created_time') or '')[:10]} — {preview[:140]}{'…' if len(preview) > 140 else ''}")
            elif recent_posts:
                lines.append("\nRecent activity pulled from Meta: posts exist, but no readable copy was returned.")

            insight_heading = (
                "Campaign-anchored insights" if campaign_binding["scope"] == "campaign_evidence"
                else "Campaign candidate insights" if campaign_binding["scope"] in {"campaign_candidate", "campaign_candidates"}
                else "Channel insights (not campaign-bound)"
            )
            lines.append(f"\n{insight_heading}")
            for item in insight_bullets:
                lines.append(f"- {item.get('insight')} ({item.get('confidence')} confidence; {item.get('coverage')})")

            if objective_feedback:
                lines.append("\nObjective feedback")
                for row in objective_feedback[:3]:
                    anchor = row.get("objective_anchor") or {}
                    assessment = row.get("assessment") or {}
                    lines.append(f"- Objective: {anchor.get('objective') or 'objective missing'}")
                    lines.append(f"  Evidence: {'; '.join(str(x) for x in (row.get('evidence') or [])[:4])}")
                    lines.append(
                        "  Evaluation: "
                        f"reach={assessment.get('reach')}; engagement={assessment.get('engagement')}; "
                        f"action={assessment.get('action')}; objective={assessment.get('objective_evaluation')}"
                    )
                    lines.append(f"  Next decision: {row.get('recommended_next_action')}")

            lines.append("\nContent intelligence detail")
            if content_intelligence["themes"]:
                lines.append("- Themes in readable copy: " + "; ".join(t["theme"] for t in content_intelligence["themes"]))
            else:
                lines.append("- Themes in readable copy: not enough readable copy to classify")
            if content_intelligence["audiences_implied"]:
                lines.append("- Audiences implied: " + "; ".join(content_intelligence["audiences_implied"]))
            else:
                lines.append("- Audiences implied: not clear from readable copy")
            lines.append(f"- CTA consistency: {content_intelligence['offer_cta_consistency']}")
            lines.append(f"- Scheduled queue empty: {'yes' if content_intelligence['scheduled_queue_empty'] else 'no'}")

            lines.append("\nNot available yet")
            for item in not_available[:6]:
                lines.append(f"- {item}")

            lines.append("\nStrategist next step")
            lines.append(f"- {recommended_next_step}")

            if warnings:
                lines.append("\nWarnings")
                for w in warnings[:5]:
                    lines.append(f"- {w.get('scope')}: {w.get('message', '')[:160]}")

            block = {
                "type": "meta_page_insights_report",
                "platform": "facebook",
                "status": "succeeded",
                "display_title": f"Meta Insight Report · {page.get('name') or page_id}",
                "report_scope": campaign_binding["scope"],
                "campaign_binding": campaign_binding,
                "coverage_label": coverage_label.lower(),
                "coverage": coverage,
                "metrics_overview": metrics_overview,
                "insight_heading": insight_heading,
                "insight_bullets": insight_bullets,
                "objective_feedback": objective_feedback,
                "page": page,
                "window": {"days": days, "since": since_dt.isoformat(), "until": until_dt.isoformat()},
                "insights": insight_summaries,
                "recent_posts": recent_posts,
                "recent_posts_source": recent_posts_source,
                "scheduled_posts": scheduled_posts,
                "content_intelligence": content_intelligence,
                "not_available": not_available,
                "recommended_next_step": recommended_next_step,
                "campaign_signal": {
                    "channel": "meta",
                    "scope": campaign_binding["scope"],
                    "campaign_id": campaign_binding.get("campaign_id"),
                    "summary": (objective_feedback[0].get("recommended_next_action") if objective_feedback else None) or (insight_bullets[0]["insight"] if insight_bullets else recommended_next_step),
                    "recommended_next_step": recommended_next_step,
                    "objective_feedback": objective_feedback[:3],
                    "coverage_label": coverage_label.lower(),
                    "fresh_as_of": until_dt.isoformat(),
                },
                "warnings": warnings,
                "read_only": True,
                "changed_resources": [],
                "allowed_actions": ["dismiss"],
            }
            return self._attempt(start, "succeeded"), {"content": "\n".join(lines), "sell_price": None, "block": block}

        except Exception as exc:
            return self._failure(start, "api_call_failed", "Unexpected error building Meta page insights report", {"error": str(exc)})

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures = []
        if not isinstance(content, str) or "Meta Page Insights Report" not in content:
            failures.append("missing_report_content")
        return ("fail" if failures else "pass"), failures
