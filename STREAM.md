# Stream — Artifact Feed

## How artifacts appear in the Stream

The Stream page (`web/src/pages/Stream.tsx`) shows two sources merged into `streamArtifacts`:

1. **`artifacts`** — fetched from `GET /api/runs` on page load, paginated at 20 per page, loaded further via infinite scroll.
2. **`pendingRunItems`** — localStorage cache (`bos_pending_run_decisions`) populated when CMO chat executes a module and returns a run result. Capped at 50 entries by `writePendingRuns`. Deduped against `artifacts` by `run_id`.

`pendingRunItems` exists so newly generated artifacts appear in the Stream immediately after a CMO chat turn, without waiting for the next API poll.

---

## Image display: hydration

Run list responses strip large binary fields (`image_data_b64`, `video_data_b64`, etc.) for performance, setting `asset_omitted: true` on the block. `StreamArtifactCard` re-fetches the full run via `GET /api/runs/{run_id}?include_assets=true` when the card enters the viewport (IntersectionObserver, `rootMargin: 240px`). The hydrated run replaces the stripped one for rendering.

`ApprovalBundle` renders the image from `result.block.image_data_b64` once hydrated. While waiting, it shows "Loading generated image…" with a Drive link fallback if available.

---

## Known bug — artifacts disappear after 1 hour

**Symptom:** Artifacts generated in a session (especially bulk image renders) vanish from the Stream after ~60 minutes.

**Root cause:** `streamArtifacts` previously filtered `pendingRunItems` to only include entries younger than 1 hour:

```ts
const oneHourAgo = Date.now() - 60 * 60 * 1000;
const freshPending = pendingRunItems.filter(r =>
  r?.run_id && !apiIds.has(r.run_id) && runTimestamp(r) > oneHourAgo && ...
);
```

With `RUN_PAGE_SIZE = 20`, if the user generated more than 20 artifacts in a session, the excess lived only in `pendingRunItems`. After 1 hour, the cutoff expired them — and since they were beyond the API's page-20 limit, they had no other source. They appeared gone.

**Fix (applied):** Removed the `oneHourAgo` cutoff. `pendingRunItems` entries now stay in the stream as long as they exist in localStorage, deduped against the API list by `run_id`. `writePendingRuns` already caps localStorage at 50 entries, so stale accumulation is bounded.

```ts
const freshPending = pendingRunItems.filter(r =>
  r?.run_id && !apiIds.has(r.run_id) && (!brandId || r.brand_id === brandId)
);
```

---

## Stream count contract

The Stream header count is the total number of current run artifacts for the active brand, not just the number currently loaded in the browser and not Stream update cards.

Implementation rules:

- `GET /api/runs` supports `exclude_approval_status=dismissed` for legacy soft-dismissed artifacts.
- The first Stream page requests `exclude_approval_status: 'dismissed'` and uses `recent.total` as `totalArtifacts`.
- `loadMoreRuns()` and the 15-second poll use the same exclusion filter and refresh `totalArtifacts` from the API response total.
- Clicking `Delete` optimistically decrements `totalArtifacts` and removes the artifact from local Stream state.
- Delete also writes the run ID to the local `bos_deleted_artifact_ids` tombstone cache. This prevents stale `bos_pending_run_decisions` entries from re-inserting a deleted artifact after browser refresh before the API page catches up.
- If the API total is not available yet, the UI falls back to the currently materialized `streamArtifacts.length`.

---

## Infinite scroll contract

Stream must always keep infinite scroll enabled for run artifacts:

- The `stream-load-more` sentinel remains mounted in the feed even when the visible artifact list is empty or already quiet.
- `IntersectionObserver` loads the next `GET /api/runs` page whenever more pages exist.
- A pre-fill guard also calls `loadMoreRuns()` when deletes/filtering leave fewer than `RUN_PAGE_SIZE` visible artifacts, so the feed cannot get stuck shorter than the viewport.
- Deleted artifacts are filtered out of `streamArtifacts`, `artifacts`, and `pendingRunItems` using the local delete tombstone cache. Legacy soft-dismissed artifacts are still filtered out by API `approval_status`. Pagination continues from the API offset so older artifacts can fill in.
- When no more run pages exist, the sentinel changes to `End of stream`; until then it stays actionable as `Scroll for more` / `Loading more…`.

Delete behavior:

- ApprovalBundle `Delete` calls `DELETE /api/runs/{run_id}` and removes the artifact from Stream.
- Approved/saved preview cards also expose `Delete` and use the same persistent delete endpoint.
- Failed/error artifacts render the full ApprovalBundle so `Delete`, `Configure`, and `Retry` remain available.
- Stream update cards call `DELETE /api/stream/{update_id}` and are removed from `stream_updates`.

---

## Persistence

- `image_data_b64` is stored in `run_traces.lineage_json` (Postgres JSONB). Images are never lost from the database.
- `output_path` in the block points to the render file on disk. In BOS containers the default is `/tmp/bos-storyboard-runs` — ephemeral across restarts. Set `STORYBOARD_RUNS_DIR` to a persistent bind-mount path to preserve render files.
- Drive upload (`drive_web_view_link`) is the only persistent URL source. Configure Google Drive credentials per brand to get a stable image URL.
