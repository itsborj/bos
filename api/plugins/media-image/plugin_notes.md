# media-image Plugin Notes

## 2026-05-26 — Stream slow-load troubleshooting

### Symptom

Opening Stream became slow after multiple `media.image.generate` runs existed in the database.

The image capability stores generated PNG bytes inline as `result.block.image_data_b64`. A single image run can make `GET /runs/{run_id}` roughly 1–2 MB.

Before the fix, `web/src/pages/Stream.tsx` loaded recent runs by:

1. `GET /runs?limit=40`
2. firing up to 40 `GET /runs/{run_id}` detail requests in parallel
3. receiving full inline base64 image payloads for every image run, even approved/non-review items

This created large download bursts and many simultaneous DB queries.

### Quick speed test

Local test against `localhost:8000` on 2026-05-26 with the latest 39 non-failed/non-rejected runs:

```text
GET /runs?limit=40
  0.123 s, 15,306 bytes

39× GET /runs/{id}?include_assets=false
  13.475 s sequential total, 69,505 bytes
  image_data_b64 keys: 0
  asset_omitted markers: 11

39× GET /runs/{id}?include_assets=true
  12.211 s sequential total, 20,949,842 bytes
  image_data_b64 keys: 11

Payload reduction on this sample:
  20,880,337 bytes saved
  99.7% smaller detail payload when bulk hydration omits assets
```

Note: the sequential timing is noisy and not a browser-parallel benchmark. The important confirmed result is payload size: `include_assets=false` removes the 20 MB base64 burst for this dataset.

### Fix applied

- `api/routers/runs.py`
  - Added `GET /runs/{run_id}?include_assets=false`.
  - Strips large inline payload fields recursively: `image_data_b64`, `_image_data_b64`, `content_b64`, `audio_data_b64`, `video_data_b64`.
  - Adds `asset_omitted: true` to blocks where inline payloads were removed.
  - Collapsed run detail loading to one joined query for `Run`, `RunAttempt`, `RunResult`, and `RunTrace` instead of separate queries.

- `web/src/pages/Stream.tsx`
  - Uses metadata-first `GET /runs?include_preview=true` for the initial feed and polling.
  - Fetches `GET /runs/{run_id}?include_assets=true` only for explicit pending-review runs.
  - Renders a lightweight image metadata placeholder when `asset_omitted` is present.

- `web/src/api/client.ts`
  - `api.getRuns({ include_preview: true })` requests compact preview blocks in one list response.
  - `api.getRun(runId, { includeAssets })` maps to `include_assets` query param.

### Validation

```text
python compile check for api/routers/runs.py: pass
web TypeScript build (`npx tsc -b`): pass
docker compose build web && docker compose up -d web: pass
```

Host `npm run build` failed only because `web/dist/assets` is root-owned from Docker builds; Docker build succeeded.

### If this regresses

Check these first:

1. Browser Network tab: Stream should call most historical details as `/api/runs/<id>?include_assets=false`.
2. Response bodies for non-pending image runs should not contain `image_data_b64`.
3. `asset_omitted: true` should appear on stripped image blocks.
4. Pending-review image artifacts may still request full assets.
5. If Stream is still slow after preview-list loading, the next fix is to add a dedicated asset endpoint backed by Drive/object-storage signed URLs and virtualize very large feeds.

### Follow-up fixes applied — 2026-05-27

- Added `GET /runs?include_preview=true` so Stream can load compact artifact preview blocks in the run-list query.
- The list preview strips large inline payload fields with the same `asset_omitted: true` marker used by run detail.
- Stream no longer hydrates every recent run detail on initial load.
- CMO split-screen now renders the same `Stream` component as `/stream`; no separate reduced feed implementation.
- Artifact details/assets hydrate lazily and sequentially when cards enter the viewport via `IntersectionObserver` + a one-at-a-time hydration queue.
- Additional run pages load as the user scrolls instead of fetching the full run history at once.
- `GET /runs/{run_id}?include_assets=false` does not trigger Drive video re-download; local video rehydration only happens when full assets are explicitly requested.

### Next iteration ideas

- Dedicated asset endpoint, e.g. `GET /runs/{run_id}/asset` or Drive-backed signed URL.
- Store generated images as Drive/object-storage files by default and keep only `drive_file_id` + preview URL in run blocks.
- Virtualize Stream cards if the feed grows beyond the current 40-item window.
