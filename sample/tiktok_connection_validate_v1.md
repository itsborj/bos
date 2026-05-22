# TikTok Connection Validation — Sample Output v1

## Purpose

Validate that Klaroha BOS is connected to the brand's TikTok account without publishing, uploading, scheduling, or changing anything.

This is the first TikTok connector proof. It confirms OAuth/token health and account identity only. A public test post is a separate approval-gated capability because TikTok posting requires a real video asset and Content Posting API permissions.

---

## Allowed outcome — connected

**User intent:** "Test my TikTok connection" or "Verify Klaroha is connected to our TikTok account."

**Artifact/block:** `tiktok_connection_check`

```json
{
  "type": "tiktok_connection_check",
  "platform": "tiktok",
  "status": "succeeded",
  "read_only": true,
  "account": {
    "open_id": "real_tiktok_open_id_from_api",
    "display_name": "Klaroha",
    "username": "@klaroha",
    "avatar_url": "https://...",
    "profile_url": "https://www.tiktok.com/@klaroha"
  },
  "api_check": {
    "endpoint": "user/info",
    "checked_at": "2026-05-22T00:00:00Z"
  },
  "test_post_readiness": {
    "can_read_account": true,
    "can_prepare_test_post_draft": true,
    "can_publish_public_test_post": false,
    "publish_blocker": "Publishing requires explicit approval, an attached video asset, and approved TikTok Content Posting API scopes."
  },
  "changed_resources": [],
  "allowed_actions": ["view_account", "create_test_post_draft", "dismiss"]
}
```

Visible CMO summary may say:

```text
TikTok connection validated.
Account: @klaroha
No TikTok resources were changed.
```

---

## Allowed outcome — connected but publish not ready

**Artifact/block:** `tiktok_connection_check`

```json
{
  "type": "tiktok_connection_check",
  "platform": "tiktok",
  "status": "partial",
  "read_only": true,
  "account": {
    "open_id": "real_tiktok_open_id_from_api",
    "display_name": "Klaroha",
    "username": "@klaroha"
  },
  "api_check": {
    "endpoint": "user/info",
    "checked_at": "2026-05-22T00:00:00Z"
  },
  "test_post_readiness": {
    "can_read_account": true,
    "can_prepare_test_post_draft": true,
    "can_publish_public_test_post": false,
    "publish_blocker": "TikTok Content Posting API scope is not approved or not present on this token. Manual export remains available."
  },
  "changed_resources": [],
  "allowed_actions": ["create_test_post_draft", "manual_export", "dismiss"]
}
```

Visible CMO summary may say:

```text
TikTok is connected for read checks.
Public posting is not ready yet.
I can prepare a test post draft for manual export.
```

---

## Allowed outcome — blocked/missing setup

**Artifact/block:** `tiktok_connection_check`

```json
{
  "type": "tiktok_connection_check",
  "platform": "tiktok",
  "status": "failed",
  "reason_code": "missing_credentials",
  "message": "TikTok OAuth access token is not connected for this brand.",
  "read_only": true,
  "changed_resources": [],
  "allowed_actions": ["connect_tiktok", "retry", "dismiss"]
}
```

Visible CMO summary may say:

```text
TikTok is not connected for this brand yet.
Connect TikTok first, then I can validate it.
```

---

## Optional next artifact — pending test post draft

This is allowed only after connection validation succeeds and the user asks for a test post draft.

**Artifact/block:** `tiktok_test_post_draft`

```json
{
  "type": "tiktok_test_post_draft",
  "platform": "tiktok",
  "status": "pending_review",
  "caption": "Testing Klaroha BOS TikTok connection. This post was prepared by Klaroha and is pending approval.",
  "video_asset": {
    "required": true,
    "status": "missing",
    "message": "TikTok test posts require an attached video asset before publishing."
  },
  "risk_policy": "draft_only_until_approved",
  "changed_resources": [],
  "allowed_actions": ["attach_video", "revise_caption", "manual_export", "dismiss"]
}
```

Visible CMO summary may say:

```text
I prepared a TikTok test post draft.
Attach a video before publishing or export it manually.
```

---

## Forbidden outcomes

- Do not publish a public TikTok post during connection validation.
- Do not upload a video while validating the connection.
- Do not schedule, delete, comment, follow, unfollow, like, or modify TikTok resources.
- Do not create TikTok ad campaigns, ad groups, pixels, budgets, audiences, or spend changes.
- Do not claim validation succeeded unless TikTok returned real account/profile data.
- Do not return fake `open_id`, username, profile URL, permission state, or post URL.
- Do not use workspace-wide credentials when an active Brand is set.
- Do not create `brand_id=NULL` TikTok artifacts in a multi-brand workspace.
- Do not paste final TikTok content inline in CMO chat as the canonical artifact; use Workspace/Stream artifacts.
- Do not treat a draft as published or an export as a live TikTok post.

---

## V1 implementation boundary

V1 capability:

```text
marketing.channel.tiktok.connection.validate
```

V1 output contract:

```text
tiktok_connection_check
```

V1 risk policy:

```text
read_only
```

Future capabilities, after this sample is approved:

```text
marketing.channel.tiktok.post.draft     # draft/manual export
marketing.channel.tiktok.post.publish   # approval-gated, requires video + posting scopes
```
