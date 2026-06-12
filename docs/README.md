# Klaroha BOS Documentation

## Core Documentation

- [PROJECT_BRIEF.md](../PROJECT_BRIEF.md) - Project overview and current status
- [BITE.md](../BITE.md) - System architecture constitution
- [BACKLOG.md](../BACKLOG.md) - Development backlog and task tracking
- [ai_providers.md](../ai_providers.md) - AI Providers & Fallback Routing Mechanism Design
- [agency_day_in_life.md](agency_day_in_life.md) - Agency business leader cadence + BOS coverage map (living requirements guide)


## Plugin Documentation

Each plugin maintains its own documentation directory under `api/plugins/{plugin-name}/docs/` to maintain separation of concerns and avoid documentation sprawl across the entire codebase.

### Example Plugin Documentation

- **Meta Plugin:** [api/plugins/meta/docs/](../api/plugins/meta/docs/)
  - [meta-publish-wiring.md](../api/plugins/meta/docs/meta-publish-wiring.md) - Complete implementation guide for Meta publish integration
  - [api-endpoints.md](../api/plugins/meta/docs/api-endpoints.md) - Meta plugin API endpoints
  - [architecture-changes.md](../api/plugins/meta/docs/architecture-changes.md) - Architecture improvements
  - [README.md](../api/plugins/meta/docs/README.md) - Meta plugin documentation hub

### Documentation Strategy

See [plugin-documentation-strategy.md](plugin-documentation-strategy.md) for detailed guidelines on plugin documentation structure, benefits, and quality standards.

### Key Benefits

- **Plugin-specific issues are documented in isolation** - Each plugin maintains its own documentation structure
- **Documentation doesn't need to be pulled up across all code changes** - Plugin docs stay focused on specific functionality
- **Each plugin maintains its own project brief and implementation logs** - Avoids documentation sprawl
- **Documentation stays focused on the specific plugin's functionality** - Clear separation of concerns

## Development

- [api/routers/chat_notes.md](../api/routers/chat_notes.md) - CMO chat coordination notes and development guidelines
- [api/capability_manifest.py](../api/capability_manifest.py) - Capability manifest generation

## Phase 6 - Full-Stack Marketing Automation

Current focus: Building a complete marketing automation system with CMO orchestration and plugin-based specialists.

### Key Components
- CMO chat agent for marketing orchestration
- Plugin system for channel integrations (Meta, Google, Email, etc.)
- Stream for artifact approval and management
- Workspace for detailed artifact review
- Brand and campaign management

### Current Status
- Phase 6, Gate 2 passed
- Meta publish integration complete
- Next: Shortform video production infrastructure