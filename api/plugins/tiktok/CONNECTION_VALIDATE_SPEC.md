# TikTok Connection Validate — Reverse Spec v1

Source sample: `sample/tiktok_connection_validate_v1.md`

## Capability

`marketing.channel.tiktok.connection.validate`

## Job

`marketing.optimize` diagnostic/readiness check.

## User intent

Use when the operator explicitly asks to test, verify, validate, troubleshoot, or check the connected TikTok account/API/OAuth pipeline.

## Connector

- Platform: `tiktok`
- OAuth handler: TikTok Login Kit / Open API v2
- Required app vars: `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REDIRECT_URI`
- Brand-scoped token stored in `social_connections`
- Credentials injected through `brief["_channel_credentials"]`

## Transform behavior

1. Require an injected TikTok access token.
2. Call TikTok read-only account endpoint:
   - `GET https://open.tiktokapis.com/v2/user/info/`
   - fields: `open_id,union_id,avatar_url,display_name,profile_deep_link,is_verified`
3. Return a `tiktok_connection_check` block.
4. Never mutate TikTok resources.

## Output contract

Block type: `tiktok_connection_check`

Success fields:
- `platform: tiktok`
- `status: succeeded | partial | failed`
- `read_only: true`
- `account.open_id`
- `account.display_name`
- optional profile/avatar fields
- `test_post_readiness`
- `changed_resources: []`
- `allowed_actions`

## Risk policy

Read-only. Public test posting is out of scope for this capability.

## Forbidden

- No upload, publish, schedule, delete, comment, like, follow, ad/campaign, budget, or pixel changes.
- No fake account IDs, usernames, profile URLs, permission states, or post URLs.
- No workspace-wide credential fallback when an active Brand is set.
