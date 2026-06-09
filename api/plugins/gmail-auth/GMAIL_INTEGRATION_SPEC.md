# Klaroha × Gmail — Integration Requirements
**Plugin ID:** `channel.gmail`
**Version target:** 1.0.0
**Capability scope:** Send outreach emails and read inbox threads per brand Gmail account

---

## Auth model

Gmail connects per brand via OAuth2. The brand owner authorizes once through the Klaroha Admin UI. Klaroha stores the refresh token in the social connections table under `platform="gmail"`.

At execution time Klaroha injects the following into `brief["_channel_credentials"]`:

| Key | Value |
|---|---|
| `gmail_email` | Authenticated Gmail address for the brand |
| `gmail_refresh_token` | Long-lived OAuth refresh token |
| `gmail_client_id` | From `GMAIL_CLIENT_ID` env var (platform-level) |
| `gmail_client_secret` | From `GMAIL_CLIENT_SECRET` env var (platform-level) |

The plugin is responsible for exchanging the refresh token for a fresh access token before each Gmail API call. Klaroha does not manage access token lifecycle — only the refresh token is stored.

**`channel.json` auth declaration:**
```json
"requires_social_connection": ["gmail"],
"requires_platform_vars": ["GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET"]
```

---

## Required modules

### `marketing.channel.gmail.outreach.send`
Generates email copy via LLM and sends it through the brand's connected Gmail account.

- `vertical`: `marketing`
- `capability`: `marketing.copywriting`
- `platform_hint`: `gmail`
- Input brief fields used: `product_name`, `brand_name`, `audience`, `key_benefit`, `recipient_email`, `recipient_name`
- Output `content` must be a human-readable sent confirmation string
- Output `block` must be:
```json
{
  "sent": true,
  "message_id": "<gmail message id>",
  "thread_id": "<gmail thread id>",
  "to": "<recipient email>",
  "subject": "<sent subject line>"
}
```
- `self_check` must fail if `sent` is not `true` or `message_id` is missing

---

### `marketing.channel.gmail.thread.read`
Reads inbox threads for the brand's Gmail account. Used by the CMO to check replies, monitor conversations, and surface responses.

- `vertical`: `marketing`
- `capability`: `marketing.copywriting`
- `platform_hint`: `gmail`
- Input brief fields used: `max_results` (default 10), `query` (Gmail search query string, optional)
- Output `content` must be a plain-text summary of threads found
- Output `block` must be:
```json
{
  "threads": [
    {
      "thread_id": "...",
      "subject": "...",
      "from": "...",
      "snippet": "...",
      "unread": true,
      "date": "ISO8601"
    }
  ],
  "total": 0
}
```
- `self_check` must fail if `block.threads` is missing or not a list

---

## Skill requirements

Two `SKILL.md` files — one per module. Minimum required frontmatter fields:

```yaml
id: marketing.channel.gmail.outreach.send   # or .thread.read
name: gmail-outreach-send
description: <inline string, no block scalar>
scope: execution
status: active
version: 1.0.0
allowed_from_chat: true
requires_intent:
  - generation              # for send
  - diagnostic              # for thread.read
triggers: [...]
memory_slots:
  - brand_profile
related_modules:
  - <this module id>
```

---

## Compliance rules

1. Import only `from klaroha_sdk import ChannelModule` and `from module_base import _get_env` (inside `build_prompt` only)
2. All Gmail API calls go inside the plugin's own `providers/` directory — no external SDK imports at module class level
3. `self_check` never raises — catch all exceptions and append to failures list
4. `block` in the result is set via `result_data["block"]` returned from `execute_tool_result` — do not embed structured data inside `content`
5. The plugin must handle missing credentials gracefully — if `gmail_refresh_token` is absent, `self_check` returns `fail` with `["no_gmail_connection"]`, never raises

---

## execute_tool_result pattern

Both modules bypass the LLM for their Gmail API calls. Use `execute_tool_result` instead of `build_prompt` for the actual send and read operations. The LLM is still used to generate email copy for the send module — call it explicitly inside `execute_tool_result`, or split into two methods.

Klaroha detects `execute_tool_result` on the module class and routes accordingly — no provider waterfall, no capability routing. The module owns the full execution.

Signature:
```python
def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
    # attempt_data: provider, model_id, mode, status, tokens_input,
    #               tokens_output, provider_cost, latency_ms, error
    # result_data:  content, sell_price, block
    return attempt_data, result_data
```

---

## Klaroha host requirements (not plugin responsibility)

The following must exist in Klaroha before the plugin can be tested end-to-end:

- `GmailOAuthHandler` in `provider_auth.py` — handles Gmail OAuth2 flow, stores refresh token via `_store_connection()` with `platform="gmail"`, `page_id=email_address`
- `/social/gmail/callback` route or generic platform callback in `routers/social.py`
- `GMAIL_CLIENT_ID` and `GMAIL_CLIENT_SECRET` in `.env`
- Brand Gmail connected in Admin → Brands → Connect Gmail

The plugin does not implement these. It reads what Klaroha injects.
