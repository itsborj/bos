# Meta Plugin

BOS channel plugin for Meta platforms: Facebook Pages, Instagram Business, and Meta Ads.

Plugin root: `api/plugins/meta/`

All capabilities live under `capabilities/marketing/channel/meta/`. The plugin expands incrementally by phase — adding a new capability directory and updating `capability_ids` in `channel.json` is all that is needed.

---

## Phased capability roadmap

| Phase | Capability ID | Job | Artifact type | Output contract | Mutates Meta? |
|---|---|---|---|---|---|
| 1 | `marketing.channel.meta.pages.read` | `marketing.optimize` | `intelligence_artifact` | `meta_page_inventory` | No |
| 1 | `marketing.channel.meta.posts.read` | `marketing.optimize` | `intelligence_artifact` | `meta_page_posts` | No |
| 1 | `marketing.channel.meta.posts.draft` | `marketing.execute` | `draft_artifact` | `fb_page_post_draft` | No |
| 1 | `marketing.channel.meta.posts.publish` | `marketing.execute` | `action_artifact` | `fb_page_post_result` | **Yes — approval-gated** |
| 2 | `marketing.channel.meta.comments.read` | `marketing.optimize` | `intelligence_artifact` | `meta_comment_intelligence` | No |
| 2 | `marketing.channel.meta.comments.respond` | `marketing.execute` | `action_artifact` | `meta_comment_response_result` | **Yes — approval-gated** |
| 3 | `marketing.channel.meta.instagram.posts.draft` | `marketing.execute` | `draft_artifact` | `ig_post_draft` | No |
| 3 | `marketing.channel.meta.instagram.posts.publish` | `marketing.execute` | `action_artifact` | `ig_post_result` | **Yes — approval-gated** |
| 4 | `marketing.channel.meta.ads.campaigns.read` | `marketing.optimize` | `intelligence_artifact` | `meta_ads_campaign_report` | No |
| 4 | `marketing.channel.meta.ads.performance.read` | `marketing.optimize` | `intelligence_artifact` | `meta_ads_data_pull` | No |

CMO-facing jobs: `marketing.optimize`, `marketing.execute`

---

## OAuth architecture

Meta OAuth is different from Google. The flow produces **Page Access Tokens**, not user tokens — and a Page Access Token is what grants access to both a Facebook Page and its linked Instagram Business Account.

### Token acquisition flow

```
1. User authorizes → short-lived User Access Token
2. Exchange for long-lived User Access Token (60 days, via client_secret)
3. GET /me/accounts → list of Pages + Page Access Tokens (never expire while the Page is connected)
4. For each Page, GET /{page_id}?fields=instagram_business_account → linked IG account ID
5. Store: page_access_token, page_id, page_name, ig_business_account_id (if present)
```

Page Access Tokens do not expire as long as the user's connection to the Page remains active. No refresh cycle is needed unless the user revokes access.

### Scopes — Phase 1 (Pages)

```
pages_show_list
pages_read_engagement
pages_manage_posts
pages_read_user_content
```

### Scopes — Phase 3 (add for Instagram)

```
instagram_basic
instagram_content_publish
instagram_manage_comments
```

Do not request Instagram scopes in Phase 1. Scope creep in the OAuth consent screen degrades user trust and can fail app review.

### Credential injection

Declared in `channel.json` as `requires_social_connection: ["facebook"]`.

BOS injects into `brief["_channel_credentials"]`:

```python
creds = brief.get("_channel_credentials", {})
page_token   = creds.get("facebook_page_token")   # Page Access Token
page_id      = creds.get("facebook_page_id")       # Facebook Page ID (string)
page_name    = creds.get("facebook_page_name")     # Human-readable Page name
ig_account   = creds.get("facebook_ig_account_id") # Instagram Business Account ID (Phase 3+)
```

Phase 4 (Ads) requires a different credential path — ad account token — which is separate from the Page Access Token. That will be handled by a dedicated credential key or a second `requires_social_connection` entry. Do not mix ad account credentials with page credentials.

### OAuth handler

A `FacebookOAuthHandler` must be added to `api/provider_auth.py`. It follows the same interface as `GmailOAuthHandler` but:
- Auth endpoint: `https://www.facebook.com/dialog/oauth`
- Token endpoint: `https://graph.facebook.com/oauth/access_token`
- Long-lived token exchange: `GET /oauth/access_token?grant_type=fb_exchange_token&...`
- Page selection step: after OAuth callback, call `/me/accounts` and present pages to the user (same pattern as `SelectPageRequest` already defined in `social.py`)

The `social.py` router already has `SelectPageRequest` defined but unused. The Facebook callback must drive a page-selection UI step before storing the final connection.

---

## Capability directory structure

```
capabilities/
└── marketing/
    └── channel/
        └── meta/
            ├── pages/
            │   └── read/
            │       ├── module.py
            │       ├── template.j2     (not used — execute_tool_result pattern)
            │       └── SKILL.md
            ├── posts/
            │   ├── read/
            │   ├── draft/
            │   └── publish/
            ├── comments/               (Phase 2)
            │   ├── read/
            │   └── respond/
            ├── instagram/              (Phase 3)
            │   └── posts/
            │       ├── draft/
            │       └── publish/
            └── ads/                    (Phase 4)
                ├── campaigns/
                │   └── read/
                └── performance/
                    └── read/
```

All Phase 1 capabilities use execution pattern B (`execute_tool_result`) — they call the Graph API directly and return structured artifact blocks. No LLM generation needed for read/publish actions. `posts/draft` uses pattern A (LLM generates the post copy via template).

---

## Routing contract

| User asks | Expected capability | Expected artifact | Notes |
|---|---|---|---|
| `show my facebook pages` | `meta.pages.read` | `meta_page_inventory` | Lists connected pages |
| `what did I post on facebook` | `meta.posts.read` | `meta_page_posts` | Recent posts from connected page |
| `draft a facebook post` | `meta.posts.draft` | `fb_page_post_draft` | LLM-drafted post, no API mutation |
| `write a post for my page` | `meta.posts.draft` | `fb_page_post_draft` | Same |
| `publish this to facebook` | `meta.posts.publish` | `fb_page_post_result` | Approval-gated; requires explicit confirm |
| `show facebook comments` | `meta.comments.read` | `meta_comment_intelligence` | Phase 2 |
| `reply to that comment` | `meta.comments.respond` | `meta_comment_response_result` | Phase 2, approval-gated |
| `draft an instagram post` | `meta.instagram.posts.draft` | `ig_post_draft` | Phase 3 |
| `show meta ads performance` | `meta.ads.performance.read` | `meta_ads_data_pull` | Phase 4 |

---

## Output shapes

### `meta_page_inventory` (pages/read)

```json
{
  "type": "meta_page_inventory",
  "platform": "facebook",
  "pages": [
    {
      "page_id": "9988776655",
      "name": "Klaroha HQ",
      "category": "Software Company",
      "followers": 1240,
      "ig_business_account_id": "17841400455324"
    }
  ],
  "read_only": true,
  "changed_resources": []
}
```

### `fb_page_post_draft` (posts/draft)

```json
{
  "type": "fb_page_post_draft",
  "platform": "facebook",
  "page_id": "9988776655",
  "page_name": "Klaroha HQ",
  "message": "Big news — our new integration is live! ...",
  "link": null,
  "image_prompt": null,
  "status": "draft",
  "allowed_actions": ["revise", "dismiss", "approve", "publish"],
  "risk_policy": "draft_only_until_approved"
}
```

### `fb_page_post_result` (posts/publish)

```json
{
  "type": "fb_page_post_result",
  "platform": "facebook",
  "status": "succeeded",
  "post_id": "9988776655_123456789",
  "page_id": "9988776655",
  "message_preview": "Big news — our new integration is live! ...",
  "permalink": "https://www.facebook.com/permalink/9988776655/pfbid...",
  "published_at": "2026-05-18T10:30:00Z",
  "changed_resources": ["9988776655_123456789"]
}
```

### `meta_page_posts` (posts/read)

```json
{
  "type": "meta_page_posts",
  "platform": "facebook",
  "page_id": "9988776655",
  "page_name": "Klaroha HQ",
  "posts": [
    {
      "post_id": "9988776655_111",
      "message": "First post ...",
      "created_time": "2026-05-15T08:00:00Z",
      "likes": 42,
      "comments": 7,
      "shares": 3
    }
  ],
  "read_only": true,
  "changed_resources": []
}
```

---

## Graph API reference

All calls use `https://graph.facebook.com/v21.0/`. Always pin the version. Do not let it float.

Key endpoints for Phase 1:

```
GET  /me/accounts                                       → list pages + page tokens
GET  /{page_id}?fields=name,category,fan_count,...      → page details
GET  /{page_id}/posts?fields=message,created_time,...   → page posts
POST /{page_id}/feed                                    → publish a post
```

Key fields for publish (`POST /{page_id}/feed`):

```json
{
  "message": "...",
  "link": "https://...",      // optional
  "published": true,          // false = schedule (requires scheduled_publish_time)
  "access_token": "<page_token>"
}
```

---

## Invariants

- `posts.draft` never calls the Graph API. It returns a draft artifact only. `changed_resources` must always be `[]`.
- `posts.publish` requires `allowed_actions` to include `"publish"` and must only execute after the CMO receives explicit user approval. Do not dispatch publish on a bare `RUN:` without a prior approval artifact.
- `pages.read` and `posts.read` are strictly read-only. `changed_resources` must always be `[]`.
- All modules use Page Access Token only — never the User Access Token — for API calls.
- Never fabricate engagement metrics (likes, shares, reach, impressions). Read-only capabilities return live API data or fail explicitly.
- `comments.respond` (Phase 2) is approval-gated at the same level as `posts.publish`.
- Do not import `requests`. Use `urllib.request` only (same rule as all other plugins).
- Do not call `get_settings()` or query the BOS database. All credentials come from `brief["_channel_credentials"]`.

---

## Do-Nots

- Do not mix Phase 1 scopes with Phase 3 Instagram scopes until Phase 3 is being built. Premature scope requests can fail Meta app review.
- Do not create a `facebook` plugin directory in addition to `meta`. This plugin is `meta` from the start.
- Do not store or log Page Access Tokens outside of the `social_connections` table + encrypted fields.
- Do not use the User Access Token for any page action. Exchange it for a Page Access Token at OAuth time and discard the user token.
- Do not add ad account credential handling to Phase 1–3 capabilities. Ads are Phase 4 and use a separate credential path.
- Do not hardcode page IDs. They come from `brief["_channel_credentials"]["facebook_page_id"]`.
- Do not accept image uploads directly. Image post support (via `/photos` endpoint) is a Phase 2 extension; Phase 1 posts are text + optional link only.
- Do not schedule posts (Phase 1). `published: false` + `scheduled_publish_time` is a Phase 2 addition.

---

## API pitfalls

- **Page tokens vs User tokens**: Page Access Tokens are scoped to a single page. The `/me/accounts` response returns one token per page — store them per-connection row, not globally.
- **Graph API version**: Always use `v21.0`. Meta deprecates old versions on a rolling schedule. Check deprecation dates when upgrading.
- **Rate limits**: 200 calls/hour per Page token for standard Graph API. `pages.read` + `posts.read` together use ~3 calls. Batch requests if reading multiple pages at once.
- **Pagination**: `posts.read` returns at most 25 posts by default. Use `?limit=` and the `paging.next` cursor for more. Phase 1 caps at 25; pagination is a Phase 2 addition.
- **Post ID format**: Page-scoped post IDs are `{page_id}_{post_id}` (e.g. `9988776655_123456789`). Do not treat these as integers.
- **Link preview**: Posting a `link` field triggers Meta to fetch an OG preview. This adds latency (~2–5s) to the publish call. Set a 30s timeout minimum.
- **Instagram Business requirement**: Instagram Business accounts must be linked to a Facebook Page. Standalone Instagram accounts (personal or Creator) cannot be accessed via the Graph API. The `ig_business_account_id` field on a Page will be absent for non-business Pages.
- **App review**: Publishing to pages beyond the app developer's own pages requires Meta app review for `pages_manage_posts`. For internal brand pages this is waived, but document the app's review status before shipping to a client.

---

## Required social connection

```
requires_social_connection: ["facebook"]
```

No platform vars needed for Phase 1–3. Phase 4 (Ads) may require `META_APP_ID` and `META_APP_SECRET` as platform vars if the OAuth handler does not already hold them in the handler config.

---

## Local backlog

- [ ] Phase 1: `FacebookOAuthHandler` in `provider_auth.py` + page selection step in `social.py`
- [ ] Phase 1: `channel.json` + `pages/read`, `posts/read`, `posts/draft`, `posts/publish` capabilities
- [ ] Phase 1: Frontend — add Facebook to Brands connect flow (same pattern as Gmail OAuth)
- [ ] Phase 2: `comments/read` with intent classification (buying intent, support risk, spam)
- [ ] Phase 2: `comments/respond` (approval-gated)
- [ ] Phase 2: `posts/draft` image support via `media.image.generate` pre-generation (pattern C)
- [ ] Phase 2: Post scheduling (`published: false` + `scheduled_publish_time`)
- [ ] Phase 2: `posts.read` pagination (cursor-based, beyond 25 posts)
- [ ] Phase 3: Add Instagram scopes to OAuth handler
- [ ] Phase 3: `instagram/posts/draft` + `instagram/posts/publish`
- [ ] Phase 4: Meta Ads credential path (ad account token) — design TBD
- [ ] Phase 4: `ads/campaigns/read`, `ads/performance/read`
