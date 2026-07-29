# Postcraft Plugin Notes

## Artifact Handling — Known Issue & Proper Fix

### The Bug
`postcraft.create` embeds the full generated image as `image_data_b64` in the artifact block (~540KB image → ~720KB base64 text). This causes the JSON output to be truncated mid-string in the BOS stream, breaking the artifact card.

### Comparison with Other Plugins

| Plugin | Block Type | Image Delivery | Truncation Risk |
|---|---|---|---|
| `storyboard.render` | `image_asset` (native) | Full `image_data_b64` embedded, but has `asset_omitted: true` fallback path | Same risk, but graceful fallback exists |
| `storyboard.motion.render` | `video_asset` (native) | Never embedded — served via `/api/media/video/{filename}` BOS route | None |
| `postcraft.create` | `post_image` (custom) | Full b64 embedded — **broken** | Truncates output |

### The Right Fix

Switch from `"type": "post_image"` to **`"type": "image_asset"`** (native BOS type). When Drive upload succeeds, set `asset_omitted: True` and omit `image_data_b64` entirely. The `image_asset` renderer in `ApprovalBundle.tsx` has a built-in `asset_omitted` path that shows a placeholder card with the Drive link.

**Trade-off**: Losing the custom post card layout (inline headline/subheadline/body/CTA). Those fields survive as block metadata and are accessible, but won't be rendered inline in the review card.

### Interim Fix Applied (2026-06-23)
Added `_make_thumbnail()` helper in `module.py` — embeds a 480px-max thumbnail as `image_data_b64` instead of the full image (~10–20KB b64 vs ~720KB). Keeps the `post_image` card rendering with the custom layout. Drive link is still shown in the card footer for full-res access.

This fixes truncation but still uses the custom `post_image` type rather than the native BOS `image_asset` type. The proper refactor (to `image_asset` + `asset_omitted`) is the right long-term direction.

### Lesson
**Never embed large binary payloads as base64 in artifact blocks.** For images, use `image_asset` + `asset_omitted: True` + Drive meta. For video, write to `/tmp/bos_video_*.mp4` and serve via `/api/media/video/{filename}`. The BOS artifact contract supports both patterns natively.
