# Plugin Lifecycle Gaps — Decision Doc

**Status:** Major gap — must be resolved before staging deploy or any further plugin activation work  
**Written:** 2026-06-09  
**Updated:** 2026-06-09 — code/state review incorporated  
**Context:** Joint analysis between agents after YouTube/Facebook social posting work surfaced activation policy gaps and confusing Admin state.

---

## Agreed deliverables — revised after code/state review

The earlier split that parked org-wide activation safety was wrong because this deployment already has multiple Brands (`Klaroha`, `MotorMoto`, `Mactan Group`). Org-wide activation is already leaking capabilities across Brands.

| # | Deliverable | Type | Gate |
|---|-------------|------|------|
| D1 | Copy 6 workflow plugins from `api/plugins/` → `~/bos-plugins/`: `youtube`, `meta`, `media-image`, `media-video`, `creative-factory`, `google-drive` | Operator action | Now |
| D2 | Remove `KLAROHA_LOAD_INTERNAL_PLUGINS=true` from `.env`, restart API | Operator action | Now |
| D3 | Clear 6 org-wide `plugin_activations` rows; recreate brand-scoped for Klaroha only | DB + API action | Now / before staging deploy |
| D4 | Stop `GET /plugins` from auto-creating `plugin_activations` rows | Code fix | Now |
| D5 | Make accidental org-wide activation impossible from normal API/UI flow | Code + UI/API contract fix | Now |
| D6 | Verify MotorMoto and Mactan inherit zero social/media plugin capabilities | Validation | Now |
| D7 | Update external plugin docs/manifests to current `credential_slots` contract | Docs/plugin package fix | Now |
| D8 | Fix brand-scoped plugin readiness display in `GET /plugins` / Admin | Code/UI fix | Before relying on Admin readiness |

## Parked — agreed not to build yet

| Item | Why parked |
|------|-----------|
| Dependency activation chain in Admin | Useful architecture feature, but not required to stop current leakage once activation is explicit and brand-scoped |
| `provider_keys` credential scope (brand vs workspace) | Phase 2; still important for billing/isolation before client onboarding |
| Marketplace / Available plugins | Not part of lifecycle repair |
| Full lockfile / release-integrity ledger | Extension-host maturity, not immediate activation leak fix |
| Hook system / full extension host | Valid future architecture, not needed for this containment |

---

## What the architecture intends

From `BITE.md`, `PLUGIN_SDK.md`, and `plugin_loader.py`:

```
api/plugins/   → SDK examples / bundled reference code. NOT runtime-installed by default.
~/bos-plugins/ → Operator-installed external plugins. This is the operational truth.

Installed ≠ Active.
Active must be explicit.
Inactive plugins must not enter the CMO manifest.
Missing credentials must not hide an active plugin — plugin returns setup_blocker artifact.
```

Brand-scoped activation is the design intent: a plugin activated for Brand A is invisible to Brand B unless explicitly activated there too.

---

## What actually happened (2026-06-09 local state)

### Current database reality — not single-brand

This deployment currently has three Brands:

```text
Klaroha      c1cb6603-e8d4-4e63-8995-640453d5b50b
MotorMoto    e44fc8fd-84e6-4cd6-a813-73da5cb63881
Mactan Group 7a3a3535-9f5b-4035-a5e7-00e2ec8d9b1c
```

Therefore any `brand_id=NULL` activation is already multi-brand leakage, not a future risk.

Observed manifest behavior from actual code/state:

```text
Klaroha, MotorMoto, and Mactan all inherit the same 6 active plugins:
channel.meta, channel.youtube, creative.factory, google.drive, media.image, media.video
```

That means social/media capabilities are visible for Brands that were never explicitly activated for those plugins.

### Issue 1 — Internal flag dragged 18 plugins into Admin

`KLAROHA_LOAD_INTERNAL_PLUGINS=true` was added to `.env` to restore social posting (YouTube, Meta, ClickUp). This flag makes `scan_plugins()` load all of `api/plugins/` alongside `~/bos-plugins/`. Result: 18 bundled examples appear as installed plugins in Admin → Specialists. The operator expected to see 3; they saw 18.

The actual external install root (`~/bos-plugins/`) currently contains only:

```text
gbp-completeness/
hello/
```

The workflow plugins used for the validated social path still live only in `api/plugins/`:

```text
media-image/
media-video/
creative-factory/
google-drive/
meta/
youtube/
```

ClickUp also still lives in `api/plugins/`; copy it only if PM sync is part of active ops. The core problem is bundled examples being used as production plugins.

### Issue 2 — `brand_id=NULL` activation is org-wide

The restore work activated 6 plugins with `brand_id=null`:
- `media.image`, `media.video`, `creative.factory`, `channel.meta`, `google.drive`, `channel.youtube`

`brand_id=NULL` in `plugin_activations` = org-level activation. These plugins are now active for **every brand** unless a brand-specific `inactive` row overrides them. This works fine for a single-brand deployment (Klaroha only) but is the wrong default for the multi-brand model BOS is built for. When a second brand is onboarded, they inherit these activations automatically.

### Issue 3 — `GET /plugins` auto-creates inactive rows

When `GET /plugins` runs, the router auto-creates an `inactive` activation row for every loaded plugin that has no row yet. This makes the DB look like every plugin has a managed lifecycle state immediately — but those rows were never explicitly created by an operator. It conflates "plugin loaded for display" with "plugin has been acknowledged by the operator."

---

## Plain-language diagnosis

The operator experience was: "I tried to activate a small number of social plugins, then almost everything looked activated/installed immediately."

The precise failure is a combination of four lifecycle leaks:

1. **Visibility leak:** `KLAROHA_LOAD_INTERNAL_PLUGINS=true` makes every bundled `api/plugins/` package look installed. This is why Admin suddenly showed 18 plugins instead of the expected small external set.
2. **Read-side write leak:** `GET /plugins` auto-creates `plugin_activations` rows with `status=inactive` for every loaded plugin. This does not activate them, but it makes the DB look as if every plugin was lifecycle-managed by an operator action.
3. **Scope leak:** activations were sent with `brand_id: null`, which means org-wide active. A selected brand then inherits those plugins, so the UI can show them as active for that brand even though no brand-specific activation happened.
4. **Dependency expansion leak:** the requested social workflow required more than the two visible channel plugins. Facebook image + YouTube video needed `media.image`, `media.video`, `creative.factory`, `google.drive`, `channel.meta`, and `channel.youtube`. Activating dependencies manually is understandable for a repair test, but it must not be hidden or global.

Current local truth after the restore test:

```text
Loaded plugins: 18
Active org-wide: 6
  channel.meta
  channel.youtube
  creative.factory
  google.drive
  media.image
  media.video
Inactive rows: 12
```

So the system did not literally mark all 18 active, but it did make all 18 visible and inserted rows for all of them. More importantly, it did mark 6 workflow plugins active org-wide, and those 6 are now inherited by all existing Brands. For an operator, that is close enough to "almost everything activated" to be a serious lifecycle bug.

---

## Code review findings — actual violations to fix

These are from the current code/state, not architecture speculation.

### C1 — `GET /plugins` mutates lifecycle state

File: `api/routers/plugins.py`

Current behavior:

```python
# D4: directory present + no activation row means installed/inactive. Persist
# an org-level inactive row so Admin can show explicit lifecycle state.
...
db.add(PluginActivation(plugin_id=plugin_id, brand_id=None, status="inactive"))
```

Violation: a read endpoint creates lifecycle rows. This conflates display with operator acknowledgement and creates stale rows that can become meaningful when a plugin with the same ID is later installed.

Required behavior: `GET /plugins` should synthesize `installed/inactive` in its response when no row exists, without writing to DB.

### C2 — Activation defaults to org-wide

File: `api/routers/plugins.py`

Current behavior:

```python
class ActivateRequest(BaseModel):
    brand_id: Optional[str] = None  # None = org-level activation
```

Violation: missing `brand_id` silently means active for all Brands.

Required behavior: normal activation must require a concrete `brand_id`. Org-wide activation, if retained, must require a separate explicit confirmation such as `scope: "org"` plus `confirm_org_wide: true`.

### C3 — Admin deactivate cannot clean org-wide activation

File: `web/src/api/client.ts`

Current behavior:

```ts
deactivatePlugin(pluginId, brandId)
  → DELETE /plugins/{id}/activate?brand_id=<selectedBrand>
```

If a plugin is org-active, deactivating from a selected Brand creates/updates only a brand-specific inactive row or leaves the org-wide active row in place for every other Brand. The UI needs a way to identify and remove org-wide active state, or org-wide activation must be forbidden in normal flows.

### C4 — Brand-scoped activation breaks `/verticals`

File: `api/routers/verticals.py`

Current behavior:

```python
active_plugin_ids = await get_active_plugin_ids(db, None)
```

This only checks org-level activation. If the system moves to brand-scoped activation, `/verticals` hides plugins active for a Brand. Conversely, `/modules/{module_id}` returns module detail without activation filtering at all.

Required behavior: module/vertical listing must either accept `brand_id` and filter for that Brand, or be clearly documented as a raw registry/debug endpoint not used for dispatch/readiness.

### C5 — Plugin readiness is not brand-scoped

File: `api/routers/plugins.py`

Current behavior preloads connected social platforms across all Brands:

```python
connected_social_platforms = set(select(SocialConnection.platform).where(status == "connected"))
```

This lets Brand A's YouTube/Drive/Facebook connection make Brand B's plugin look configured. It also treats any matching social platform as enough, instead of all required social slots being connected for the selected Brand.

Required behavior: readiness should be computed for the selected Brand, or labeled as global/summary only. It must not imply Brand readiness using another Brand's tokens.

### C6 — External plugin docs/manifests are stale

Path: `~/bos-plugins/README.md` and current external plugins.

The README and external manifests still teach/use legacy fields:

```json
requires_social_connection
requires_platform_vars
```

Current loader resolves credentials from `credential_slots`. External plugins using only old fields may load but receive no credentials via the new resolver. Example: `gbp-completeness/channel.json` declares `requires_social_connection: ["google_business"]`, but no `credential_slots`, so its module will not receive `google_business` token injection under the new resolver.

Required behavior: update external plugin docs and manifests to `credential_slots`, or add a compatibility adapter deliberately. Do not let stale sample docs be the source of new broken plugins.

### C7 — Current lifecycle doc had a false assumption

The previous doc text said some issues could wait until a second Brand exists. That is false: this deployment already has MotorMoto and Mactan Group, and both inherit the org-wide active social/media plugins today.

### C8 — Social connection documentation may be stale

A current `social_connections` DB check showed Klaroha has Gmail, Google Business, Google Calendar, Google Drive, and YouTube rows, but did not show a Facebook row in that query output. Earlier SOCIAL notes said Facebook was connected. Before any Facebook retry, re-check the actual `social_connections` table and Admin connection state. Do not rely on stale docs for connection status.

---

## Points of agreement

Both agents agree:

- **The flag as production workaround is wrong.** `KLAROHA_LOAD_INTERNAL_PLUGINS=true` is documented as a local compatibility shim. Using it to reach production plugins (YouTube, Meta, ClickUp) crosses the intended architecture boundary.
- **`brand_id=NULL` activation spreads to all brands.** This is the dangerous part of the current state, not the credentials.
- **Auto-created inactive rows are not activation.** They are noise that makes the DB state look managed when it isn't.
- **The fix is activation policy and UI clarity, not platform code rewrites.** The plugin loading code is working as designed. The gap is in how activation is requested and displayed.

---

## Points of disagreement / additions

### Pushback: The code also needs a targeted fix

"Fix should be around activation policy and UI clarity, not platform code" — partially agreed, but `GET /plugins` auto-creating inactive rows IS a code behavior that should change. Displaying a plugin and registering it in `plugin_activations` are different operations. The auto-row creation should be removed; rows should only exist when an operator explicitly calls `POST /plugins/{id}/activate` or `DELETE /plugins/{id}/activate`.

### Addition: Credential scope risk exists alongside activation scope risk

With `brand_id=NULL` activation, `media.image` (ByteDance key, workspace-level credential) will serve any brand. In a single-brand deployment this is harmless. In a multi-brand deployment, Brand B would use the same ByteDance key as Brand A — including for billing. Credential rows in `provider_keys` are currently workspace-scoped (no `brand_id` on the ByteDance row). Activation scope and credential scope are separate concerns that both need to be addressed for multi-brand.

### Addition: The near-term visibility fix is a move, but lifecycle fixes are still required

The immediate reason Admin shows 18 plugins is that workflow plugins live in `api/plugins/` while `KLAROHA_LOAD_INTERNAL_PLUGINS=true` is enabled. Moving only the real workflow plugins to `~/bos-plugins/` and removing the flag fixes Admin visibility.

However, this is not independent of activation policy. If the 6 org-wide active rows are not cleared first, copying those same plugin IDs to `~/bos-plugins/` will preserve global activation because activation is keyed by `plugin_id`, not source path.

Safe order:

1. Clear/deactivate current org-wide active rows for the 6 workflow plugins.
2. Copy the 6 workflow plugins to `~/bos-plugins/`.
3. Remove `KLAROHA_LOAD_INTERNAL_PLUGINS=true` from `.env`.
4. Restart API.
5. Activate the 6 plugins for Klaroha brand only.
6. Verify MotorMoto and Mactan do not see those plugin capabilities.

### Addition: Docs conflict is an implementation gap, not a true doc conflict

The other agent identified a conflict: "Plugin Host MVP docs say bundled plugins are skipped unless flag set; some higher-level docs say bundled plugins may auto-activate org-wide." After review, no higher-level doc explicitly grants bundled plugins auto-activate rights. The apparent conflict comes from the auto-row creation in `GET /plugins` — that's an implementation artifact, not a documented design decision. The plugin-host rule wins by default; no doc change needed, only the code change to stop auto-creating rows.

---

## Required fixes

### Phase 0 — Safe containment order

Moving production-use plugins out of `api/plugins/` and into `~/bos-plugins/` is necessary containment. It reduces Admin noise and restores the intended installed-plugin root. It is **not** the full lifecycle fix.

**Step 0.** Clear the current org-wide active rows first. Do not copy the plugins before clearing these rows, or the same plugin IDs will remain active globally after they load from `~/bos-plugins/`.

```sql
UPDATE plugin_activations
SET status = 'inactive', updated_at = now()
WHERE brand_id IS NULL
  AND plugin_id IN (
    'media.image',
    'media.video',
    'creative.factory',
    'google.drive',
    'channel.meta',
    'channel.youtube'
  );
```

**Step 1.** Copy only the plugins actually needed for the current workflow from `api/plugins/` to `~/bos-plugins/`:

```bash
cp -r api/plugins/youtube          ~/bos-plugins/
cp -r api/plugins/meta             ~/bos-plugins/
cp -r api/plugins/media-image      ~/bos-plugins/
cp -r api/plugins/media-video      ~/bos-plugins/
cp -r api/plugins/creative-factory ~/bos-plugins/
cp -r api/plugins/google-drive     ~/bos-plugins/
# Copy ClickUp only if PM sync is part of the active ops path:
# cp -r api/plugins/clickup        ~/bos-plugins/
```

**Step 2.** Remove `KLAROHA_LOAD_INTERNAL_PLUGINS=true` from `.env`.

**Step 3.** Restart the API: `docker compose up -d api`.

**Step 4.** Activate the workflow plugins for Klaroha brand specifically:

```text
POST /plugins/{id}/activate
body: { "brand_id": "c1cb6603-e8d4-4e63-8995-640453d5b50b" }
```

**Step 5.** Verify MotorMoto and Mactan do not inherit plugin capabilities.

Expected containment result:

```text
Admin → Specialists shows external installed plugins only.
Bundled examples disappear.
No org-wide active rows exist for the workflow plugins.
```

This containment step does **not** solve:

```text
GET /plugins write side effect
brand_id=NULL org-wide activation footgun unless API/UI is patched
unclear org-active vs brand-active UI
brand-scoped readiness bugs in GET /plugins
stale external plugin docs/manifests using old credential fields
workspace-scoped provider credential leakage across future brands
manual hidden activation of workflow dependencies
```

---

### Phase 1 — Mandatory code/API fixes

These are mandatory because the current deployment already has multiple Brands.

1. **Stop read-side writes.** `GET /plugins` must not create `plugin_activations` rows. Missing rows should be rendered as installed/inactive in the response only.
2. **Block accidental org-wide activation.** Require a concrete `brand_id` for normal activation. Org-wide activation, if retained, must require explicit `scope: "org"` plus `confirm_org_wide: true` or equivalent.
3. **Fix Admin deactivation semantics.** If org-wide activation exists, the UI/API must let an operator remove the org-wide row; selected-brand deactivation is not enough.
4. **Fix module listing semantics.** `/verticals` currently filters with `brand_id=None`; either accept `brand_id` and filter for that Brand, or mark `/verticals`/`/modules` as raw registry debug endpoints not used for readiness/dispatch.
5. **Fix brand-scoped readiness.** `GET /plugins` must not mark social-token credentials configured because some other Brand has a connection. Readiness must be scoped to selected Brand or clearly labeled as global summary.
6. **Update external plugin package docs/manifests.** `~/bos-plugins/README.md` and external plugin `channel.json` examples must use `credential_slots`, or the loader must intentionally support a compatibility adapter.

Acceptance for staging gate:

```text
Admin shows only externally installed plugins.
GET /plugins creates zero DB rows.
Activation without brand_id fails unless explicit org-wide confirmation is present.
No org-wide active rows remain for social workflow plugins.
The 6 social workflow plugins are active for Klaroha brand specifically.
MotorMoto and Mactan see no inherited social/media plugin capabilities.
Brand readiness does not use another Brand's SocialConnection tokens.
External plugin docs/manifests match current credential_slots contract.
```

---

### Phase 2 — Multi-brand credential policy before client onboarding

Activation scope and credential scope are separate. Fixing activation does not fix billing/data isolation.

Before a second real client brand uses media generation or external publishing:

1. Decide whether provider keys are workspace/org shared or brand-scoped.
2. If shared, Admin must label them as shared infrastructure credentials.
3. If brand-scoped billing/isolation is required, `provider_keys` / backend override resolution needs brand-aware credential selection.
4. Publish/read tokens must remain brand-scoped through `social_connections.brand_id`.

Do not call workspace-scoped provider credentials safe for multi-brand until this decision is explicit.

---

## Non-negotiable rules from this incident

- Do not use `KLAROHA_LOAD_INTERNAL_PLUGINS=true` as a production or staging restore mechanism.
- Do not activate with `brand_id: null` as a shortcut when only specific brands need a plugin.
- Operator experience rule: Admin → Specialists must show only externally installed plugins in normal operation.

---

## Spec references

- Plugin loader contract: `api/plugin_loader.py` — `scan_plugins()`, `_LOAD_INTERNAL_PLUGINS`
- Activation table: `api/models/plugin_activation.py` — `plugin_activations` (plugin_id, brand_id, status)
- Admin UI: `web/src/pages/admin/AdminModules.tsx` — `specialists` useMemo, line 422
- BITE.md § Everything is a Package
- `specs/001-thin-core-proof/tasks.md` — T035/T036 (activate/deactivate endpoints), T096–T099 (arch cop), SDK-020–SDK-025
