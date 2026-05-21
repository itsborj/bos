# YouTube Plugin — Project Brief

## Scope
Integrate YouTube API to enable the CMO to manage video publishing and channel optimization.

### Core Capabilities
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
- **OAuth Scopes**: Must request `https://www.googleapis.com/auth/youtube.upload` and `https://www.googleapis.com/auth/youtube.force-ssl`.
- **Risk Policy**: `read_and_draft_only` by default. Mutations require an approved artifact.

## Directory Structure
```
api/plugins/youtube/
├── channel.json          # Plugin manifest
├── module.py             # Transform nodes
├── SKILL.md              # Activation contracts
├── template.j2           # Prompt templates
└── sample/               # Agreed output samples (BITE Stage 2)
```
