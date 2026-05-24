# google-drive — Plugin Notes

Per-brand Google Drive as the creative asset warehouse. The creative factory writes here; channel specialists read approved assets from here. Architecture: `CREATIVE_SUPPLY_CHAIN.md` → Google Drive Integration. OAuth connection layer lives in `api/provider_auth.py` (`GoogleDriveOAuthHandler`) + `api/routers/social.py`.

---

## Invariants

- **Every module declares `platform_hint`** (and the full required ClassVar set) or app startup crashes — see creative-factory/plugin_notes.md.
- **The module execution-record dict (`attempt`) MUST include `tokens_input`, `tokens_output`, `provider_cost`, `latency_ms`.** `runs.py:_execute_module` reads `tokens_output` directly and raises `KeyError` otherwise. `drive_client.attempt()` supplies all of them.
- **`drive_client.py` is loaded by path, not import.** Modules are loaded via `importlib.spec_from_file_location` with the plugin dir NOT on `sys.path`, so sibling `import drive_client` fails. Each module loads it via `Path(__file__).resolve().parents[4] / "drive_client.py"`. Keep the 4-level depth (capability dirs are `capabilities/drive/<x>/<y>/module.py`).
- **Operator owns the root folder; BOS owns the substructure.** `drive.folder.setup` creates working subfolders UNDER the picked root (`root_folder_id` from the connection's `token_meta_json.drive_root_folder_id`). It never creates the root. Root is chosen via the Google Picker (`/social/drive/root`).
- **`drive.file` scope** lets BOS write only to folders it created or the operator granted via the Picker. Never silently fall back to a different folder/brand on a credential miss — raise loudly.

## Capability contract (params from brief, token from injected creds)

Token arrives via `brief._channel_credentials.page_token` (alias for `google_drive_page_token`) — `requires_social_connection: ["google_drive"]` in channel.json triggers injection.

- `drive.folder.setup` — `root_folder_id` (+ optional `campaign`) → ensures subtree, returns `{folders}`
- `drive.asset.upload` — `parent_folder_id`, `filename`, `content_b64` (or `_image_data_b64`), `mime_type` → returns `drive_file_id` + `web_view_link`
- `drive.asset.list` — `parent_folder_id` (+ optional `mime_type`) → returns `{files}`
- `drive.asset.get` — `file_id` (+ optional `include_bytes`) → returns meta + optional `content_b64`

## Validated (2026-05-24)

- Warehouse round-trip via `drive_client` against the real connected brand ("Sir Borj" root): generate (928KB PNG) → `ensure_path` → `upload_file` → `list_children` → `download_file` → **byte-identical (md5 match)**.
- Dispatchable path via `POST /runs drive.folder.setup` (real credential injection) created the full subtree in the operator's Drive.

## Local backlog

- SKILL.md not yet added for the 4 capabilities — they are orchestration/infra (`allowed_from_chat` should stay false), so they dispatch via `/runs` and the worker without chat discovery. Add SKILL.md if any becomes CMO-facing (e.g. Scenario B "attach existing asset").
- `drive_root_folder_id` is not currently injected into briefs — the orchestrator/worker (which has DB) passes `root_folder_id`/`parent_folder_id` explicitly. If a CMO-dispatched drive capability is added, inject the root via `inject_channel_credentials`.
- Next: the primitive-generation worker that loops Creative Brief requirements → `media.image.generate` → `drive.asset.upload` → writes `creative_assets` rows.
