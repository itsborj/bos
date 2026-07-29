# TikTok Plugin — Project Brief

## Scope
Integrate TikTok's official Content Posting API so the CMO can validate a TikTok connection and directly publish a video post.

### Core Capabilities
0. **Connection Validation (`marketing.optimize`)**
   - Read-only `marketing.channel.tiktok.connection.validate` check.
   - Calls TikTok `user/info` and `post/publish/creator_info/query` with brand-scoped OAuth credentials.
   - Returns `tiktok_connection_check` artifact with account identity, privacy-level options, post-duration limits, and `changed_resources: []`.

1. **Video Publishing (`marketing.execute`)**
   - Direct post a specific video to TikTok via `post/publish/video/init`.
   - Upload the media binary to TikTok and poll `post/publish/status/fetch`.
   - Defaults to private/self-only posting unless the operator explicitly chooses another privacy level and the creator account allows it.

## BITE Pipeline Flow
Every mutation must follow the BITE pipeline:
`Intent` → `Specialist Transform` → `Proposal Artifact` → `Human Approval` → `Execution` → `Action Result Artifact`.

## Technical Constraints
- **Plugin Boundary**: All code stays in `plugins/tiktok/`.
- **Credentials**: Use `inject_channel_credentials()` / plugin credential injection to get the brand-scoped TikTok OAuth token.
- **OAuth Scopes**: Current OAuth requests `user.info.basic,video.publish`.
- **Risk Policy**: Validation is read-only. Direct post mutations are approval-gated.
- **TikTok audit rule**: Unaudited clients are typically restricted to private viewing mode. Public posting depends on TikTok app review / audit.

## Directory Structure
```
plugins/tiktok/
├── channel.json
├── capabilities/
│   └── marketing/channel/tiktok/
│       ├── connection/validate/
│       │   ├── module.py
│       │   └── SKILL.md
│       └── video/publish/
│           ├── module.py
│           └── SKILL.md
└── SKILL.md
```
