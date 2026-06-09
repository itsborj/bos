# Meta Plugin Documentation

## Overview

This directory contains plugin-specific documentation for the Meta integration. Each plugin maintains its own documentation to keep concerns separated and avoid documentation sprawl across the entire codebase.

## Documentation Structure

- `meta-publish-wiring.md` - Complete implementation guide for Meta publish integration
- `api-endpoints.md` - Meta plugin-specific API endpoints
- `architecture-changes.md` - Architecture improvements specific to Meta plugin

## Plugin Documentation Strategy

**Important:** Each plugin will have its own documentation directory under `api/plugins/{plugin-name}/docs/` to maintain separation of concerns. This approach ensures that:

- Plugin-specific issues are documented in isolation
- Documentation doesn't need to be pulled up across all code changes
- Each plugin maintains its own project brief and implementation logs
- Documentation stays focused on the specific plugin's functionality

For detailed guidelines on plugin documentation structure, see the main documentation strategy at [docs/plugin-documentation-strategy.md](../../docs/plugin-documentation-strategy.md).

## Related Files

- `README.md` - Main plugin overview and roadmap
- `channel.json` - Plugin metadata and capability IDs
- `capabilities/` - Individual capability implementations

## Documentation Format

All plugin documentation follows this format:
- **Date and status** header
- **Problem statement** and **solution architecture**
- **Implementation details** with code examples
- **Validation results**
- **Next steps** and **future implications**
- **Files modified** list
- **Decision log** with rationale
- **Plugin-specific notes** section