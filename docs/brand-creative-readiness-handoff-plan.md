# Brand Creative Readiness — Remediation and Validation Handoff Plan

**Prepared:** 2026-07-26  
**Target deployment:** `http://127.0.0.1:8090`  
**Scope:** Google Drive, Postcraft, Storyboard, and Previs Motion readiness for Klaroha, Golden Gate Memorial, and MotorMoto.

## 1. Objective

Make each Brand operationally ready to:

1. Read and write assets through its own Google Drive Brand Kit root.
2. Generate an approved Postcraft image and persist it to the correct Drive folder.
3. Generate an approved Storyboard image and persist it to the correct Drive folder.
4. Transition an approved Storyboard artifact into Previs Motion and persist the resulting video to the correct Drive folder.
5. Report readiness accurately through the APIs exposed behind port `8090`.

Readiness must be Brand-scoped. A connection, activation, asset, campaign, or provider belonging to one Brand must never make another Brand appear ready.

## 2. Current verified baseline

All checks below were executed through `http://127.0.0.1:8090/api`.

### Deployment

- `GET /api/` returns `200`; API and database report `ok`.
- Requests without `X-API-Key` return `401`.
- `GET /api/modules/postcraft.render` returns `200`.
- `GET /api/modules/storyboard.render` returns `200`.
- `GET /api/modules/storyboard.motion.render` returns `200`.
- Relevant mocked regression suite: `78 passed`.

### Brand status

| Brand | Drive | Postcraft | Storyboard | Previs Motion |
|---|---|---|---|---|
| Klaroha | `DRIVE_REAUTH_REQUIRED` | Active but blocked | Active but blocked | Active but blocked |
| Golden Gate Memorial | `DRIVE_REAUTH_REQUIRED` | Active but blocked | Active but blocked | Active but blocked |
| MotorMoto | `DRIVE_REAUTH_REQUIRED` | Inactive and blocked | Inactive and blocked | Inactive and blocked |

For every Brand, `GET /api/onboarding/status?brand_id=...` currently reports:

- `brand_profile_configured: true`
- `campaign_brand_kit_approved: true`
- `live_campaign_present: true`
- `drive_connected: false`
- `brand_mark_configured: false`
- Postcraft, Storyboard, and Previs modules `ready: false`

All three Brand Kit resource endpoints currently return zero indexed resources.

### Live provider checks

`POST /api/providers/check` was executed for every Brand:

- OpenAI OAuth: `ok`
- ByteDance: `ok`
- Gemini: `error — credential rejected or provider unreachable`

Current backend overrides are:

- `postcraft.render` → OpenAI / `gpt-image-2`
- `storyboard.render` → OpenAI / `gpt-image-2`
- `storyboard.motion.render` → Gemini / `veo-3.1-generate-preview`

There is a reporting inconsistency: the live Gemini check repeatedly fails for all Brands, while `GET /providers` can still report Gemini as `live` for some Brand scopes.

### Campaign alignment

- Klaroha has two active campaigns. Calling Postcraft alignment without `campaign_id` returns `POSTCRAFT_CAMPAIGN_AMBIGUOUS`. Both explicit campaigns resolve, but audience and offer are empty.
- Golden Gate Memorial has two active campaigns. Calling alignment without `campaign_id` returns `POSTCRAFT_CAMPAIGN_AMBIGUOUS`. Both explicit campaigns resolve; audience is populated but offer is empty.
- MotorMoto has one active campaign and resolves automatically; audience and offer are empty.

## 3. Relevant implementation contracts

Do not weaken these generation gates.

### Postcraft

`plugins/postcraft/capabilities/postcraft/render/module.py`

Requires:

- approved Brand Kit with real Brand identity/style;
- Google Drive credentials;
- validated Drive root;
- official logo Drive file ID;
- selected Campaign alignment;
- explicit CMO-level text approval before rendering.

### Storyboard

`plugins/storyboard/capabilities/storyboard/json/render/module.py`

Requires:

- working image-generation provider credential;
- Google Drive credentials;
- validated Drive root;
- approved Storyboard text before rendering.

### Previs Motion

`plugins/previs-motion/capabilities/storyboard/motion/render/module.py`

Requires:

- working selected video provider credential;
- Google Drive credentials;
- validated Drive root;
- official logo Drive file ID;
- approved Storyboard artifact/input.

`storyboard.motion.render` is intentionally `allowed_from_chat: false` in the capability-level SKILL. It must remain an artifact action/transition after Storyboard approval, not a first-pass chat tool.

## 4. Work plan

### Phase A — Capture a reproducible baseline

1. Confirm the compose stack and `8090` listener are healthy.
2. Obtain the runtime API key into process memory without printing or logging it.
3. Save secret-free JSON responses for each Brand from:
   - `/api/onboarding/status?brand_id=...`
   - `/api/plugins?brand_id=...`
   - `/api/capability-manifest?brand_id=...`
   - `/api/social/connections?brand_id=...`
   - `/api/brands/{brand_id}/brand-kit/resources`
   - `/api/campaigns?brand_id=...`
   - `/api/postcraft/campaign-alignment?brand_id=...`
4. Record provider selection from `/api/settings/backends` and live results from `/api/providers/check`.
5. Do not place credentials, OAuth tokens, refresh tokens, or raw environment files in reports.

**Deliverable:** timestamped, secret-free baseline JSON and Markdown summary.

### Phase B — Correct readiness-reporting defects

#### B1. Provider check scope consistency

Investigate `api/routers/providers.py`, especially:

- `_provider_rows_for_scope()`;
- `list_providers()`;
- `check_key()` and its lookup of the row receiving `last_check_status`.

The effective credential checked by `/providers/check` and the row whose status is returned by `/providers` must be the same Brand-scoped credential, including workspace-level API-key fallback when no Brand override exists.

Add tests covering:

1. Brand-specific credential wins over workspace credential.
2. Workspace API-key fallback is checked and its health metadata is updated consistently.
3. Workspace OAuth fallback behaves consistently.
4. Failed check cannot leave the same effective credential displayed as `live`.
5. Health metadata for one Brand-specific key does not alter another Brand's key.

#### B2. Onboarding/module readiness must use effective provider health

Inspect the readiness assembly behind `/onboarding/status`.

Required behavior:

- A stored key or configured provider means **configured**, not necessarily **live**.
- A module requiring a provider must not report ready when its selected provider has a current explicit failed health check.
- Drive connection/root/logo requirements remain independent hard gates.
- Readiness reasons should identify the failed prerequisite without exposing secrets.

Do not make transient provider health the only permanent source of truth. Preserve the distinction among configured, unverified, live, expired, and failed.

#### B3. Add a reusable, read-mostly assessment command

Add a script such as:

`api/scripts/check_brand_creative_readiness.py`

It should:

- accept `--base-url`, defaulting to `http://127.0.0.1:8090/api`;
- accept an API key through an environment variable or secure prompt, never a positional CLI argument;
- enumerate Brands or accept repeated `--brand-id` values;
- check stored readiness and optionally run live provider/Drive probes;
- support `--no-live-checks` and `--json-output`;
- clearly disclose that a failed Drive auth probe may mark the connection `needs_reauth`, and provider checks update health metadata;
- never initiate OAuth, select folders, activate plugins, alter campaigns, or generate media.

**Deliverables:** code fix, focused tests, reusable assessment script, and documented command examples.

### Phase C — Operator-owned Google Drive recovery

OAuth and Brand folder selection require an authorized operator. Do not automate or bypass consent.

For each Brand:

1. Reconnect Google Drive from Admin → Brands → Integrations.
2. Verify the connection is stored against the correct `brand_id`.
3. Select a dedicated Brand Kit root below My Drive; do not use `root` itself.
4. Ensure the selected folder contains at least one image with a recognizable official name such as `logo`, `wordmark`, `brandmark`, or `mark`.
5. Submit the selected folder through `/api/social/drive/root` or the normal UI.
6. Confirm root validation indexes assets and sets:
   - `drive_root_folder_id`;
   - `drive_root_name`;
   - `imprint_asset_validation.status: ok`;
   - an official logo/Brand mark file ID.
7. Verify real reads through:
   - `GET /api/social/drive/folders?brand_id=...`
   - `GET /api/social/drive/images?brand_id=...&media_type=image`
8. Verify `GET /api/brands/{brand_id}/brand-kit/resources` returns the Brand's indexed assets.

Do not copy a Drive token, folder ID, or logo ID from one Brand to another.

**Acceptance criteria per Brand:** Drive folder and image calls return `200`; onboarding reports `drive_connected: true` and `brand_mark_configured: true`; indexed resources are non-empty.

### Phase D — Resolve Brand activation and Campaign setup

#### Klaroha

- Keep Postcraft, Storyboard, and Previs active.
- Decide which active Campaign should be the default execution target, or require explicit Campaign selection in every creative request.
- Do not silently choose between two active campaigns.
- Complete audience and offer fields for the selected Campaign where business truth is available.

#### Golden Gate Memorial

- Keep Postcraft, Storyboard, and Previs active.
- Decide which active Campaign should be selected, or require explicit selection.
- Complete the offer field for the selected Campaign.

#### MotorMoto

- Activate `creative.postcraft`, `channel.storyboard`, and `channel.previs_motion` for MotorMoto.
- Activate Google Drive support as required by the product's plugin policy.
- Complete audience and offer fields where business truth is available.

Use Brand-scoped activation. Do not activate plugins org-wide as a shortcut.

**Acceptance criteria:** the Brand-filtered capability manifest contains `postcraft.render` and `storyboard.render` for all three Brands. Previs remains an artifact transition and need not appear as a direct chat capability.

### Phase E — Repair or replace the Previs provider

The current Gemini/Veo backend fails its live credential check. Present the operator with two explicit options:

1. Repair/replace the Gemini credential and verify `POST /api/providers/check` returns `ok`; or
2. Change `storyboard.motion.render` to the already healthy ByteDance provider and an installed Seedance model.

Recommended short path, subject to operator approval:

- provider: ByteDance/ModelArk;
- model: the installed Seedance model declared by `plugins/previs-motion/channel.json`.

After changing the backend, verify the effective provider/model through `/api/settings/backends` and rerun the live provider check. Do not generate video during this phase.

**Acceptance criteria:** the selected Previs provider returns `ok`, and readiness resolves the same provider/model that execution will use.

### Phase F — Zero-media-cost readiness validation

Run these checks through port `8090` for every Brand:

1. `GET /api/` → `200`, DB `ok`.
2. `GET /api/onboarding/status?brand_id=...`.
3. `GET /api/plugins?brand_id=...`.
4. `GET /api/capability-manifest?brand_id=...`.
5. `GET /api/social/drive/folders?brand_id=...` → `200`.
6. `GET /api/social/drive/images?brand_id=...` → `200` and Brand-correct assets.
7. `GET /api/brands/{brand_id}/brand-kit/resources` → official logo plus indexed resources.
8. `POST /api/providers/check` for each selected generation provider → `ok`.
9. `GET /api/postcraft/campaign-alignment` with explicit Campaign IDs → `200` and correct Brand ownership.
10. Confirm MotorMoto's creative plugins are active and dispatchable.
11. Confirm Previs remains available through the approved Storyboard artifact transition.

No Postcraft image, Storyboard image, or Previs video should be generated in this phase.

### Phase G — Paid end-to-end smoke tests

Do not begin without explicit operator confirmation of provider spend.

For each Brand, use a uniquely identifiable, harmless test brief and execute serially:

1. **Postcraft**
   - Write the creative text in CMO chat.
   - Obtain explicit operator approval.
   - Render one image.
   - Confirm the official logo and correct Brand styling were used.
   - Confirm upload under that Brand's Drive `Postcraft/` folder.

2. **Storyboard**
   - Write and approve one short Storyboard/script.
   - Render one Storyboard image.
   - Confirm upload under the Brand's Drive `Storyboard/` folder.

3. **Previs Motion**
   - Approve the Storyboard artifact for motion.
   - Trigger `generate_video` from the artifact action, not first-pass chat.
   - Use the shortest acceptable duration/resolution for the smoke test.
   - Confirm upload under the Brand's Drive `Previs Motion/` folder.

4. Verify Run/RunTrace records, approval gates, provider attempts, artifact MIME types, Drive file IDs, and web-view links.
5. Verify no artifact, logo, Campaign, Drive root, or provider override crossed Brand boundaries.

Stop immediately on wrong-Brand assets, a missing approval gate, failed Drive persistence, or unexpected provider spend.

## 5. Test plan

Run at minimum:

```bash
cd /tmp
PYTHONPATH=/home/ubu/bos/api python -m pytest -q \
  /home/ubu/bos/api/tests/test_google_drive_brand_kit_index.py \
  /home/ubu/bos/api/tests/test_google_drive_pagination.py \
  /home/ubu/bos/api/tests/test_plugin_host_invariants.py \
  /home/ubu/bos/api/tests/test_postcraft_brand_templates.py \
  /home/ubu/bos/api/tests/test_postcraft_render_mime.py \
  /home/ubu/bos/api/tests/test_storyboard_quality_gate.py \
  /home/ubu/bos/api/tests/test_storyboard_size_normalization.py \
  /home/ubu/bos/api/tests/test_previs_motion_modelark_payload.py \
  /home/ubu/bos/api/tests/test_cmo_v2_storyboard_endpoints.py
```

Add focused tests for provider scope/status consistency and the new assessment script. Run broader provider, plugin activation, onboarding, campaign selection, and artifact action tests when those areas change.

## 6. Definition of done

The work is complete only when:

- all three Brands pass real Drive folder and image reads;
- all three have a validated Brand root and official Brand mark;
- Postcraft and Storyboard are active and dispatchable for all three Brands;
- Previs is active for all three and reachable only through the approved artifact transition;
- each selected generation provider passes a live check;
- `/providers`, `/onboarding/status`, plugin readiness, and actual live checks agree;
- Campaign selection is unambiguous or always explicit;
- one approved Postcraft image, Storyboard image, and Previs video per Brand completes and persists to the correct Drive root after spend approval;
- no cross-Brand asset or Campaign bleed is observed;
- focused and affected regression tests pass;
- a final secret-free Markdown and JSON readiness report is delivered.

## 7. Stop conditions and escalation

The implementing agent must stop and ask the operator when:

- Google OAuth consent or account selection is required;
- choosing which Campaign remains active requires business judgment;
- changing the Previs provider/model requires approval;
- a provider check or generation may incur material cost;
- a fix would weaken an approval, Drive, logo, Campaign, or Brand-scope gate;
- existing unrelated working-tree changes overlap a required source file;
- the live deployment does not match the checked-out source.

## 8. Expected handoff from the implementing agent

Return:

1. Changed files and rationale.
2. Operational changes by Brand, excluding secrets.
3. Commands executed and exit codes.
4. Before/after readiness matrix.
5. Live endpoint evidence through `8090`.
6. Provider spend incurred, if any.
7. Generated Run IDs and Drive file IDs from approved smoke tests.
8. Remaining blockers, risks, and operator decisions.
