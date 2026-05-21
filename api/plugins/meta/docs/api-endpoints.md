# Meta Plugin API Documentation

## Approved Action Endpoint

### POST /runs/{run_id}/actions/{action}

Execute an action declared by a persisted artifact block.

**This endpoint keeps approval-gated channel actions out of CMO chat** while still allowing Stream/Workspace to execute approved actions.

### Request Body

```json
{
  "confirm": true,
  "overrides": {}
}
```

### Response

```json
{
  "source_run_id": "string",
  "source_approval_status": "string",
  "action": "string",
  "action_run": RunResponse
}
```

### Implementation Details

- Approves the source artifact
- Builds action brief from persisted block metadata
- Executes declared module via `_execute_module()`
- Stores result artifact
- Returns action run for UI updates

### Usage Examples

Meta publish workflow:
```bash
curl -X POST \
  http://localhost:8000/runs/{draft_run_id}/actions/publish \
  -H "Content-Type: application/json" \
  -d '{"confirm": true}'
```

See: `api/routers/runs.py` `execute_run_action()`

## Meta-Specific Endpoints

### Meta OAuth Connection

#### POST /social/meta/connect/start
Initiate Meta OAuth connection flow.

#### GET /social/meta/callback
Handle Meta OAuth callback and store connection.

### Meta Page Reading

#### GET /meta/pages/read
Read connected Facebook pages.

#### GET /meta/posts/read
Read posts from a connected page.

## Plugin-Specific Notes

This documentation is specific to the Meta plugin API endpoints. Each plugin will have its own API documentation within its `docs/` directory to maintain separation of concerns.