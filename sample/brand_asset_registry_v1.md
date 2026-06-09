# brand.asset_registry — Stage 2 Sample
**Status:** Stage 2 — Sample for approval
**Date:** 2026-05-23
**Capability ID:** `brand.asset.select`
**Plugin home:** `api/plugins/google-drive-assets/` (first connector)
**CMO job:** `marketing.execute` → asset requirement → asset selection

---

## What This Sample Covers

Per BITE, this sample must show:
1. **Allowed outcome** — full happy path through asset selection into a channel artifact
2. **Forbidden outcome** — what BOS must NOT do when no approved asset exists
3. **Artifact contracts** — `asset_requirement`, `selected_asset`, `creative_bundle` block shapes
4. **CMO chat boundary** — what the operator sees vs. what the system does

---

## Scenario

Client: Golden Gate Memorial Park
Brand brief: memorial property — lawn lots, garden lots, columbary, family villas
Google Drive folder connected and indexed
Campaign: Summer Promo

---

## Trigger

> **Operator (CMO chat):** Create a Facebook post for the summer promo targeting life plan holders.

---

## Allowed Outcome ✅

### Step 1 — CMO reply (mobile-first, 3 lines)

```
Summer Promo Facebook post — starting now.

Pulling from approved campaign assets for life plan holders.
(Asset selection + copy in Stream)
```

No inline copy. No pasted image. No made-up asset description.

---

### Step 2 — Specialist dispatch (hidden from operator)

```
RUN: brand.asset.select
RUN: marketing.channel.meta.posts.draft
```

The CMO dispatches two transforms in parallel:
- `brand.asset.select` — retrieves the best matching approved asset
- `meta.posts.draft` — generates the post copy using brand brief

Both share the same campaign brief. Neither blocks the other.

---

### Step 3 — Asset selection transform output

```json
{
  "transform": "brand.asset.select",
  "status": "success",
  "asset_requirement": {
    "type": "image",
    "product": "lawn_lot",
    "campaign": "summer_promo",
    "offer": "life_plan_holder_discount",
    "audience": "life_plan_holders",
    "channel": "facebook",
    "aspect_ratio": ["1:1", "4:5"],
    "status_gate": ["approved_for_use", "approved_with_expiry"]
  },
  "selected_asset": {
    "source": "google_drive",
    "folder_path": "/02_Approved Campaign Assets/Summer Promo/",
    "file_name": "summer-promo-lawn-lot-4x5-v2.png",
    "file_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OL_2TIaC0",
    "drive_url": "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OL_2TIaC0",
    "thumbnail_url": "https://drive.google.com/thumbnail?id=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OL_2TIaC0",
    "status": "approved_for_use",
    "aspect_ratio": "4:5",
    "product_match": "lawn_lot",
    "campaign_match": "summer_promo",
    "reason": "Exact match: campaign, product, channel format. Approved for use. No expiry.",
    "expiry_date": null,
    "do_not_use_notes": null
  }
}
```

---

### Step 4 — Post copy transform output (parallel)

```json
{
  "transform": "meta.posts.draft",
  "status": "success",
  "block_type": "fb_page_post_draft",
  "copy": {
    "caption": "Your family deserves a place of honor. This summer, Golden Gate's Summer Promo gives life plan holders an exclusive discount on lawn lot packages — spaces designed for reflection, beauty, and peace.",
    "cta": "Message us today to check your promo eligibility.",
    "hashtags": ["#GoldenGate", "#SummerPromo", "#LifePlanHolder", "#ForeverInPeace"]
  }
}
```

---

### Step 5 — Stream artifact (creative bundle)

**Stream card — Facebook Post Draft**
Brand: Golden Gate ◦ Campaign: Summer Promo ◦ Channel: Facebook

```
┌─────────────────────────────────────────────────────────────┐
│ 🖼 summer-promo-lawn-lot-4x5-v2.png                         │
│    [thumbnail preview — 4:5 — approved_for_use]            │
│    Source: Google Drive / Summer Promo folder               │
│    Reason: Exact match — campaign, product, Facebook format │
├─────────────────────────────────────────────────────────────┤
│ CAPTION                                                     │
│ Your family deserves a place of honor. This summer,        │
│ Golden Gate's Summer Promo gives life plan holders an      │
│ exclusive discount on lawn lot packages — spaces designed   │
│ for reflection, beauty, and peace.                         │
│                                                             │
│ Message us today to check your promo eligibility.          │
│ #GoldenGate #SummerPromo #LifePlanHolder #ForeverInPeace   │
├─────────────────────────────────────────────────────────────┤
│  [Approve & Publish]     [Revise]     [Dismiss]            │
└─────────────────────────────────────────────────────────────┘
```

Asset link + reason visible. Operator approves the whole bundle: copy + selected image + channel draft.

---

### Step 6 — Creative bundle artifact block (JSON contract)

```json
{
  "artifact_type": "creative_bundle",
  "channel": "facebook",
  "campaign": "Summer Promo",
  "brand_id": "<golden_gate_brand_id>",
  "status": "pending_review",
  "copy": {
    "caption": "Your family deserves a place of honor...",
    "cta": "Message us today to check your promo eligibility.",
    "hashtags": ["#GoldenGate", "#SummerPromo", "#LifePlanHolder", "#ForeverInPeace"]
  },
  "asset_requirement": {
    "type": "image",
    "product": "lawn_lot",
    "campaign": "summer_promo",
    "audience": "life_plan_holders",
    "channel": "facebook",
    "aspect_ratio": ["1:1", "4:5"],
    "status_gate": ["approved_for_use", "approved_with_expiry"]
  },
  "selected_asset": {
    "source": "google_drive",
    "file_name": "summer-promo-lawn-lot-4x5-v2.png",
    "file_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OL_2TIaC0",
    "drive_url": "https://drive.google.com/file/d/...",
    "thumbnail_url": "https://drive.google.com/thumbnail?id=...",
    "status": "approved_for_use",
    "aspect_ratio": "4:5",
    "reason": "Exact match: campaign, product, channel format."
  },
  "allowed_actions": ["approve_and_publish", "revise", "dismiss"],
  "action_modules": {
    "publish": "meta.posts.publish"
  }
}
```

---

## Forbidden Outcomes ❌

### Forbidden 1 — Generating an image when an approved asset exists

```
❌ BOS generates a new AI image instead of selecting from the approved folder.
```

BOS does not call `media.image.generate` when `brand.asset.select` returns a valid approved asset. Native generation is a fallback plugin, not the default path, per v1 product rule.

---

### Forbidden 2 — Auto-selecting from raw/draft/unapproved assets

**Scenario:** The only matching image is in `05_Raw / Unapproved/`.

```
❌ BOS picks the raw file and proceeds as if it is approved.
```

BOS must block and surface this instead:

**Allowed behavior when no approved asset found:**

```
┌─────────────────────────────────────────────────────────────┐
│ ⚠️  Asset Review Required                                   │
│                                                             │
│ I found matching images for Summer Promo / lawn lot         │
│ but they are not approved for use yet:                     │
│                                                             │
│   • summer-promo-lawn-lot-4x5-DRAFT.png  [draft]          │
│   • lawn-lot-raw-shoot-03.jpg            [raw]             │
│                                                             │
│ Post copy is ready. The draft will be held until an        │
│ approved asset is selected.                                │
│                                                             │
│  [Flag asset for review]  [Skip image]  [Dismiss]          │
└─────────────────────────────────────────────────────────────┘
```

Copy is produced and saved. Visual asset is flagged. The creative bundle is held at `asset_pending_review` status — not published until the asset is resolved.

---

### Forbidden 3 — CMO pasting the image or copy inline in chat

```
❌ CMO chat reply contains the full caption, hashtags, and image preview inside the chat bubble.
```

CMO returns a short dispatch confirmation only. All native creative content lives in the Stream artifact card. The operator reviews in Stream, not in chat.

---

### Forbidden 4 — Asset selection with no status gate

```
❌ BOS queries any folder with any file and selects at random.
```

Every asset selection query must apply the status gate:
```python
status IN ['approved_for_use', 'approved_with_expiry']
AND (expiry_date IS NULL OR expiry_date > today)
AND 'do_not_use' NOT IN flags
```

If the expiry is tomorrow and the planned publish is next week, BOS should surface a warning:

```
⚠️ Selected asset expires 2026-06-01 — confirm publish before expiry or request a replacement asset.
```

---

### Forbidden 5 — Making BOS the asset editor or designer

```
❌ BOS cannot resize, crop, recolor, or edit the selected asset.
❌ BOS cannot provide Canva links or embed Figma previews.
❌ BOS cannot generate variations of the selected image.
```

If the asset format does not match the channel requirement, BOS surfaces:

```
The available approved image is 16:9 landscape — this format is suboptimal for Facebook feed posts (recommended 4:5 or 1:1). Would you like to:
  → Flag the asset library gap for the creative team
  → Use the 16:9 image anyway (with a note)
  → Proceed without a visual
```

Resolution decision stays with the operator.

---

## Capability Placement in BOS Architecture

```
api/plugins/google-drive-assets/
  channel.json           ← plugin manifest
  capabilities/
    brand/asset/index/
      SKILL.md           ← triggers: "index our drive", "refresh asset library"
      module.py          ← walk folder, build manifest, write to DB
    brand/asset/select/
      SKILL.md           ← triggers: fired by marketing.execute when asset_requirement is set
      module.py          ← query asset_manifest, return best match or flag
```

Why plugin (not first-party capability)?
- Google Drive is an external connector — belongs in `api/plugins/`
- Future connectors (Dropbox, Cloudinary, DAM) replace only the plugin, zero BOS core changes
- Same pattern as Gmail, Meta, Google Ads: credentials injected via `inject_channel_credentials()`

---

## Asset Manifest DB Schema (new table: `asset_manifest`)

```sql
asset_id           UUID PRIMARY KEY
brand_id           UUID FK brands.id
source             TEXT          -- 'google_drive', 'dropbox', 'cloudinary', 'local'
source_file_id     TEXT          -- platform-native file ID
folder_path        TEXT
file_name          TEXT
drive_url          TEXT
thumbnail_url      TEXT
product            TEXT          -- 'lawn_lot', 'garden_lot', 'columbary', ...
campaign           TEXT          -- 'summer_promo', 'broker_recruitment', ...
offer              TEXT          -- 'life_plan_holder_discount', ...
audience           TEXT[]        -- ['life_plan_holders', 'brokers']
channels           TEXT[]        -- ['facebook', 'instagram', 'email', 'print']
aspect_ratio       TEXT          -- '1:1', '4:5', '16:9', ...
status             TEXT          -- 'approved_for_use', 'approved_with_expiry', 'draft', 'raw', 'archived', 'do_not_use'
expiry_date        DATE
do_not_use_notes   TEXT
indexed_at         TIMESTAMPTZ
last_synced_at     TIMESTAMPTZ
```

---

## Asset Metadata Source (v1)

Metadata starts as a Google Sheet or CSV manifest inside the Drive folder.

File: `00_Brand/_asset_manifest.csv`

```csv
file_name,product,campaign,offer,audience,channels,aspect_ratio,status,expiry_date,do_not_use_notes
summer-promo-lawn-lot-4x5-v2.png,lawn_lot,summer_promo,life_plan_holder_discount,"life_plan_holders","facebook,instagram",4:5,approved_for_use,,
broker-kit-cover-landscape.png,lawn_lot,broker_recruitment,,brokers,"email,print",16:9,approved_for_use,,
raw-shoot-garden-lot-12.jpg,garden_lot,,,,"",16:9,raw,,Not for public use yet
```

The `brand.asset.index` module reads this CSV on sync, upserts rows into `asset_manifest`.

Later: metadata sourced directly from Drive file properties or a structured JSON file alongside each asset.

---

## Plugin Capabilities Summary

| Module ID | Job | Trigger | Risk |
|---|---|---|---| 
| `brand.asset.index` | `marketing.execute` | "sync assets", "refresh drive", "index our folder" | read-only drive scan |
| `brand.asset.select` | `marketing.execute` | fired internally by campaign execution | read-only DB query |

`brand.asset.select` is NOT directly user-triggered by CMO chat — it is called by the campaign execution layer when `asset_requirement` is set in the module brief. It is not a standalone user-facing capability.

---

## Future Connectors (same capability IDs, swappable plugin)

```
api/plugins/dropbox-assets/
api/plugins/cloudinary-assets/
api/plugins/canva-assets/
api/plugins/meta-asset-library/
api/plugins/local-upload/
```

All implement the same `brand.asset.select` interface. BOS core never changes when connectors are added.

---

## What This Capability Does Not Do (v1 scope boundary)

```
✘ Does not generate images (that is media.image.generate — a separate plugin)
✘ Does not edit, resize, or crop assets
✘ Does not manage Canva, Figma, or Adobe workflows
✘ Does not sync asset metadata automatically on cadence (manual index trigger only in v1)
✘ Does not support video assets in v1 (images only)
✘ Does not give brokers or external users direct upload access
```

---

## Open Questions for Client Setup (Golden Gate)

Before building:
1. Does Golden Gate already have a structured Google Drive folder? Or does setup require a folder structure migration?
2. Is there an existing approval/naming convention for assets? Or does the team need a naming standard guidance doc first?
3. Who owns asset approval at Golden Gate — a specific person? Or a shared role?
4. Should expired assets be archived automatically in Drive, or just flagged in BOS?
5. Will BOS need to send an asset gap notification to the creative team when a required asset is missing or unapproved?

---

*Sample status: Stage 2 — awaiting approval before reverse-spec and build.*
