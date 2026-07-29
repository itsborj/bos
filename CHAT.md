# CMO Chat Architecture

## Principle

`chat_v2.py` is **only the loop**. It owns:
- Receive user message → build state
- Call CMO (LLM) → get decision
- Execute tool calls → append results to state
- Return reply

It owns nothing else. No domain logic, no output formatting, no plugin-specific guardrails.

## External Skills (Tool Calls)

The CMO calls capabilities as tools. The tool definition (in the plugin's `SKILL.md` / `actions`) tells the CMO when and how to call it. The plugin module handles all output structure.

```
User message
    → CMO decides to call storyboard_create
    → storyboard.create module packages CMO text as draft artifact
    → User reviews in Stream
    → User approves
    → storyboard.render generates the image
```

chat_v2.py has no knowledge of storyboard, postcraft, or any domain. It just routes tool calls.

## What Does NOT Belong in chat_v2.py

- Guardrails that detect intent in CMO text replies and force a tool call
- Regex parsing of CMO output to extract domain metadata
- Domain-specific retry counters or quality gate checks
- Plugin-specific dedup logic

If the CMO doesn't call a tool when it should, the fix is the **system prompt** and the **tool description** — not a guardrail in the loop.

## Storyboard Flow

```
CMO receives: "create a 15s video for segment 2"
CMO calls: storyboard_create(title=..., storyboard_text=<CMO draft text>)
Module: packages text as storyboard_json draft artifact (no re-generation)
Stream: shows draft for operator review
Operator: approves
System: calls storyboard.render with the approved text
Result: image generated and saved to Drive
```

The storyboard_create module is a **thin packager**. It takes the CMO's text as-is and wraps it in a reviewable block. It does not re-generate, normalize, or validate the text content — the CMO already did that.

## Providers

Provider logic lives in `cmo_providers.py`. chat_v2.py calls `call_cmo()` and gets back a decision. It does not know which model was used.

## Tools

Tool definitions come from `build_tools()` in `cmo_tools.py`. chat_v2.py calls `execute_all()` to run them. It does not know what any tool does.
