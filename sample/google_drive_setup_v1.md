# google-drive — Setup & Capability Sample v1

> **BITE gate:** Stage 2 sample for the `google-drive` plugin. No plugin code until this is approved.
> Plugin path: `api/plugins/google-drive/`
> Architecture: `CREATIVE_SUPPLY_CHAIN.md` → Google Drive Integration + Asset Library.

---

## Why Drive, and why it's cheap to add

BOS already runs Google OAuth for Gmail and Calendar against one Google Cloud app. Drive is an **additive scope on the same app** — no new vendor, no new OAuth client, no new env vars for deploying orgs. The asset library's binaries live in Drive; the `creative_assets` table is the index.

**Connection is per brand.** Each brand connects its own Drive (or a shared company Drive with a brand-specific root folder). Isolation is by folder + by `social_connections` row scoped to `brand_id`. Client A's assets can never resolve into Client B's render job.

---

## OAuth scopes

```
https://www.googleapis.com/auth/drive.file       # read/write files BOS creates
https://www.googleapis.com/auth/drive.readonly    # read brand assets the client uploads by hand
```

**Scope-matching constraint (carried from CLAUDE.md):** each handler requests only scopes matching its redirect URI. Drive scopes go through the Drive redirect URI, never piggy-backed on the Gmail or Calendar redirect — Google silently rejects mismatched scope/redirect pairs (returns no `code`, no `error`). Register:

```
http://localhost/social/google-drive/callback
https://hq.klaroha.com/social/google-drive/callback
https://staging.klaroha.com/social/google-drive/callback
```

---

## Connection flow (operator experience)

On the **Brands** page (never Connectors — per CLAUDE.md, per-brand connect lives on Brands):

```
Vantage Coaching                          [ Connect Google Drive ]
                                                  │
                                          Google consent screen
                                                  │
                                          callback → social_connections row:
                                            platform = "google_drive"
                                            brand_id = vantage_001
                                            page_id  = drive account email (identity)
                                            token_meta_json = { refresh_token_encrypted, expires_at }
                                                  │
Vantage Coaching   ✓ Connected            [ Choose folder ]  [ Disconnect ]
                                                  │
                                          Google Picker opens (uses stored token)
                                                  │
                                          operator selects an EXISTING folder,
                                          e.g. My Drive/Clients/Vantage/
                                                  │
                                          POST /social/drive/root stores on connection:
                                            token_meta_json += {
                                              drive_root_folder_id, drive_root_name, drive_root_path }
                                                  │
Vantage Coaching   ✓ Connected   Root: Clients/Vantage   [ Change folder ] [ Disconnect ]
```

The **operator owns the root folder** (picked from their existing Drive layout via the Google Picker, which grants `drive.file` write access to that folder). **BOS owns the substructure** it creates underneath. Token refresh reuses the existing `get_page_token()` auto-refresh path.

Why the Picker: under `drive.file`, BOS can only write to folders it created OR folders the user explicitly grants via the Picker. Picking an existing folder through the Picker is the documented way to grant that write access — so an agency can point BOS at its existing `Clients/{Brand}/` layout instead of a BOS-imposed root.

---

## Folder structure

The hierarchy is **Org (deployer) → agency/project → brand**, so the root is NOT hardcoded. The operator picks the brand's root folder. `drive.folder.setup` then creates BOS's working subfolders *under* that picked root (idempotent):

```
<operator-picked root>/                  ← e.g. My Drive/Clients/Vantage/  (picked via Picker)
├── Brand Assets/                         ← CLIENT UPLOADS here by hand
│   ├── Logos/                               vantage-logo.svg, vantage-logo-white.png
│   ├── Products/                            (n/a for a service brand)
│   └── Footage/                             existing b-roll, testimonial clips
├── Templates/
├── Campaigns/
│   └── VP Transition/
│       ├── Creative Concepts/
│       ├── Primitives/
│       │   ├── Image Plates/
│       │   ├── Video Plates/
│       │   └── Motion Cards/
│       ├── Blueprints/
│       └── Export Packages/             ← finished, channel-ready files
└── Archive/
```

The picked root's folder ID is stored as `drive_root_folder_id` on the connection. The creative factory, channel specialists, and CMO all resolve asset paths from there. Anything the client drops in `Brand Assets/` is visible via `drive.readonly`; everything BOS produces it writes via `drive.file`.

---

## Capability contracts

Four capabilities. Each is a thin wrapper — BOS builds the request, Drive does the storage. All are brand-scoped via injected credentials (`brief["_channel_credentials"]`), never direct DB/token access.

### `drive.folder.setup`
Creates BOS's working subfolders *under the operator-picked root* (`drive_root_folder_id` from the connection). Idempotent — returns existing folder IDs if already present. Does NOT create the root itself; the operator picked that via the Picker.

```json
// in
{ "brand_id": "vantage_001" }   // root resolved from connection
// out
{ "root_folder_id": "1Picked...", "created": ["Brand Assets/Logos", "Campaigns", ...],
  "already_existed": false }
```

### `drive.asset.upload`
BOS uploads a binary it produced (a primitive, a blueprint JSON, an export package), writes the `creative_assets` row, returns the Drive file ID.

```json
// in
{ "brand_id": "vantage_001", "campaign": "VP Transition",
  "asset_type": "image_plate", "modality": "image", "source": "ai_generated",
  "folder": "Campaigns/VP Transition/Primitives/Image Plates",
  "filename": "plate_desk_warm_01.png", "content_b64": "..." }
// out
{ "asset_id": "ca_...", "drive_file_id": "1XyZ...",
  "drive_folder_id": "1Par...", "web_view_link": "https://drive.google.com/file/d/1XyZ.../view" }
```

### `drive.asset.list`
Query the library by brand/campaign/type/approval — this is how blueprint assembly and Scenario B find assets.

```json
// in
{ "brand_id": "vantage_001", "asset_type": "brand_asset", "approval_status": "approved",
  "tags": { "kind": "logo" } }
// out
{ "assets": [
    { "asset_id": "ca_logo_01", "drive_file_id": "1Logo...", "asset_type": "brand_asset",
      "modality": "image", "tags_json": { "kind": "logo", "variant": "primary" },
      "web_view_link": "..." }
  ], "count": 1 }
```

### `drive.asset.get`
Resolve an `asset_id` (or Drive file ID) to a downloadable URL / bytes. The render adapter calls this to pull every layer before the stitch; Scenario B calls it to hand a file to a channel plugin.

```json
// in
{ "asset_id": "ca_logo_01" }
// out
{ "asset_id": "ca_logo_01", "drive_file_id": "1Logo...",
  "download_url": "https://.../export?...", "mime_type": "image/svg+xml",
  "content_b64": "..." }   // content_b64 included only when caller requests inline bytes
```

---

## How the two acceptance scenarios use these

### Scenario A — brand asset → stitched channel creatives

```
1. drive.asset.list  brand=vantage type=brand_asset tags={kind:logo}   → logo asset_id
2. (primitive gen produces a background plate → drive.asset.upload)     → plate asset_id
3. blueprint.assemble references both asset_ids in one CompositionSpec
4. render adapter: drive.asset.get on each asset_id → Drive URLs → stitch
5. three render targets (banner 300×250 + 728×90, carousel 1080×1080 ×3, shortform 1080×1920)
6. drive.asset.upload each Export Package → Campaigns/VP Transition/Export Packages/
```

The logo file is fetched once and composited into all three formats. One source, three outputs.

### Scenario B — attach existing creative → single social post

```
1. drive.asset.list  brand=vantage approval_status=approved              → existing creative
2. operator: "post this to Instagram"
3. drive.asset.get  asset_id                                             → file
4. hand file to Meta plugin's post composition → approval-gated publish
```

No generation, no blueprint, no stitch. The library is useful on its own.

---

## Readiness & error states

- **Not connected:** any creative-factory job for the brand surfaces a setup blocker in Stream: "Connect Google Drive for Vantage Coaching to store creative assets." Mirrors existing `onboarding/status` readiness pattern.
- **Token expired:** `get_page_token()` auto-refreshes; if refresh fails, surface a reconnect blocker — never a silent fallback to another brand's Drive.
- **`drive.readonly` can't see client uploads:** files must live inside `Klaroha BOS/{Brand}/` (created by BOS, so `drive.file` covers them) or be explicitly shared. The setup step tells the operator exactly which folder to upload to.
- **Asset deleted in Drive but row exists:** `drive.asset.get` returns a `not_found` state; the `creative_assets` row is marked `archived`, not silently re-fetched.

---

## What this sample does NOT cover (later)

- Drive change-watching / webhook sync (V2 — for now BOS is the writer of record)
- Shared-drive (Team Drive) vs My Drive distinction (V1 assumes My Drive or a shared folder; Team Drive quirks deferred)
- Versioning of overwritten assets (Drive keeps revisions; BOS does not expose them in V1)
