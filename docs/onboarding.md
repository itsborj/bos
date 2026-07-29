# Onboarding & Postcraft Data Flow Investigation

> Update 2026-07-11: onboarding now creates the first live active campaign directly from the imported brand profile. The intended execution path is no longer “brand foundation first, campaign later.” New brands should enter Postcraft/Storyboard/Previs Motion with a real active campaign available by default.

## Problem Statement

**Issue:** Both Klaroha and Golden Gate Memorial get Postcraft blocked with the same error:
```
Postcraft blocked before draft/render: missing official_logo_drive_file_id, campaign_alignment
Failed · setup blocker · Preview in Stream
```

**Tested 2026-06-27:** CMO chat (gpt-4o-mini via OpenRouter) triggered for both brands. Neither can produce a full postcraft draft artifact — both hit the same two preflight blockers. The LLM does generate copy text (visible in tool call inputs), but the pipeline blocks before creating the reviewable draft artifact.

**Previous assumption was wrong:** Klaroha does NOT work either — both brands fail identically.

## Postcraft Preflight Requirements

From `/home/ubu/bos/plugins/postcraft/capabilities/postcraft/draft/module.py`, the `_postcraft_preflight()` function checks these **non-negotiable** inputs:

### 1. Brand Kit Loaded (Required) ✅ Both brands pass
- Brand ID and brand name present
- Brand voice/tone/colors or approved brand visual constraints present
- No generic placeholders like `brand` or `this brand`

### 2. Google Drive + Official Logo Resolved (Required) ❌ Both brands fail
- Google Drive connected for the selected Brand
- Validated Brand Kit Drive root folder present
- Real logo/wordmark Drive file ID available
- Google Drive credentials available to download logo
- **Postcraft must not rely on prompt text** - actual logo image must be sent to image model

### 3. Optional Brand Visual References (Optional)
- Mascot, product, people, location, vehicle/property, template/reference masters
- Injected as visual references alongside logo when relevant
- Missing optional refs do NOT block generation

### 4. Campaign Alignment Loaded (Required) ❌ Both brands fail
- Campaign ID and Campaign V2 sheet/alignment data present
- Brief carries campaign name/goal/audience/message angle
- **Even when a campaign exists and campaign_id is passed**, the `campaign_alignment` dict is not populated in the brief — see Campaign Alignment Gap below

## Postcraft Preflight Implementation

**Location:** `/home/ubu/bos/plugins/postcraft/capabilities/postcraft/draft/module.py`

```python
def _postcraft_preflight(brief: dict) -> list[str]:
    brand_kit = brief.get("brand_kit") if isinstance(brief.get("brand_kit"), dict) else {}
    brand_name = str(brand_kit.get("brand_name") or brand_kit.get("name") or brief.get("brand_name") or "").strip()
    generic_names = {"", "brand", "this brand", "this business"}
    colors = brand_kit.get("color_palette") or brand_kit.get("colors") or {}
    has_style = bool(colors or brand_kit.get("visual_tone") or brand_kit.get("tone") or brand_kit.get("voice") or brand_kit.get("brand_visual_constraints") or brief.get("brand_visual_constraints"))
    
    # CRITICAL: brand_spec is where logo_drive_file_id should come from
    brand_spec = _resolve_brand_spec(brief)
    logo_id = str(brand_spec.get("logo_drive_file_id") or "").strip()
    
    creds = brief.get("_channel_credentials") or {}
    drive_token = str(creds.get("google_drive_page_token") or creds.get("page_token") or creds.get("access_token") or "").strip()
    drive_root = str(creds.get("drive_root_folder_id") or brand_spec.get("drive_root_folder_id") or "").strip()
    
    alignment = _campaign_alignment(brief)
    has_campaign = bool(str(brief.get("campaign_id") or alignment.get("campaign_id") or "").strip() and alignment)
    
    missing: list[str] = []
    if not brand_kit.get("brand_id") or brand_name.lower() in generic_names or not has_style:
        missing.append("brand_kit")
")
    if not drive_token:
        missing.append("google_drive_credentials")
    if not drive_root:
        missing.append("google_drive_root_folder")
    if not logo_id:  # ← THIS IS WHERE GOLDENGATE FAILS
        missing.append("official_logo_drive_file_id")
    if not has_campaign:
        missing.append("campaign_alignment")
    return missing
```

### Brand Spec Resolution

```python
def _resolve_brand_spec(brief: dict) -> dict:
    """Read postcraft_brand_spec from brand_kit.brand_spec, brand_json, or workspace docs."""
    brand_kit = brief.get("brand_kit") or {}
    spec = brand_kit.get("brand_spec") or {}
    if spec:
        return spec
    for key in ("brand_spec", "brand_json"):
        val = brief.get(key)
        if isinstance(val, dict):
            return val
    docs = brief.get("workspace_documents") or brief.get("workspace_docs") or []
    for doc in docs:
        if isinstance(doc, dict) and doc.get("type") == "postcraft_brand_spec":
            content = doc.get("content") or doc.get("data") or {}
            if isinstance(content, dict):
                return content
    return {}  # ← GOLDENGATE RETURNS EMPTY DICT HERE
```

## Onboarding Data Flow (Correct Implementation)

### Step 1: Onboarding Extracts Logo Info

**Location:** `/home/ubu/bos/api/routers/onboarding.py:1012-1053`

```python
async def _brand_drive_asset_folder_metadata(db: AsyncSession, brand_id) -> dict:
    _empty = {"drive_connected": False, "brand_mark_configured": False, "brand_visual_assets": {}}
    if not brand_id:
        return _empty
    
    row = (await db.execute(
        select(SocialConnection).where(
            SocialConnection.brand_id == brand_id,
            SocialConnection.platform == "google_drive",
            SocialConnection.status == "connected",
        ).order_by(SocialConnection.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    
    if not row:
        return _empty

    meta = dict(row.token_meta_json or {})
    folder_id = str(meta.get("drive_root_folder_id") or "").strip()
    
    # EXTRACT LOGO FROM IMPRINT ASSET VALIDATION
    validation = meta.get("imprint_asset_validation") if isinstance(meta.get("imprint_asset_validation"), dict) else {}

    logo_files = validation.get("logo_files") or []
    first_logo = next((f for f in logo_files if isinstance(f, dict) and f.get("id")), None)

    result: dict = {
        "drive_connected": True,
        "brand_mark_configured": bool(first_logo),
        "brand_visual_assets": {
            "brand_mark":         _asset_category(logo_files, "Brand Mark"),
            "brand_character":    _asset_category(
                validation.get("brand_character_files") or validation.get("mascot_files") or [],
                "Brand Character",
            ),
            "hero_imagery":       _asset_category(validation.get("hero_imagery_files") or [], "Hero Imagery"),
            "lifestyle":          _asset_category(validation.get("lifestyle_files") or [], "Lifestyle & People"),
            "location":           _asset_category(validation.get("location_files") or [], "Location & Space"),
            "creative_references": _asset_category(validation.get("template_files") or [], "Creative References"),
            "supporting_visuals": _asset_category(validation.get("visual_asset_files") or [], "Supporting Visuals"),
        },
    }
    
    if folder_id:
        result["drive_root_folder_id"] = folder_id
        result["drive_root_name"] = meta.get("drive_root_name") or folder_id
    
    # ← CRITICAL: LOGO FILE ID IS STORED HERE
    if first_logo:
        result["brand_mark_file_id"] = str(first_logo.get("id") or "")
        result["brand_mark_file_name"] = str(first_logo.get("name") or "")
    
    return result
```

### Step 2: Onboarding Stores Logo in Campaign Brand Kit Metadata

**Location:** `/home/ubu/bos/api/routers/onboarding.py:1059-1160`

```python
async def generate_campaign_brand_kit(
    body: BrandKitRequest = BrandKitRequest(),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Generate required Campaign Brand Kit and store it as a draft document."""
    # ... setup code ...
    
    # ← EXTRACT ASSET METADATA INCLUDING LOGO
    asset_metadata = await _brand_drive_asset_folder_metadata(db, run_brand_id)
    
    # Generate campaign brand kit content
    content = _campaign_brand_kit_markdown(brief, title_fallback)
    title = _title_from_markdown(content, title_fallback)
    
    # Store document with metadata including logo info
    doc = WorkspaceDocument(
        workspace_id=ws.id,
        brand_id=run_brand_id,
        doc_type="campaign_brand_kit",
        title=title,
        content_markdown=content,
        status="draft",
        tags_json=["required_onboarding", "brand", "design", "campaign-readiness"],
        metadata_json={
            "version": "v1.0-draft",
            "generated_by_module": "onboarding.brand_guidelines",
            "generation_mode": "deterministic_local",
            "required_for_onboarding": True,
            **asset_metadata,  # ← brand_mark_file_id, brand_mark_file_name INCLUDED HERE
            "summary_fields": [
                "color_palette",
                "tone_of_voice",
                "typography_basics",
                "campaign_components",
                "platform_consistency_rules",
            ],
        },
        source_run_id=run.id,
    )
```

**Result:** `campaign_brand_kit.metadata_json` contains:
- `brand_mark_file_id`: Google Drive file ID of logo
- `brand_mark_file_name`: Logo filename
- `drive_root_folder_id`: Brand Kit Drive folder ID
- `drive_root_name`: Brand Kit Drive folder name
- `brand_visual_assets`: Asset categories

## Chat Data Flow (Gap Identified)

### Step 3: Chat Loads Campaign Brand Kit Metadata but Never Uses It

**Location:** `/home/ubu/bos/api/routers/chat.py:594-606`

```python
async def _brand_scoped_brief(db: AsyncSession, ws, brand: Brand | None, base: dict) -> dict:
    """Build a module brief scoped to the active Brand when available."""
    # ... brand profile setup ...
    
    docs = (await db.execute(
        select(WorkspaceDocument)
        .where(WorkspaceDocument.brand_id == brand.id)
        .order_by(WorkspaceDocument.updated_at.desc())
    )).scalars().all()
    
    by_type: dict[str, list[str]] = {}
    latest_kit_metadata: dict = {}  # ← METADATA IS LOADED
    
    for doc in docs:
        # ← CAPTURE CAMPAIGN BRAND KIT METADATA
        if doc.doc_type == "campaign_brand_kit" and not latest_kit_metadata:
            latest_kit_metadata = doc.metadata_json or {}
        
        if doc.content_markdown:
            by_type.setdefault(doc.doc_type, []).append(doc.content_markdown)
    
    brief["brand_guidelines_excerpt"] = "\n\n".join(by_type.get("brand_guideline", []))[:4000]
    brief["campaign_brand_kit_excerpt"] = "\n\n".join(by_type.get("campaign_brand_kit", []))[:4000]
    # ... other excerpts ...
    
    # ← CRITICAL GAP: latest_kit_metadata IS NEVER USED!
    return brief
```

**Problem:** `latest_kit_metadata` contains `brand_mark_file_id` but is never transformed into `brand_spec.logo_drive_file_id` format.

## CMO Tools Data Flow (Gap Continues)

### Step 4: CMO Tools Creates Brand Kit Without Logo Info

**Location:** `/home/ubu/bos/api/routers/cmo_tools.py:872-896`

```python
async def _brand_kit_for_tool(db: AsyncSession, brand_id: UUID | None) -> dict:
    """Small brand kit injected into native tool briefs.

    The system prompt gives of LLM brand context, but tools like postcraft need
    structured brand fields in their brief. Keep this lightweight; brand
    scaffold remains to full prompt context.
    """
    if not brand_id:
        return {}
    from models.workspace import Brand
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        return {}
    bj = brand.brand_json or {}
    
    # ← CRITICAL GAP: NO brand_spec CREATED, NO logo_drive_file_id
    return {
        "brand_id": str(brand.id),
        "brand_name": brand.name,
        "name": brand.name,
        "tone": bj.get("tone") or bj.get("brand_tone"),
        "voice": bj.get("voice"),
        "values": bj.get("values") or [],
        "color_palette": bj.get("color_palette") or bj.get("colors") or {},
        "visual_tone": bj.get("visual_tone") or bj.get("tone") or [],
        "negative_prompts": bj.get("negative_prompts") or [],
    }
```

### Step 5: Tool Brief Assembly

**Location:** `/home/ubu/bos/api/routers/cmo_tools.py:1225-1229`

```python
# Build brief from tool args, then merge server-owned context
brief: dict[str, Any] = dict(tool_args) if isinstance(tool_args, dict) else {}
if extra_brief:
    for k, v in extra_brief.items():
        if k not in brief and v not in (None, "", [], {}):
            brief[k] = v

# ← BRAND_KIT IS INJECTED BUT MISSING brand_spec
if brand_id and not isinstance(brief.get("brand_kit"), dict):
    kit = await _brand_kit_for_tool(db, brand_id)
    if kit:
        brief["brand_kit"] = kit
        brief.setdefault("brand_name", kit.get("brand_name"))
```

## Postcraft Data Flow (Failure Point)

### Step 6: Postcraft Resolves Brand Spec and Fails

**Location:** `/home/ubu/bos/plugins/postcraft/capabilities/postcraft/draft/module.py:29-45, 156-157`

One of these paths should provide `brand_spec.logo_drive_file_id`:

```python
def _resolve_brand_spec(brief: dict) -> dict:
    """Read postcraft_brand_spec from brand_kit.brand_spec, brand_json, or workspace docs."""
    brand_kit = brief.get("brand_kit") or {}
    
    # Path 1: brand_kit.brand_spec (not populated by _brand_kit_for_tool)
    spec = brand_kit.get("brand_spec") or {}
    if spec:
        return spec
    
    # Path 2: brief.brand_spec (not set by CMO tools)
    for key in ("brand_spec", "brand_json"):
        val = brief.get(key)
        if isinstance(val, dict):
            return val
    
    # Path 3: workspace_documents with type "postcraft_brand_spec" (doesn't exist for Goldengate)
    docs = brief.get("workspace_documents") or brief.get("workspace_docs") or []
    for doc in docs:
        if isinstance(doc, dict) and doc.get("type") == "postcraft_brand_spec":
            content = doc.get("content") or doc.get("data") or {}
            if isinstance(content, dict):
                return content
    
    return {} 11 ← GOLDENGATE HITS THIS: EMPTY DICT
```

```python
# Postcraft preflight checks for logo_drive_file_id
brand_spec = _resolve_brand_spec(brief)
logo_id = str(brand_spec.get("logo_drive_file_id") or "").strip()

if not logo_id:  # ← GOLDENGATE FAILS HERE
    missing.append("official_logo_drive_file_id")
```

## Why Klaroha Works

Klaroha likely has one of these:

1. **Manual `postcraft_brand_spec` workspace document** with type `"postcraft_brand_spec"` containing:
   ```json
   {
     "logo_drive_file_id": "1ABCxyz...",
     "drive_root_folder_id": "folder_id..."
   }
   ```

2. **Manual brand_spec** set somewhere that includes `logo_drive_file_id`

This bypasses the missing data flow bridge.

## Why Goldengate Fails

Goldengate relies on standard onboarding flow:

1. ✅ Onboarding extracts `brand_mark_file_id` from Drive validation
2. ✅ Onboarding stores it in `campaign_brand_kit.metadata_json`
3. ✅ Chat loads `campaign_brand_kit.metadata_json` into `latest_kit_metadata`
4. ❌ Chat never uses `latest_kit_metadata` to create `brand_spec`
5. ❌ `_brand_kit_for_tool` doesn't read `campaign_brand_kit` metadata
6. ❌ `_brand_kit_for_tool` doesn't create `brand_spec` with `logo_drive_file_id`
7. ❌ Postcraft's `_resolve_brand_spec` returns empty dict
8. ❌ Postcraft preflight fails on missing `logo_drive_file_id`

## The Missing Bridge

The system needs to transform:
- **Source:** `campaign_brand_kit.metadata_json.brand_mark_file_id`
- **Target:** `brief["brand_kit"]["brand_spec"]["logo_drive_file_id"]`

## Potential Fix Locations

### Option 1: Fix in Chat's `_brand_scoped_brief`

**File:** `/home/ubu/bos/api/routers/chat.py:594-606`

**Change:** Transform `latest_kit_metadata` into `brand_spec` format:

```python
async def _brand_scoped_brief(db: AsyncSession, ws, brand: Brand | None, base: dict) -> dict:
    # ... existing code ...
    
    by_type: dict[str, list[str]] = {}
    latest_kit_metadata: dict = {}
    for doc in docs:
        if doc.doc_type == "campaign_brand_kit" and not latest_kit_metadata:
            latest_kit_metadata = doc.metadata_json or {}
        if doc.content_markdown:
            by_type.setdefault(doc.doc_type, []).append(doc.content_markdown)
    
    # ← ADD THIS: Transform metadata into brand_spec
    if latest_kit_metadata:
        brand_spec = {}
        if latest_kit_metadata.get("brand_mark_file_id"):
            brand_spec["logo_drive_file_id"] = latest_kit_metadata["brand_mark_file_id"]
        if latest_kit_metadata.get("brand_mark_file_name"):
            brand_spec["logo_file_name"] = latest_kit_metadata["brand_mark_file_name"]
        if latest_kit_metadata.get("drive_root_folder_id"):
            brand_spec["drive_root_folder_id"] = latest_kit_metadata["drive_root_folder_id"]
        if latest_kit_metadata.get("drive_root_name"):
            brand_spec["drive_root_name"] = latest_kit_metadata["drive_root_name"]
        if brand_spec:
            brief["brand_spec"] = brand_spec
    
    # ... rest of function ...
    return brief
```

### Option 2: Fix in CMO Tools' `_brand_kit_for_tool`

**File:** `/home/ubu/bos/api/routers/cmo_tools.py:872-896`

**Change:** Read `campaign_brand_kit` metadata and create `brand_spec`:

```python
async def _brand_kit_for_tool(db: AsyncSession, brand_id: UUID | None) -> dict:
    if not brand_id:
        return {}
    from models.workspace import Brand, WorkspaceDocument
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        return {}
    bj = brand.brand_json or {}
    
    # ← ADD THIS: Read campaign_brand_kit metadata
    kit_doc = (await db.execute(
        select(WorkspaceDocument)
        .where(
            WorkspaceDocument.brand_id == brand_id,
            WorkspaceDocument.doc_type == "campaign_brand_kit"
        )
        .order_by(WorkspaceDocument.status.desc(), WorkspaceDocument.updated_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    
    kit_metadata = kit_doc.metadata_json if kit_doc else {}
    
    brand_spec = {}
    if kit_metadata.get("brand_mark_file_id"):
        brand_spec["logo_drive_file_id"] = kit_metadata["brand_mark_file_id"]
    if kit_metadata.get("brand_mark_file_name"):
        brand_spec["logo_file_name"] = kit_metadata["brand_mark_file_name"]
    if kit_metadata.get("drive_root_folder_id"):
        brand_spec["drive_root_folder_id"] = kit_metadata["drive_root_folder_id"]
    
    result = {
        "brand_id": str(brand.id),
        "brand_name": brand.name,
        "name": brand.name,
        "tone": bj.get("tone") or bj.get("brand_tone"),
        "voice": bj.get("voice"),
        "values": bj.get("values") or [],
        "color_palette": bj.get("color_palette") or bj.get("colors") or {},
        "visual_tone": bj.get("visual_tone") or bj.get("tone") or [],
        "negative_prompts": bj.get("negative_prompts") or [],
    }
    
    # ← ADD THIS: Include brand_spec if available
    if brand_spec:
        result["brand_spec"] = brand_spec
    
    return result
```

### Option 3: Fix Both (Recommended)

Implement both fixes to ensure data flows through entire pipeline:
1. Chat creates `brand_spec` for all briefs
2. CMO tools also create `brand_spec` for tool-specific briefs

## Campaign Alignment Gap

**Issue:** Even with active campaigns created and `campaign_id` passed in the chat request, Postcraft still reports `campaign_alignment` as missing.

**Tested:** Created active campaigns for both brands via `POST /api/campaigns`, then sent chat requests with `campaign_id` populated. Postcraft preflight still failed on `campaign_alignment`.

**Root cause:** Postcraft's `_campaign_alignment()` looks for `campaign_alignment` as a dict in the brief, not just `campaign_id`:

```python
def _campaign_alignment(brief: dict) -> dict:
    brand_kit = brief.get("brand_kit") or {}
    val = brief.get("campaign_alignment") or brand_kit.get("campaign_alignment") or brief.get("campaign_context") or {}
    return val if isinstance(val, dict) else {}
```

And the preflight check requires both `campaign_id` AND `alignment` to be truthy:

```python
alignment = _campaign_alignment(brief)
has_campaign = bool(str(brief.get("campaign_id") or alignment.get("campaign_id") or "").strip() and alignment)
```

**The gap:** CMO tools pass `campaign_id` (a UUID string) in the brief, but never populate a `campaign_alignment` dict with goal/audience/offer/message_angle. Postcraft needs the structured alignment object, not just the ID.

**Fix needed:** CMO tools' `_brand_kit_for_tool()` or the tool brief assembly should load campaign data and populate `campaign_alignment` with goal, audience, offer, and message_angle from the campaign record.

## CMO Chat Copy Generation Behavior

Even when Postcraft is blocked, the CMO chat LLM still generates copy text. This copy is visible in the `tool_calls[].input` fields of the response. The LLM produces brand-aware copy that respects each brand's configured voice/tone/values.

### Klaroha Copy (B2B Lead Management)

| Field | Value |
|---|---|
| **Headline** | "Capture Buyer Intent with Klaroha" |
| **Body** | "Are you a Fragmented High-Value Seller struggling with inconsistent follow-ups and poor visibility into your sales performance? Klaroha's Demand-Capture Infrastructure is engineered for clarity. Start routing your demand to the right people and see clear next steps for serious prospects." |
| **Template** | promo / square |
| **Tone match** | "clear and practical" / "authoritative" — uses "engineered for clarity", "route demand", "clear next steps" |

### Golden Gate Memorial Copy (Pre-Need Memorial Plans)

| Field | Variant 1 | Variant 2 |
|---|---|---|
| **Headline** | "Secure Your Family's Future Today" | "A Peaceful Place for Loved Ones" |
| **Body** | "At Golden Gate Memorial, we understand the importance of planning ahead. Our pre-need memorial plans offer a dignified and peaceful resting place for your loved ones. Don't leave your family unprepared—choose our Memorial Garden and Columbarium today for a confident and compassionate planning experience." | "Ensure a serene and dignified resting place for your family with our pre-need memorial plans. Golden Gate Memorial provides confidence and calmness in your planning process. Give your family the gift of preparedness. Contact us today!" |
| **CTA** | "Learn More" | "Contact Us" |
| **Tone match** | "warm, calm, respectful, emotionally intelligent" / "empathetic" — uses "dignified", "peaceful", "serene", "gift of preparedness" |

### Key Observations

1. **Brand voice fidelity is strong**: Both brands' copy reflects their configured voice/tone/values. Klaroha is direct and technical; Golden Gate is warm and family-focused.
2. **Golden Gate got 2 variants**: The CMO loop retried after the first attempt "failed" (blocked), producing a useful A/B of "urgency framing" vs "gift framing."
3. **Postcraft pipeline produces richer copy**: When the LLM knows it's calling `postcraft_draft`, it generates longer, more structured body copy with pain-point hooks and specific offer mentions. Pure text-only responses are shorter and more generic.
4. **Consistent latency**: ~11-14s for gpt-4o-mini via OpenRouter, regardless of brand.
5. **Provider**: Both used `openai` / `gpt-4o-mini` (routed through OpenRouter).

## Summary

| Component | Status | Issue |
|------------|---------|---------|
| Onboarding logo extraction | ✅ Working | Correctly extracts `brand_mark_file_id` |
| Onboarding metadata storage | ✅ Working | Stores in `campaign_brand_kit.metadata_json` |
| Chat metadata loading | ⚠️ Partial | Loads `latest_kit_metadata` but never uses it |
| CMO Tools brand kit creation | ❌ Missing | Doesn't create `brand_spec` with `logo_drive_file_id` |
| CMO Tools campaign alignment | ❌ Missing | Passes `campaign_id` but never populates `campaign_alignment` dict |
| Postcraft brand spec resolution | ❌ Failing | Returns empty dict — no `logo_drive_file_id` found |
| Postcraft campaign alignment | ❌ Failing | `campaign_alignment` dict never populated in brief |
| Postcraft preflight | ❌ Failing | Blocks on missing `logo_drive_file_id` AND `campaign_alignment` |
| LLM copy generation | ✅ Working | Brand-aware copy produced even when pipeline blocked |

**Root Causes (two gaps):**

1. **Logo gap:** Data flow gap between `campaign_brand_kit.metadata_json.brand_mark_file_id` and `brand_spec.logo_drive_file_id`.
2. **Campaign gap:** `campaign_id` is passed but `campaign_alignment` dict (with goal/audience/offer/message_angle) is never populated in the tool brief.

**Fixes Required:**
1. Transform onboarding-stored logo metadata into Postcraft-expected `brand_spec` format in either Chat or CMO Tools layer.
2. Populate `campaign_alignment` dict from campaign record data when `campaign_id` is present in the brief.
