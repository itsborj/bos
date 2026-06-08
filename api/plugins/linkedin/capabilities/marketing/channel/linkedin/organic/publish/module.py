from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule


class LinkedInOrganicPublishModule(ChannelModule):
    id = "marketing.channel.linkedin.organic.publish"
    name = "LinkedIn Organic Post Publish"
    vertical = "marketing"
    capability = "marketing.copywriting"
    platform_hint = "linkedin"
    policy_default = "publish_requires_explicit_approval"
    template = "marketing/channel/linkedin/organic/publish/template.j2"

    max_chars = 3000
    must_mention = []
    banned_phrases = []

    def _creds(self, brief: dict) -> dict:
        raw = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
        return raw if isinstance(raw, dict) else {}

    def _token(self, creds: dict) -> str:
        return str(
            creds.get("linkedin_access_token")
            or creds.get("linkedin_page_token")
            or creds.get("access_token")
            or ""
        ).strip()

    def _org_id(self, creds: dict) -> str:
        return str(
            creds.get("linkedin_organization_id")
            or creds.get("linkedin_page_id")
            or creds.get("organization_id")
            or ""
        ).strip()

    def _post_content(self, brief: dict) -> str:
        return str(
            brief.get("message")
            or brief.get("post_content")
            or brief.get("linkedin_post")
            or brief.get("content")
            or ""
        ).strip()

    def _attempt(self, status: str, error: str | None = None, latency_ms: int = 0) -> dict:
        return {
            "provider": "linkedin",
            "model_id": "ugc_posts_api_v2",
            "mode": "tool",
            "status": status,
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": latency_ms,
            "error": error,
        }

    def _failure(self, reason_code: str, message: str, latency_ms: int = 0) -> tuple[dict, dict]:
        content = (
            f"Failed to publish LinkedIn post.\n\n"
            f"Reason: {message}\n"
            "Mutation: none — post was not created or scheduled."
        )
        return self._attempt("failed", reason_code, latency_ms), {
            "content": content,
            "sell_price": None,
            "block": {
                "type": "linkedin_publish_result",
                "platform": "linkedin",
                "status": "failed",
                "reason_code": reason_code,
                "message": message,
                "post_id": None,
                "post_url": None,
                "read_only": False,
                "changed_resources": [],
                "allowed_actions": ["retry", "dismiss"],
                "risk_policy": "publish_requires_explicit_approval",
            },
        }

    def _get_person_sub(self, token: str) -> str:
        try:
            req = Request(
                "https://api.linkedin.com/v2/userinfo",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                method="GET",
            )
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return str(data.get("sub") or "").strip()
        except Exception:
            return ""

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        t_start = time.perf_counter()
        try:
            if not isinstance(brief, dict):
                return self._failure("invalid_brief", "brief must be a dictionary")

            creds = self._creds(brief)
            token = self._token(creds)
            if not token:
                return self._failure("missing_credentials", "LINKEDIN_ACCESS_TOKEN is not configured for this deployment")

            message = self._post_content(brief)
            if not message:
                return self._failure("missing_content", "No post content found in brief — include 'message' or 'post_content'")

            if len(message) > self.max_chars:
                return self._failure(
                    "content_exceeds_limit",
                    f"Post is {len(message)} characters — LinkedIn limit is {self.max_chars}",
                )

            org_id = self._org_id(creds)
            if org_id:
                author_urn = f"urn:li:organization:{org_id}"
            else:
                sub = self._get_person_sub(token)
                if not sub:
                    return self._failure(
                        "author_resolution_failed",
                        "Could not resolve LinkedIn author identity. Provide LINKEDIN_ORGANIZATION_ID or verify token has 'openid profile' scopes.",
                    )
                author_urn = f"urn:li:person:{sub}"

            post_body = json.dumps({
                "author": author_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": message},
                        "shareMediaCategory": "NONE",
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                },
            }).encode("utf-8")

            req = Request(
                "https://api.linkedin.com/v2/ugcPosts",
                data=post_body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "X-Restli-Protocol-Version": "2.0.0",
                },
                method="POST",
            )

            latency_ms = 0
            try:
                with urlopen(req, timeout=30) as resp:
                    latency_ms = round((time.perf_counter() - t_start) * 1000)
                    raw_id = resp.headers.get("X-LinkedIn-Id") or resp.headers.get("x-linkedin-id") or ""
                    try:
                        body = json.loads(resp.read().decode("utf-8"))
                        post_id = raw_id or str(body.get("id") or "").strip()
                    except Exception:
                        post_id = raw_id

            except HTTPError as exc:
                latency_ms = round((time.perf_counter() - t_start) * 1000)
                if exc.code == 401:
                    return self._failure("token_expired_or_invalid", "LinkedIn returned 401 — token may be expired or missing write scopes (w_member_social or rw_organization_social)", latency_ms)
                if exc.code == 403:
                    return self._failure("insufficient_permissions", f"LinkedIn returned 403 — token lacks required publish scopes for {author_urn}", latency_ms)
                if exc.code == 422:
                    return self._failure("invalid_post_content", "LinkedIn returned 422 — post content failed platform validation", latency_ms)
                return self._failure("api_error", f"LinkedIn API returned HTTP {exc.code}", latency_ms)
            except URLError as exc:
                latency_ms = round((time.perf_counter() - t_start) * 1000)
                return self._failure("network_error", f"Network error calling LinkedIn API: {exc.reason}", latency_ms)

            post_url = f"https://www.linkedin.com/feed/update/{post_id}/" if post_id else None
            content = (
                f"Published to LinkedIn.\n\n"
                f"Post ID: {post_id or 'unknown'}\n"
                f"Author: {author_urn}\n"
                f"Characters: {len(message)}\n"
                "Mutation: post created on LinkedIn."
            )

            return self._attempt("succeeded", latency_ms=latency_ms), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "linkedin_publish_result",
                    "platform": "linkedin",
                    "status": "published",
                    "post_id": post_id or None,
                    "post_url": post_url,
                    "author_urn": author_urn,
                    "character_count": len(message),
                    "read_only": False,
                    "changed_resources": [{"type": "linkedin_post", "id": post_id}] if post_id else [{"type": "linkedin_post", "id": "unknown"}],
                    "allowed_actions": ["dismiss"],
                    "risk_policy": "publish_requires_explicit_approval",
                },
            }

        except Exception as exc:
            latency_ms = round((time.perf_counter() - t_start) * 1000)
            return self._failure("publish_exception", f"Unexpected error: {exc}", latency_ms)

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        try:
            lowered = (content or "").lower()
            if "published to linkedin" not in lowered and "failed to publish linkedin post" not in lowered:
                failures.append("missing_publish_status_summary")
            if "mutation:" not in lowered:
                failures.append("missing_mutation_declaration")
        except Exception:
            failures.append("self_check_exception")
        return ("fail" if failures else "pass", failures)
