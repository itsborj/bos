# Klaroha Channel Plugin — Gmail v0.1 Build Instructions
**For:** Third-party AI agentic developer
**Purpose:** MVP pipeline test — verify plugin architecture compatibility
**Scope:** Email draft generation only. No sending. No OAuth. No frontend.

---

## What you are building

A minimal channel plugin that generates an outreach email subject + body via the Klaroha LLM pipeline. The CMO says "write an outreach email for [product]" — a structured draft comes back and is stored as a Run record.

This is a compatibility test, not a feature build. If all six verification steps pass, the plugin is architecturally compatible with Klaroha.

---

## How Klaroha discovers plugins

Klaroha scans `api/plugins/` at startup. Every immediate subdirectory is treated as one plugin. The scanner looks for `channel.json` at the root of that subdirectory — not nested deeper.

```
api/plugins/
└── gmail/               ← plugin root
    ├── channel.json     ← must be HERE, at this exact level
    └── capabilities/
```

If `channel.json` is one level deeper (e.g. `api/plugins/gmail/klaroha-channel-gmail/channel.json`), the plugin is silently ignored.

---

## Prerequisites

- Access to the Klaroha `api/plugins/` directory
- One line added to Klaroha `.env`: `GMAIL_USER=your-sender@gmail.com`
- No Gmail API required for v0.1

---

## Recommended build method: create_plugin.py

Create a file named `create_plugin.py` in a temporary working directory (NOT inside `api/plugins/`). Run it. It produces a `gmail/` directory. Move that directory into `api/plugins/`.

```python
#!/usr/bin/env python3
"""
Klaroha Gmail Channel Plugin v0.1 — build script.
Run from any directory OUTSIDE api/plugins/.
Output: creates ./gmail/ directory.
Install: move the resulting gmail/ into api/plugins/.
"""
import os

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

BASE = "gmail"

# ── channel.json ──────────────────────────────────────────────────────────────
write(f"{BASE}/channel.json", """{
  "plugin_id": "channel.gmail",
  "name": "Gmail Channel",
  "version": "0.1.0",
  "klaroha_min_version": "3.5",
  "capabilities_root": "capabilities/",
  "requires_social_connection": [],
  "requires_platform_vars": ["GMAIL_USER"],
  "capability_ids": [
    "marketing.channel.gmail.outreach.draft"
  ]
}
""")

# ── module.py ─────────────────────────────────────────────────────────────────
write(f"{BASE}/capabilities/marketing/channel/gmail/outreach/draft/module.py",
"""from klaroha_sdk import ChannelModule


class GmailOutreachDraftModule(ChannelModule):
    id = "marketing.channel.gmail.outreach.draft"
    name = "Gmail Outreach Draft"
    vertical = "marketing"
    capability = "marketing.copywriting"
    platform_hint = "gmail"
    policy_default = "balanced"
    template = "marketing/channel/gmail/outreach/draft/template.j2"

    max_chars = 4000
    must_mention = ["product_name"]
    banned_phrases = ["guaranteed", "100% free", "act now"]

    def build_prompt(self, brief: dict) -> str:
        creds = brief.get("_channel_credentials", {})
        context = dict(brief)
        context["sender_email"] = creds.get("gmail_user", "")
        context["copywriting_guidance"] = self._copywriting_guidance()
        context["copywriting_skill_ids"] = list(self.copywriting_skills)
        from module_base import _get_env
        return _get_env().get_template(self.template).render(**context)

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        if len(content) > self.max_chars:
            failures.append(f"exceeds_max_chars:{len(content)}>{self.max_chars}")
        for field in self.must_mention:
            val = str(brief.get(field, field))
            if val and val.lower() not in content.lower():
                failures.append(f"must_mention_missing:{val}")
        for phrase in self.banned_phrases:
            if phrase.lower() in content.lower():
                failures.append(f"banned_phrase_found:{phrase}")
        if "Subject:" not in content:
            failures.append("missing_subject_line")
        return ("fail" if failures else "pass"), failures
""")

# ── template.j2 ───────────────────────────────────────────────────────────────
# WARNING: do NOT wrap this string in {% raw %}...{% endraw %}.
# The file on disk must contain raw Jinja2 syntax. {% raw %} prevents rendering.
write(f"{BASE}/capabilities/marketing/channel/gmail/outreach/draft/template.j2",
"""You are an expert email copywriter. Write a professional outreach email on behalf of {{ brand_name or "the company" }}.

BRAND CONTEXT
=============
Voice: {{ brand_voice or "professional and clear" }}
Tone: {{ brand_tone or "helpful and direct" }}
Product: {{ product_name or "our product" }}
Key benefit: {{ key_benefit or "" }}
Target audience: {{ audience or "potential customers" }}

{% if sender_email %}
SENDER
======
From: {{ sender_email }}
{% endif %}

TASK
====
Write a cold outreach email to introduce {{ product_name or "our product" }} to {{ audience or "potential customers" }}.

OUTPUT FORMAT — follow exactly:
Subject: [one compelling subject line, max 60 characters]
---
[Email body — 3 to 5 short paragraphs]
[End with a single clear call to action]
[Sign off with the sender name or brand name]

CONSTRAINTS
===========
- Subject line must be under 60 characters
- Body must be under 400 words
- Do not use the words: guaranteed, 100% free, act now
- Match the brand voice and tone exactly
- Do not add commentary, notes, or explanations outside the email format
""")

# ── SKILL.md ──────────────────────────────────────────────────────────────────
write(f"{BASE}/capabilities/marketing/channel/gmail/outreach/draft/SKILL.md",
"""---
id: marketing.channel.gmail.outreach.draft
name: gmail-outreach-draft
description: Use when the CMO asks to write, draft, generate, or create an outreach email, cold email, or introduction email via Gmail. Activates on: write an email, draft an outreach, gmail outreach, send an email to, cold email for. For email sequences (multi-step drip), use the email-sequence skill instead. For internal client onboarding emails, defer to the workspace CMO context skill.
scope: execution
status: active
version: 0.1.0
allowed_from_chat: true
requires_intent:
  - generation
triggers:
  - gmail
  - write an email
  - draft an email
  - outreach email
  - cold email
  - email to
excluded_triggers:
  - email sequence
  - drip campaign
  - newsletter
memory_slots:
  - brand_profile
  - campaign_brand_kit
related_modules:
  - marketing.channel.gmail.outreach.draft
quality_gates:
  - subject_line_present
  - content_within_char_limit
  - no_banned_phrases
metadata:
  version: 0.1.0
  author: third-party
  plugin_id: channel.gmail
---

## Gmail Outreach Draft

Generates a single cold outreach email (subject + body) on behalf of a brand.

### When to activate
- CMO asks to write or draft an outreach email, introduction email, or cold email
- CMO mentions "gmail" as the channel
- CMO asks to send an email to a specific audience or lead

### Do not activate for
- Multi-step email sequences: use email-sequence skill
- Newsletter campaigns: not implemented in this plugin version
- Internal operational emails

### Output contract
Every output must contain exactly:
1. Subject: line on the first line (max 60 chars)
2. --- separator
3. Body (3-5 paragraphs, max 400 words)
4. Clear call-to-action
5. Sign-off

### Quality gates
- subject_line_present: output must start with Subject:
- content_within_char_limit: total content under 4000 chars
- no_banned_phrases: guaranteed, 100% free, act now are blocked
""")

print("Plugin created at ./gmail/")
print("Next: move gmail/ into api/plugins/ and restart Klaroha.")
print()
print("Verify structure:")
for root, dirs, files in os.walk(BASE):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    level = root.replace(BASE, "").count(os.sep)
    print("  " + "  " * level + os.path.basename(root) + "/")
    for f in files:
        print("  " + "  " * (level + 1) + f)
```

### Known errors to avoid in this script

**Do not add `{% raw %}...{% endraw %}` around the template string.**
This is a common AI code-generation mistake. In Python, `{% raw %}` is not needed to embed Jinja2 syntax in a string — Python strings and Jinja2 templates are separate. Adding `{% raw %}` writes those tags literally into the `.j2` file, which tells Jinja2 to treat its contents as plain text, disabling all variable substitution. The rendered prompt will contain `{{ brand_name or "the company" }}` literally instead of the actual value.

**Do not run this script from inside `api/plugins/`.**
The script creates `./gmail/` relative to the current directory. If run from inside `api/plugins/`, it creates `api/plugins/gmail/` correctly. If run from inside `api/plugins/gmail/`, it creates `api/plugins/gmail/gmail/` — wrong nesting. Run it from a scratch directory, then move the output.

---

## Install

```bash
# From a scratch directory — NOT from inside api/plugins/
python create_plugin.py

# Move output into Klaroha
mv gmail/ /path/to/klaroha/api/plugins/gmail

# Add to Klaroha .env
echo "GMAIL_USER=your-sender@gmail.com" >> /path/to/klaroha/.env

# Restart
docker compose restart api
```

---

## Pre-flight structure check — run before verification

```bash
find api/plugins/gmail -type f | grep -v __pycache__ | sort
```

Expected output — exactly these four files:
```
api/plugins/gmail/channel.json
api/plugins/gmail/capabilities/marketing/channel/gmail/outreach/draft/SKILL.md
api/plugins/gmail/capabilities/marketing/channel/gmail/outreach/draft/module.py
api/plugins/gmail/capabilities/marketing/channel/gmail/outreach/draft/template.j2
```

If the output shows `gmail/gmail/...` or `channel/channel/...` — stop. Fix the structure before proceeding.

---

## Verification — run all six in order, stop on first failure

### Step 1: Plugin discovered
```bash
docker compose exec api python -c "
from plugin_loader import scan_plugins
plugins = scan_plugins()
print([p.manifest.plugin_id for p in plugins])
# Expected: ['channel.gmail']
"
```

### Step 2: Module registered
```bash
docker compose exec api python -c "
from plugin_loader import scan_plugins
scan_plugins()
from registry import get_module
cls = get_module('marketing.channel.gmail.outreach.draft')
assert cls is not None, 'FAIL: module not found'
print('OK:', cls)
"
```

### Step 3: Credential injection
```bash
docker compose exec api python -c "
import asyncio, os
os.environ['GMAIL_USER'] = 'test@example.com'
from plugin_loader import scan_plugins, inject_channel_credentials
scan_plugins()
async def test():
    result = await inject_channel_credentials(
        'marketing.channel.gmail.outreach.draft',
        {'product_name': 'TestProduct'}, None, None, None
    )
    creds = result.get('_channel_credentials', {})
    assert creds.get('gmail_user') == 'test@example.com', f'FAIL: {creds}'
    print('OK:', creds)
asyncio.run(test())
"
```

### Step 4: Template renders
```bash
docker compose exec api python -c "
from plugin_loader import scan_plugins
scan_plugins()
from registry import get_module
module = get_module('marketing.channel.gmail.outreach.draft')()
brief = {
    'brand_name': 'TestBrand',
    'product_name': 'TestProduct',
    'audience': 'startup founders',
    '_channel_credentials': {'gmail_user': 'test@test.com'}
}
prompt = module.build_prompt(brief)
assert 'TestProduct' in prompt, 'FAIL: product_name not in prompt'
assert '{{' not in prompt, 'FAIL: unrendered Jinja variables — check for {% raw %} in template.j2'
print('OK — first 200 chars:')
print(prompt[:200])
"
```

### Step 5: self_check
```bash
docker compose exec api python -c "
from plugin_loader import scan_plugins
scan_plugins()
from registry import get_module
module = get_module('marketing.channel.gmail.outreach.draft')()

good = 'Subject: Try TestProduct Today\n---\nHello startup founders, TestProduct saves hours.\n\nLearn more.'
v, f = module.self_check(good, {'product_name': 'TestProduct'})
assert v == 'pass', f'FAIL: {f}'
print('PASS test: OK')

bad = 'Hello there, no subject line here.'
v, f = module.self_check(bad, {'product_name': 'TestProduct'})
assert v == 'fail', 'FAIL: expected fail verdict'
assert 'missing_subject_line' in f, f'FAIL: expected missing_subject_line in {f}'
print('FAIL test: OK')
"
```

### Step 6: End-to-end via API (requires LLM provider connected in Klaroha)
```bash
curl -s -X POST http://localhost:8000/api/runs \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "module_id": "marketing.channel.gmail.outreach.draft",
    "policy": "balanced",
    "payload": {
      "brief": {
        "product_name": "TestProduct",
        "brand_name": "TestBrand",
        "audience": "startup founders",
        "key_benefit": "saves 3 hours per day"
      }
    }
  }' | python -m json.tool
# Expected: run_id present, status "success" or "partial", result.content starts with "Subject:"
```

---

## Pass criteria

| Step | Check | Pass condition |
|---|---|---|
| 1 | Plugin discovered | `channel.gmail` in list |
| 2 | Module registered | `GmailOutreachDraftModule` class returned |
| 3 | Credential injection | `gmail_user` key in `_channel_credentials` |
| 4 | Template renders | `TestProduct` present, no `{{` in output |
| 5 | self_check | pass/fail verdicts correct |
| 6 | End-to-end | `run_id` present, content starts with `Subject:` |

Steps 1–5 can be verified without a live LLM provider. Step 6 requires one.

---

## Scope boundary — do not build in v0.1

- Gmail API sending
- OAuth or SMTP connection
- A second module
- Any frontend component
- Any database migration
- Any file outside `api/plugins/gmail/`
