# Meta Plugin

BOS channel plugin for Meta platforms: Facebook Pages, Instagram Business, and Meta Ads.

Plugin root: `api/plugins/meta/`

All capabilities live under `capabilities/marketing/channel/meta/`. The plugin expands incrementally by phase — adding a new capability directory and updating `capability_ids` in `channel.json` is all that is needed.

## Plugin Documentation

See `docs/` directory for plugin-specific documentation:
- `docs/meta-publish-wiring.md` - Publish implementation details
- `docs/api-endpoints.md` - Meta plugin API endpoints

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

## Meta Developer App Setup

Meta uses a **Use Cases** model (not the old Products model). The correct setup process:

### 1. Create the app
- Go to developers.facebook.com → **Create App**
- App type: **Business** (or Other → Business)
- Fill in name and contact email

### 2. Add the Manage Pages use case
- Dashboard → **Add use case** → **Manage Pages** → Customize
- In the permissions list, click **Add** next to each of these (order matters — dependencies first):
  1. `pages_show_list` — lists pages the user admins
  2. `pages_read_engagement` — reads page content, follower data, metadata; **hard dependency of `pages_manage_posts`**
  3. `pages_read_user_content` — reads user-generated content on the page; hard dependency of `pages_manage_engagement`
  4. `pages_manage_posts` — create/edit/delete posts
  5. `pages_manage_engagement` — create/edit/delete comments (Phase 2)
- Each enabled permission shows **"0 / Ready for testing"** in the Status column
- Do NOT enable permissions you don't need — unused permissions are flagged in App Review

> **Critical:** permissions listed in a use case are NOT automatically enabled. Each one must be explicitly clicked **Add**. If a permission is listed but not added, Meta injects it as a dependency but the OAuth dialog rejects it as "Invalid Scope".

### 3. Facebook Login settings
- Left sidebar → **Facebook Login → Settings**
- **Valid OAuth Redirect URIs** — add all that apply:
  ```
  https://staging.klaroha.com/social/facebook/callback
  https://hq.klaroha.com/social/facebook/callback
  ```
- **Note:** `http://localhost` does not work when Enforce HTTPS is on. Use staging for OAuth testing.
- Save Changes
- Verify with the Redirect URI Validator — should show a green checkmark

### 4. App Domains
- **Settings → Basic**
- **App Domains** — add domain only (no protocol, no path):
  ```
  staging.klaroha.com
  hq.klaroha.com
  ```
- Save Changes

### 5. Enter credentials in BOS
- Credentials go in **Admin → Specialists → Social Specialist / Meta Channel → Connectors** (not `.env`)
- `META_APP_ID` — from Settings → Basic
- `META_APP_SECRET` — click Show next to the dots in Settings → Basic
- `META_REDIRECT_URI` — match the URI registered in step 3

### 6. Testing with Graph API Explorer
- Go to developers.facebook.com/tools/explorer
- Select **Klaroha** app in the Meta App dropdown
- Click **Add a Permission** and add: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`
- Click **Generate Access Token** → grant permissions in the Facebook dialog
- Test `/me/accounts` → should return pages with access tokens
- Switch **User or Page** to a specific page → test `/{page_id}?fields=id,name,category,fan_count,link`
- Test `POST /{page_id}/feed` with `message` param to verify publish works

### App Review (for production with non-admin accounts)
- Standard Access = developer + test users only (development mode)
- Advanced Access = any user; requires Business Verification + App Review approval per permission
- For Klaroha's own brand pages, Standard Access is sufficient
- For managing client pages, App Review is required for `pages_manage_posts`

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
pages_read_engagement       ← hard dependency of pages_manage_posts
pages_manage_posts
```

`pages_read_user_content` and `pages_manage_engagement` must be enabled in the Meta app but are not requested in the Phase 1 OAuth scope — they are needed for Phase 2 (comment management).

### Scopes — Phase 3 (add for Instagram)

```
instagram_basic
instagram_content_publish
instagram_manage_comments
```

Do not request Instagram scopes in Phase 1. Scope creep in the OAuth consent screen degrades user trust and can fail app review.

### Credential injection

Declared in `channel.json` as `requires_social_connection: ["facebook", "google_drive"]` and `requires_platform_vars: ["META_APP_ID", "META_APP_SECRET", "META_REDIRECT_URI"]`.

Plugin vars (META_APP_ID, META_APP_SECRET, META_REDIRECT_URI) are stored in the DB via Admin → Specialists → Social Specialist / Meta Channel → Connectors and loaded at runtime via `get_plugin_vars("channel.meta", db, settings)`.

BOS injects page credentials into `brief["_channel_credentials"]`:

```python
creds = brief.get("_channel_credentials", {})
page_token        = creds.get("facebook_page_token")       # Facebook Page Access Token
page_id           = creds.get("facebook_page_id")          # Facebook Page ID (string)
page_name         = creds.get("facebook_page_name")        # Human-readable Page name
ig_account        = creds.get("facebook_ig_account_id")    # Instagram Business Account ID (Phase 3+)
drive_token       = creds.get("google_drive_page_token")   # Drive OAuth token (for image attachment)
```

`facebook` is always first in `requires_social_connection` so its token claims the generic `access_token` / `page_token` slots. `google_drive` injects under `google_drive_page_token` only. The publish module reads Facebook from `facebook_page_token` and Drive from `google_drive_page_token` explicitly — never the generic `page_token` for Drive, which would be the Facebook token.

Phase 4 (Ads) requires a different credential path — ad account token — which is separate from the Page Access Token. That will be handled by a dedicated credential key or a third `requires_social_connection` entry. Do not mix ad account credentials with page credentials.

### OAuth handler

`FacebookOAuthHandler` lives in `api/provider_auth.py`, registered as `"facebook"` in `_OAUTH_HANDLERS`.
- Auth endpoint: `https://www.facebook.com/dialog/oauth`
- Token endpoint: `https://graph.facebook.com/oauth/access_token`
- Long-lived token exchange: `GET /oauth/access_token?grant_type=fb_exchange_token&...`
- Page selection step: after OAuth callback, call `/me/accounts`; auto-select if 1 page, show picker modal if multiple
- Multi-page storage: encrypted pages JSON stored in `provider_login_sessions.verifier_encrypted` (Text column, migration 026)

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

### Approved action handoff

Draft artifacts declare their publish action in the block:

```json
{
  "allowed_actions": ["revise", "dismiss", "approve", "publish"],
  "action_modules": {"publish": "marketing.channel.meta.posts.publish"}
}
```

Workspace/Stream executes this through the generic core endpoint:

```text
POST /runs/{draft_run_id}/actions/publish
{ "confirm": true }
```

The endpoint approves the source draft, builds an action brief from the persisted block, executes the declared module, and stores the `fb_page_post_result` action artifact. CMO chat does not need platform-specific publish routing and does not need the draft body pasted inline.

---

## Routing contract

| User asks | Expected capability | Expected artifact | Notes |
|---|---|---|---|
| `show my facebook pages` | `meta.pages.read` | `meta_page_inventory` | Lists connected pages |
| `what did I post on facebook` | `meta.posts.read` | `meta_page_posts` | Recent posts from connected page |
| `draft a facebook post` | `meta.posts.draft` | `fb_page_post_draft` | LLM-drafted post, no API mutation |
| `write a post for my page` | `meta.posts.draft` | `fb_page_post_draft` | Same |
| `draft a Facebook post and generate a matching visual` | `meta.posts.draft` + `media.image.generate` | `fb_page_post_draft` + `image_asset` | Paired draft + visual direction; no publish/spend |
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
  "image_url": null,
  "drive_file_id": null,
  "drive_file_name": null,
  "drive_file_mime": null,
  "status": "draft",
  "allowed_actions": ["revise", "dismiss", "approve", "publish"],
  "action_modules": {"publish": "marketing.channel.meta.posts.publish"},
  "risk_policy": "draft_only_until_approved"
}
```

Operator can attach a Drive image before publishing: `PATCH /runs/{run_id}/attach-image` sets `drive_file_id`, `drive_file_name`, `drive_file_mime` on the persisted block and clears `image_url`. The publish module reads `drive_file_id` at execution time and downloads the binary via `DriveClient`.

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

All calls use `https://graph.facebook.com/v21.0/`. Always pin the version. Do not let it float. Current stable version is v21.0; Graph API Explorer defaults to v25.0 — both work for Phase 1 endpoints.

Key endpoints for Phase 1:

```
GET  /me/accounts                                       → list pages + page tokens
GET  /{page_id}?fields=name,category,fan_count,...      → page details
GET  /{page_id}/posts?fields=message,created_time,...   → page posts
POST /{page_id}/feed                                    → publish text post (+ optional link)
POST /{page_id}/photos                                  → publish image post (url or binary source)
```

Key fields for text publish (`POST /{page_id}/feed`):

```json
{
  "message": "...",
  "link": "https://...",      // optional
  "published": true,
  "access_token": "<page_token>"
}
```

Key fields for image publish by URL (`POST /{page_id}/photos`):

```json
{
  "url": "https://...",
  "message": "...",
  "published": "true",
  "access_token": "<page_token>"
}
```

Key fields for image publish from binary (`POST /{page_id}/photos`, multipart/form-data):

```
source      <binary image bytes>
message     ...
published   true
access_token  <page_token>
```

The `/photos` endpoint returns `{"id": "...", "post_id": "..."}`. Use `post_id` (not `id`) as the timeline post ID for the permalink. The publish module routes to `/photos` when `drive_file_id` or `image_url` is present in the brief, and falls back to `/feed` for text-only posts.

---

## Invariants

- `posts.draft` routes through the seeded `marketing.channel` capability for LLM-backed channel drafting. Do not point it at the CMO-facing job label `marketing.execute`; that key is not a seeded execution capability and causes `No healthy model options` at runtime.
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
- Image posts via Drive attachment are supported in Phase 1: `PATCH /runs/{run_id}/attach-image` stores the Drive file reference; the publish module downloads and uploads binary to `/photos`. Direct image URL posting (`image_url` in brief) is also supported.
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
requires_social_connection: ["facebook", "google_drive"]
requires_platform_vars: ["META_APP_ID", "META_APP_SECRET", "META_REDIRECT_URI"]
```

Platform vars are stored in DB via Admin → Specialists → Social Specialist / Meta Channel → Connectors. Never put them in `.env` for production — `.env` values are fallbacks for local dev only.

`google_drive` is optional at runtime — if the brand has no Drive connection, `google_drive_page_token` will be absent from `_channel_credentials`. The publish module returns `missing_credentials` only when `drive_file_id` is in the brief but `google_drive_page_token` is absent. Text-only posts proceed regardless of Drive connection.

## Image attachment workflow

```
1. Operator reviews fb_page_post_draft artifact in Workspace/Stream
2. Clicks "Attach image" → Drive picker modal loads images from GET /social/drive/images?brand_id=
3. Selects file → PATCH /runs/{run_id}/attach-image stores drive_file_id/name/mime in RunTrace.lineage_json.block
4. Clicks "Approve & Publish" → POST /runs/{run_id}/actions/publish?confirm=true
5. Publish module reads drive_file_id from brief, downloads binary via DriveClient (google_drive_page_token)
6. POSTs multipart to /{page_id}/photos with source=<binary> → live image post on Facebook page
```

`GET /social/drive/images?brand_id=` lists images from the brand's `drive_root_folder_id` (set via Google Picker). Supported MIME types: `image/jpeg`, `image/png`, `image/gif`, `image/webp`.
