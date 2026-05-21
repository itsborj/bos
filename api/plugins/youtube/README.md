# YouTube Plugin — Project Brief

## Scope
Integrate YouTube API to enable the CMO to manage video publishing and channel optimization.

### Core Capabilities
0. **Connection Validation (`marketing.optimize`)**
   - Read-only `marketing.channel.youtube.connection.validate` check.
   - Calls YouTube Data API v3 `channels.list` with brand-scoped OAuth credentials.
   - Returns `youtube_connection_check` artifact with channel identity, endpoint, estimated quota use, and `changed_resources: []`.

1. **Video Publishing (`marketing.execute`)**
   - Upload videos (Long-form and Shorts).
   - Manage metadata (Titles, Descriptions, Tags, Category).
   - Set visibility (Public, Unlisted, Private).
   - Approval-gated publishing (Draft $\to$ Review $\to$ Publish).

2. **Channel Management (`marketing.execute`)**
   - Update Channel "About" section.
   - Manage channel keywords.
   - Update channel branding metadata.

3. **Video Intelligence (`marketing.optimize`)**
   - Fetch performance metrics for specific videos or the whole channel.
   - Compare video performance (CTR, Average View Duration, Views).
   - Identify optimization opportunities (Title/Thumbnail A/B testing suggestions).

## BITE Pipeline Flow
Every mutation (Upload/Update) must follow the BITE pipeline:
`Intent` $\to$ `Specialist Transform` $\to$ `Proposal Artifact` $\to$ `Human Approval` $\to$ `Execution` $\to$ `Action Result Artifact`.

## Technical Constraints
- **Plugin Boundary**: All code stays in `api/plugins/youtube/`.
- **Credentials**: Use `inject_channel_credentials()` to get OAuth tokens.
- **OAuth Scopes**: Current OAuth requests `https://www.googleapis.com/auth/youtube.upload` and `https://www.googleapis.com/auth/youtube.force-ssl`.
- **Risk Policy**: Validation is read-only. Mutations require an approved artifact.

## Directory Structure
```
api/plugins/youtube/
├── channel.json          # Plugin manifest
├── capabilities/         # Discoverable BOS plugin capabilities
│   └── marketing/channel/youtube/connection/validate/
│       ├── module.py     # Read-only Data API connection check
│       └── SKILL.md      # Activation contract
├── module.py             # Legacy draft transform sketch (not discovery path)
├── SKILL.md              # Legacy draft overview (not discovery path)
├── template.j2           # Prompt templates
└── sample/               # Agreed output samples (BITE Stage 2)
```
