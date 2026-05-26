# Stream Image Load Performance Fix v1

## Bad sample (current)

Opening Stream with 13 prior image runs causes the browser to fire 40 parallel detail requests:

```http
GET /api/runs?limit=40&brand_id=<brand>
GET /api/runs/<image-run-1>  -> response includes result.block.image_data_b64 (~2 MB)
GET /api/runs/<image-run-2>  -> response includes result.block.image_data_b64 (~2 MB)
...
```

Observed outcome:

```text
Initial Stream load: ~26 MB of image base64 pulled before review intent.
Concurrent run-detail hydration: 40 requests at once.
Other API calls stall while the async DB pool is saturated.
```

## Fixed sample (target)

Opening Stream still loads artifact metadata and reviewable cards, but bulk hydration does not pull image bytes for non-review items:

```http
GET /api/runs?limit=40&brand_id=<brand>
GET /api/runs/<approved-image-run>?include_assets=false
```

Representative run detail response for bulk Stream hydration:

```json
{
  "run_id": "9a7...",
  "module_id": "media.image.generate",
  "status": "succeeded",
  "approval_status": "approved",
  "result": {
    "self_check": "pass",
    "block": {
      "type": "image_asset",
      "status": "succeeded",
      "mime_type": "image/png",
      "width": 1024,
      "height": 1024,
      "prompt": "Brand-safe hero image for Klaroha",
      "byte_size": 981234,
      "asset_omitted": true
    }
  }
}
```

Review-needed artifacts may still request full assets so the approval surface stays usable:

```http
GET /api/runs/<pending-image-run>?include_assets=true
```

Acceptance:

```text
No image_data_b64 appears in Stream bulk responses for approved/non-pending runs.
Stream hydrates run details with bounded concurrency instead of 40 parallel requests.
Pending review cards remain reviewable.
```
