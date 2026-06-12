# Token Billing — How It Works

Authoritative reference for what token data is recorded, where it lives, and how the billing summary is calculated. Use this to troubleshoot discrepancies.

---

## Data Sources

There are two independent token sources. Both feed into `/api/billing/summary`.

### 1. Module runs — `run_attempts` table

Every time the CMO dispatches a capability module (strategy, ad draft, image gen, etc.), a `RunAttempt` row is written with the exact token counts returned by the provider.

**Write path:**
```
POST /runs  →  executor.execute_live()  →  adapter.complete_messages()
           →  ProviderResponse.tokens_input / tokens_output
           →  RunAttempt row  (run_id, provider, model_id, mode, tokens_input, tokens_output, provider_cost)
```

**Modes counted in billing:** `platform`, `byok`, `oauth` only.  
`mock` and `tool` are excluded by the billing query filter (`RunAttempt.mode.in_([...])`) — they always record `0` anyway.

**Cost calculation** (in `executor.execute_live`):
```
provider_cost = tokens_input * model.input_cost_per_token
              + tokens_output * model.output_cost_per_token
```
Cost rates come from the `model_options` table seeded per provider.

---

### 2. CMO chat messages — `cmo_token_usage` table

Every LLM call made by the CMO conversation loop (including synthesis rounds and revise calls) writes a `CmoTokenUsage` row.

**Write path:**
```
POST /chat  →  _complete_cmo_messages()  →  adapter.complete_messages()
            →  ProviderResponse.tokens_input / tokens_output
            →  CmoTokenUsage row  (workspace_id, brand_id, provider, model_id, tokens_input, tokens_output, provider_cost)
```

`brand_id` is populated from the chat request when a brand is active; `NULL` for workspace-level (no active brand) chat sessions.

**Cost calculation** (in `_cmo_provider_cost`):
```
provider_cost = tokens_input * ModelOption.input_cost_per_token
              + tokens_output * ModelOption.output_cost_per_token
```
If the model has no row in `model_options`, `provider_cost` is recorded as `0.0` — tokens are still counted.

**CMO calls per user message (worst case):**
- 1 initial completion
- Up to 3 synthesis loop completions (`_MAX_CMO_LOOP_DEPTH = 3`)
- 1 revise completion (on `POST /chat/revise`)

All of these write individual rows.

---

## Billing Summary Aggregation

`GET /api/billing/summary` combines both sources.

**Optional filter:** `?brand_id=<uuid>` scopes the summary to a single brand — both module runs and CMO chat usage. Omit for workspace-wide totals.

```
total_tokens      = SUM(run_attempts.tokens_input + tokens_output)  [mode IN platform/byok/oauth, brand filter applied]
                  + SUM(cmo_token_usage.tokens_input + tokens_output)  [brand filter applied]

total_provider_cost = SUM(run_attempts.provider_cost)               [same mode filter]
                    + SUM(cmo_token_usage.provider_cost)

total_sell_price  = SUM(run_results.sell_price)                     [platform mode only, markup applied]
```

Sell price is only set for `platform` mode module runs. CMO chat has no sell price — it is a cost-only line.

**Per-brand billing note:** When `brand_id` is supplied, `cmo_token_usage` rows with `brand_id = NULL` (workspace-level chat sessions with no active brand) are excluded from the brand total. They remain in the workspace-wide total. This means workspace-wide total ≥ sum of all per-brand totals when any chat sessions were conducted without an active brand context.

---

## What Is NOT Tracked

| Source | Status | Reason |
|---|---|---|
| Mock module runs | Excluded | `tokens_input=0, tokens_output=0` recorded intentionally |
| Tool/channel plugin runs | Excluded | No LLM call; `tokens=0` by design |
| Council LLM calls | **Not tracked** | Council uses its own adapter calls outside chat.py — not yet wired |
| Image generation tokens | Partial | ByteDance returns `total_tokens` only (no input/output split); stored as `tokens_input=total, tokens_output=0` |
| Video generation tokens | Same as above | ByteDance video API limitation |

---

## Troubleshooting

### `total_tokens` is 0 after a real run

1. Check the run's mode:
   ```sql
   SELECT provider, model_id, mode, tokens_input, tokens_output, provider_cost
   FROM run_attempts ORDER BY created_at DESC LIMIT 10;
   ```
   If `mode = 'mock'` the run never hit a real provider. Check that a provider key is connected in Admin → AI Providers.

2. Check if the provider returned a `usage` object:
   ```sql
   SELECT tokens_input, tokens_output FROM run_attempts WHERE tokens_input = 0 AND mode != 'mock';
   ```
   If rows appear here with real modes, the provider returned an empty `usage` field — check the adapter for that provider.

### `total_tokens` is 0 after a CMO chat message

1. Check `cmo_token_usage` directly:
   ```sql
   SELECT provider, model_id, tokens_input, tokens_output, provider_cost, created_at
   FROM cmo_token_usage ORDER BY created_at DESC LIMIT 10;
   ```
   If empty: either no provider is connected (`_complete_cmo_messages` returned `None`) or the provider returned `tokens_input=0, tokens_output=0`.

2. The write only happens when `tokens_input > 0 OR tokens_output > 0`. If both are 0 from the provider, no row is written. Check the adapter's `usage` parsing.

### `provider_cost` is 0 but tokens are non-zero

The model has no row in `model_options`. Check:
```sql
SELECT provider, model_id, input_cost_per_token, output_cost_per_token
FROM model_options WHERE provider = '<your_provider>';
```
Cost will show as `0.0` until the model is seeded. Tokens are still counted accurately.

### Billing total looks higher than expected

Check for double-counting — confirm the same run isn't creating both a `run_attempts` row and a `cmo_token_usage` row. Module runs write only to `run_attempts`. Chat completions write only to `cmo_token_usage`. They are separate paths.

---

## Key Files

| File | Role |
|---|---|
| `api/executor.py` | `execute_live()` — calls provider adapter, returns `ProviderResponse` |
| `api/providers/base.py` | `ProviderResponse` dataclass — `tokens_input`, `tokens_output`, `latency_ms` |
| `api/providers/<name>.py` | Each adapter reads `usage.prompt_tokens` / `usage.completion_tokens` from provider response |
| `api/models/run.py` | `RunAttempt` — module run token storage |
| `api/models/cmo_usage.py` | `CmoTokenUsage` — CMO chat token storage (includes `brand_id` for per-brand attribution) |
| `api/routers/runs.py` | Writes `RunAttempt` after every module execution |
| `api/routers/chat.py` | `_complete_cmo_messages()` — writes `CmoTokenUsage` row after each CMO LLM call |
| `api/routers/billing.py` | `GET /billing/summary` — aggregates both tables; accepts `?brand_id=` for per-brand totals |
| `api/models/capability.py` | `ModelOption` — cost rates per provider/model |
| `api/migrations/versions/042_cmo_token_usage_brand_id.py` | Migration adding `brand_id` to `cmo_token_usage` |
