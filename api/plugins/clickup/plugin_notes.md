# ClickUp Plugin — Notes & Invariants

## Invariants

- `tasks.read` is strictly read-only. It never creates, updates, or deletes tasks. The `changed_resources` block field must always be `[]`.
- `tasks.read` scans the **full workspace** — all spaces, folders, and lists. No default list. Output is grouped by space.
- `tasks.create` requires explicit user confirmation before dispatch. The SKILL.md requires_intent includes `action`. The CMO must show what will be created and receive a confirm before emitting `RUN:`.
- `tasks.create` resolves the target list from `brief["list_id"]` (preferred) or `brief["list_name"]` (fuzzy match). If neither is in the brief, the module returns an error with the full list of available lists — the CMO must include one.
- Neither module calls `get_settings()` or queries the BOS database. All credentials come from `brief["_channel_credentials"]`.
- `CLICKUP_TEAM_ID` is the Workspace ID in ClickUp's API — confusingly named `team_id` in all API calls.
- Only `CLICKUP_API_TOKEN` and `CLICKUP_TEAM_ID` are required credentials. No default list ID.

## Fixed Bugs

- v0.1.1: Removed `CLICKUP_DEFAULT_LIST_ID` from required credentials. `tasks.read` now scans full workspace; `tasks.create` resolves list from brief instead of a stored default.
- v0.1.1: Removed `Bearer` prefix from Authorization header — ClickUp personal tokens (`pk_...`) use the raw token value, not OAuth Bearer format.

## Do-Nots

- Do not reintroduce `CLICKUP_DEFAULT_LIST_ID` as a required credential. Full workspace coverage is the correct model.
- Do not hardcode a list ID anywhere in the modules. List targeting must come from the brief.
- Do not add OAuth flow here. Personal API token (`pk_...`) via Admin → Connectors is sufficient for v1. If OAuth is needed later, follow the Gmail OAuth handler pattern in `api/routers/social.py`.
- Do not accept `notify_all=true` for bulk task creation — it spams all watchers.
- Do not import `requests` or any third-party HTTP library. Use `urllib.request` only.
- Do not add the `Bearer` prefix to the Authorization header. ClickUp personal tokens are sent raw.

## API Pitfalls (from ClickUp API docs)

- Task IDs are alphanumeric strings (e.g. `"9hz"`). Workspace, space, folder, list IDs are integers. Do not coerce task IDs to int.
- `due_date` in both API requests and responses is a Unix timestamp in **milliseconds**. Multiply seconds by 1000. Do not pass seconds directly.
- `status` strings are case-sensitive and list-specific (e.g. `"to do"` not `"To Do"`). The module uses `"to do"` as the safe default; if creation fails due to invalid status, the error surfaces in `failed[]`.
- Rate limit: 100 requests/minute per token. `tasks.read` makes ~3 + (2 × spaces) + lists API calls for workspace traversal. At 2 spaces and 6 lists that's ~16 calls. `tasks.create` caps at 20 tasks per call.
- `team_id` in ClickUp API = Workspace ID, not a user group.
- `tasks.read` workspace traversal silently skips lists that return errors (network or permissions) rather than failing the whole read.

## Local Backlog

- [ ] Add `tasks.update` capability (approval-gated) for marking tasks complete from CMO chat
- [ ] Add `tasks.read` pagination for lists with >100 tasks (`page=1`, `page=2`, etc.)
- [ ] Consider OAuth per-brand connection following Gmail pattern once multi-brand ClickUp usage is needed
