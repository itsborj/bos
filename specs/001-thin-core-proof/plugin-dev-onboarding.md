# Plugin Developer Onboarding

You are building a third-party plugin for Klaroha BOS.
This doc is the canonical authoring guide — start here, not in code.

---

## Mental model

BOS fires events. Your plugin reacts. You never touch BOS core.

```
User message → CMO reads SKILL.md manifests → decides to dispatch your plugin
→ BOS fires brief.before_dispatch → credentials injected into brief
→ BOS calls your execute(brief) → you return RunResult
→ artifact appears in Stream
```

Your plugin is one directory. BOS scans it on startup. Delete the directory → capability disappears. No config changes required.

---

## 1. Set up your environment

```bash
# Install the SDK (from the BOS repo)
pip install -e /path/to/bos/packages/klaroha_sdk

# Verify
python -c "from klaroha_sdk import ChannelModule, ArtifactBlock, RunResult; print('SDK OK')"
```

Your plugin lives in `~/bos-plugins/your-plugin-name/`. The full contract is in `~/bos-plugins/README.md`.

---

## 2. The three files

Every plugin needs exactly three things:

```
your-plugin/
├── channel.json                               ← who you are + what you need
└── capabilities/{vertical}/{domain}/{task}/
    ├── SKILL.md                               ← when the CMO invokes you
    └── module.py                              ← what you do
```

Start by copying `hello/` and editing from there.

---

## 3. Write SKILL.md first

The CMO reads SKILL.md to decide when to invoke your plugin. Get this right before writing code.

The two most important fields:

**`description`** — the CMO's primary signal. Be specific about what data you need and what you produce.

```yaml
# Too vague — CMO may not dispatch when it should
description: Analyzes Google data for the brand.

# Better — CMO knows exactly when to use this
description: Score the brand's Google Business Profile on the 8 critical ranking fields
  (primary category, additional categories, business name, address, phone, website,
  hours, verification). Returns a 0-100 completeness score with gap analysis.
  Use when the operator asks how complete their Google listing is, wants a GBP audit,
  or asks why they're not appearing in local search results.
```

**`requires_intent`** — must be one of these exact values (anything else = silently skipped):

| Value | Use when your plugin... |
|---|---|
| `generation` | Creates new content (copy, image, email draft) |
| `diagnostic` | Reads and scores external data (audits, reports) |
| `action` | Executes on an external system (posts, sends, publishes) |
| `approval` | Puts something in the operator's review queue |
| `discussion` | Responds conversationally, no artifact |
| `revision` | Edits an existing artifact |
| `onboarding` | Guides brand or workspace setup |
| `publish` | Distributes an approved artifact |

**`excluded_triggers`** — critical if your plugin shares vocabulary with other Google plugins.
If you use Google OAuth, explicitly exclude GA, Search Console, Ads, and SEO phrases —
smaller fallback models don't discriminate well between overlapping trigger sets.

Full SKILL.md reference: `~/bos-plugins/README.md` → SKILL.md section.

---

## 4. Write module.py

```python
from klaroha_sdk import ChannelModule, ArtifactBlock, RunResult


class YourTask(ChannelModule):
    id = "marketing.channel.yourplugin.task"   # must match channel.json capability_ids
    vertical = "marketing"
    capability = "marketing.execute"
    platform_hint = "yourplugin"

    async def execute(self, brief: dict) -> RunResult:
        # 1. Check credentials (if your plugin needs them)
        token = brief.get("_channel_credentials", {}).get("page_token")
        if not token:
            return RunResult(
                run_id=brief.get("run_id", ""),
                status="failed",
                artifact_blocks=[ArtifactBlock(
                    block_type="your_result_type",
                    content={"error": "Connect your account in Admin → Brands."},
                    renderer_hint="setup_blocker",
                    allowed_actions=[],
                )],
                self_check="fail",
            )

        # 2. Do your work
        result_data = {"score": 85, "details": "..."}

        # 3. Return a RunResult
        return RunResult(
            run_id=brief.get("run_id", ""),
            status="success",
            artifact_blocks=[ArtifactBlock(
                block_type="your_result_type",
                content=result_data,
                renderer_hint="approval_bundle",      # or "stream_card"
                allowed_actions=["approve", "dismiss"],
            )],
            self_check="pass",
        )
```

**What's in `brief`:**

| Key | Description |
|---|---|
| `run_id` | Pass this to every `RunResult` |
| `brand_name` | Active brand name |
| `brand_json` | Full brand settings dict |
| `_channel_credentials` | Dict of resolved credentials |
| `product_catalog` | Brand's active products |
| `audience_profiles` | Brand's target audiences |
| `message` | The user's original message |

Always `.get(key)` with a fallback — none of these are guaranteed.

---

## 5. Verify it loaded

```bash
# Restart the api container
docker compose restart api     # from ~/bos/

# Check startup logs
docker compose logs api | grep "Plugin loaded"
# Expected: Plugin loaded [external]: channel.yourplugin v0.1.0 — 1 capabilities
```

**"Plugin loaded [external]" in logs does not mean it's dispatchable.**
The plugin transport layer (channel.json) and the skill layer (SKILL.md) are checked separately.
A plugin can load but still be invisible to the CMO if SKILL.md fails validation.

Verify it's in the CMO manifest:

```bash
docker exec bos-api-1 python3 -c "
import sys; sys.path.insert(0, '/app')
import registry; registry._scan()
from capability_manifest import build_dispatchable_manifest
ids = [e.module_id for e in build_dispatchable_manifest()]
print([i for i in ids if 'yourplugin' in i])
"
```

If your module_id is missing from this list, debug your SKILL.md (see Diagnostics below).

---

## 6. Test dispatch

```bash
API_KEY=your-key
BRAND_ID=your-brand-uuid

curl -s -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"your trigger phrase\", \"history\": [], \"brand_id\": \"$BRAND_ID\"}" \
  http://localhost:8090/api/chat \
  | python3 -c "
import sys, json; d = json.load(sys.stdin)
print('runs:', [r['module_id'] for r in d.get('runs', [])])
print('reply:', d.get('reply', '')[:200])
"
```

Expected: `runs: ['your.module.id']`

Inspect the artifact:
```bash
curl -s -H "X-API-Key: $API_KEY" \
  "http://localhost:8090/api/runs?limit=1&module_id=your.module.id" \
  | python3 -m json.tool
```

---

## Diagnostics

### Plugin loads but never appears in CMO manifest

Check in this order:

**1. `requires_intent` uses an invalid value**
This is the most common silent failure. Valid: `generation | diagnostic | action | approval | discussion | revision | onboarding | publish`. Anything else → SKILL.md silently skipped.

**2. `allowed_from_chat` is missing or false**
Without `allowed_from_chat: true`, the skill is excluded from the manifest.

**3. `status` is not `active`**
Any other value skips the skill.

**4. `module_id` mismatch**
The `module_id` in SKILL.md, `id` on your class, and `capability_ids` in channel.json must all match exactly.

**Parse your SKILL.md to get the exact error:**
```bash
docker exec bos-api-1 python3 -c "
import sys; sys.path.insert(0, '/app')
from pathlib import Path
from skills.loader import _parse_frontmatter, _normalize_frontmatter, SkillManifest

path = Path('/external_plugins/your-plugin/capabilities/your/path/SKILL.md')
data, _ = _parse_frontmatter(path.read_text())
data = _normalize_frontmatter(data, path, path.parents[4])
try:
    m = SkillManifest.model_validate(data)
    print('OK:', m.module_id, m.allowed_from_chat)
except Exception as e:
    print('VALIDATION FAILED:', e)
"
```

### CMO dispatches a different plugin instead

Add `excluded_triggers` to your SKILL.md. If your plugin uses Google OAuth, explicitly exclude analytics, ads, and SEO phrases — smaller fallback LLMs don't differentiate overlapping trigger vocabulary:

```yaml
excluded_triggers:
  - google analytics
  - ga4
  - search console
  - google ads
  - paid search
  - on-page seo
  - page speed
```

### Artifact status is `partial` / nothing appears in Stream

The module ran but returned a failure result, or the execute() raised an exception.

```bash
# Check recent runs for your module
curl -s -H "X-API-Key: $API_KEY" \
  "http://localhost:8090/api/runs?limit=3&module_id=your.module.id" \
  | python3 -c "
import sys, json; d = json.load(sys.stdin)
for r in d['runs']:
    print(r['run_id'], r['status'], r.get('result', {}).get('block', {}).get('error', ''))
"
```

Common causes:
- Exception in `execute()` → check `docker compose logs api`
- Missing credential check → returns `status="failed"` before the token check
- `self_check="fail"` with `status="failed"` → `partial` run status (expected for setup_blocker path)

### `EXTERNAL_PLUGINS_PATH` not resolving

Docker does not expand `~`. Set an absolute path:
```env
# .env
EXTERNAL_PLUGINS_PATH=/home/yourusername/bos-plugins
```

Symptom: `No external plugin root found — external plugins disabled` in startup logs.

---

## Known gaps in the SDK (as of 2026-06-08)

These are not blocking but worth knowing:

- **No validate CLI**: `klaroha validate ./my-plugin` doesn't exist yet. Use the manual SKILL.md parse command above to catch enum violations before restarting BOS.
- **No local test runner**: You must restart the api container to test dispatch. A future `klaroha test` command would run `execute()` against a mock brief locally.
- **`brief` shape not version-locked**: The keys documented above are stable but not yet formally versioned. Pin to the SDK version in your `channel.json` (`sdk_version`).
- **`plugin_activations` gate not wired**: Activation state (active/inactive per brand) is in the DB but not yet enforced in the manifest. All loaded plugins are currently auto-active.

---

## Reference

- Plugin contract + diagnostics: `~/bos-plugins/README.md`
- SDK types: `packages/klaroha_sdk/klaroha_sdk/types.py`
- Hook event payloads: `specs/001-thin-core-proof/contracts/hook-events.md`
- Working example (minimal): `~/bos-plugins/hello/`
- Working example (OAuth + approval flow): `~/bos-plugins/gbp-completeness/`
