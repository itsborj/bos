#!/usr/bin/env python3
"""
Creational script for Klaroha Gmail Channel Plugin v0.1.
Run this script to generate the folder: gmail/
Move the resulting gmail/ directory into api/plugins/ when done.
"""
import os

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

# 1. channel.json
channel_json = '''{
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
'''

# 2. module.py
module_py = '''from klaroha_sdk import ChannelModule


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
'''

# 3. template.j2
template_j2 = '''{% raw %}You are an expert email copywriter. Write a professional outreach email on behalf of {{ brand_name or "the company" }}.

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
{% endraw %}'''

# 4. SKILL.md
skill_md = '''---
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
- CMO asks to "send an email" to a specific audience or lead

### Do not activate for
- Multi-step email sequences → use email-sequence skill
- Newsletter campaigns → not implemented in this plugin version
- Internal operational emails

### Output contract
Every output must contain exactly:
1. `Subject:` line on the first line (max 60 chars)
2. `---` separator
3. Body (3–5 paragraphs, max 400 words)
4. Clear call-to-action
5. Sign-off

### Quality gates
- `subject_line_present` — output must start with `Subject:`
- `content_within_char_limit` — total content under 4000 chars
- `no_banned_phrases` — "guaranteed", "100% free", "act now" are blocked
'''

# Build tree
base = "gmail"
write_file(os.path.join(base, "channel.json"), channel_json)
write_file(os.path.join(base, "capabilities/marketing/channel/gmail/outreach/draft/module.py"), module_py)
write_file(os.path.join(base, "capabilities/marketing/channel/gmail/outreach/draft/template.j2"), template_j2)
write_file(os.path.join(base, "capabilities/marketing/channel/gmail/outreach/draft/SKILL.md"), skill_md)

print("Plugin folder 'gmail' created successfully.")
print("Move it to api/plugins/gmail and restart Klaroha.")
