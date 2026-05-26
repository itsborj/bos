# TikTok Specialist Plugin

V1 provides a read-only connection validation capability for brand-scoped TikTok OAuth.

## Capabilities

- `marketing.channel.tiktok.connection.validate` — validates the connected TikTok account via a read-only `user/info` API call and returns a `tiktok_connection_check` artifact.

## OAuth setup

Register redirect URIs in the TikTok developer app:

```text
http://localhost/social/tiktok/callback
https://staging.klaroha.com/social/tiktok/callback
https://hq.klaroha.com/social/tiktok/callback
```

Required app vars:

```env
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
TIKTOK_REDIRECT_URI=http://localhost/social/tiktok/callback
TIKTOK_SCOPES=user.info.basic

# If your TikTok Sandbox app exposes only expanded scopes, use the exact enabled set:
# TIKTOK_SCOPES=user.info.profile,user.info.stats,video.list
```

## V1 boundary

Connection validation is read-only. Test post publishing is a later approval-gated capability that requires a video asset and TikTok Content Posting API access.
