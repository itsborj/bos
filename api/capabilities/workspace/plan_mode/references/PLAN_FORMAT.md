# Plan Format — Reference

This file is the canonical plan output format spec for the `cmo-strategic-planner` skill.
It is a lazy-loaded resource — loaded when `@klar plan` is active.

---

## Three-Zone Structure

Every plan output has exactly three zones in this order. No exceptions.

```
Zone 1: Header + Mission
Zone 2: Channel cards
Zone 3: Gaps list + Footer
```

No tables. No wide text. No section headers with `##`. No horizontal rules between channel cards.
The plan scrolls vertically in a mobile chat bubble.

---

## Zone 1 — Header + Mission

```
**[BRAND NAME] — [CAMPAIGN DESCRIPTION IN CAPS]**
*Planning Mode · Draft for review*

---

**🎯 MISSION**
[One sentence: verb + outcome + target segment]
```

Rules:
- Brand name from loaded `brand_profile`.
- Campaign description from the operator's `@klar plan [description]` input.
- Mission must be brand-specific. "Increase brand awareness and drive leads" is rejected by quality gate.
- Pull positioning language from brand guidelines and brand kit.

---

## Zone 2 — Channel Cards

One block per channel the brand uses. **Every channel gets a card — active or Hold**. Never silently omit a channel the brand is known to use.

### Active Channel Card

```
**[emoji] [CHANNEL NAME]**
*[role — 3–5 words]*
[effort] · [tactic angle — one line]
Target: [number if data exists] or ⚠️ TBD — [what data would set this]
```

### Hold Channel Card (single line)

```
**⏸ [CHANNEL NAME]** — Hold · [one-line reason]
```

### Channel Emoji Map

| Channel | Emoji |
|---|---|
| Facebook | 📣 |
| LinkedIn | 📘 |
| X / Twitter | 🐦 |
| Email | 📧 |
| Google Ads | 🔍 |
| Google Business Profile | 📍 |
| Instagram | 📱 |
| Paid Social (generic) | 🎯 |
| YouTube | ▶️ |
| Hold | ⏸ |

### Confidence Signal Rules

- Use a real target **only** when `marketing_reports` or `campaign_reports` contain a baseline for that channel.
- When no baseline: write `⚠️ TBD — no [channel] baseline loaded`.
- Never invent a number without labeling it `estimate`.
- As resources are loaded, ⚠️ flags automatically become real targets.

### Effort Must Be Concrete

✅ `3 posts/week`
✅ `1 sequence/week · 50 contacts`
❌ `as needed`
❌ `ongoing`

---

## Zone 3 — Gaps List + Footer

```
---

**📋 WHAT WOULD SHARPEN THIS PLAN**
☐ **[Resource]** → [what it unlocks — one line]
☐ **[Resource]** → [what it unlocks — one line]
```

Standard gap-to-unlock mappings:

| Gap | Unlock |
|---|---|
| Budget | Paid channel spend targets and Google Ads activation |
| Performance data | Replaces ⚠️ estimates with channel benchmarks |
| Competitor profiles | Sharpens positioning angle per channel |
| Industry report | Validates segment priorities and TAM |
| Tech stack | Surfaces integration and automation opportunities |
| Team / freelancers | Unlocks execution capacity per channel |

If all resources are loaded, replace gaps list with:
```
✅ All resources loaded — targets are data-backed.
```

### Footer (always last)

```
---
*Confirm with `@klar confirm` · Revise with `@klar plan [change]`*
```

---

## Separator Rules

- Blank line between channel cards.
- No horizontal rules (`---`) between channel cards.
- One `---` before the gaps list.
- One `---` in the footer.

---

## Extended Thinking Posture

Before writing any word of the plan:

1. Audit which memory slots are loaded vs. empty.
2. Identify gaps (no baseline, no competitor context, no budget).
3. Derive strategic intent from brand positioning + operator's campaign description.
4. Map channels to brand maturity, audience concentration, and resource availability.
5. Set targets from actual data; use `⚠️ TBD` when no baseline exists.
