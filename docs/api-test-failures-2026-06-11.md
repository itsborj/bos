# API Test Failures — 2026-06-11

Three Schemathesis runs. Run 1: 2213 cases, 117 failures. Run 2 (after partial fixes): 1724 cases, 114 failures. Run 3: 3177 generated cases, 108 unique failures + 1 health-check error.

**Legend:** 🔵 Owned by Claude | 🟢 Owned by pi | ⬜ Unowned | ✅ Fixed

---

## Run delta — what changed between runs

| Category | Run 1 | Run 2 | Delta |
|---|---|---|---|
| Server error | 1 | 0 | ✅ resolved |
| Response violates schema | 3 | 3 | no change |
| API accepted schema-violating request | 1 | 1 | no change |
| API rejected schema-compliant request | 16 | 16 | no change |
| Undocumented Content-Type | 2 | 2 | no change |
| Undocumented HTTP status code | 36 | 33 | ✅ -3 (responses={404} additions worked) |
| Unsupported methods | 58 | 59 | ❌ nginx hardcodes TRACE block before config — unfixable without replacing nginx |
| Failed Health Check | — | 1 | new error |

## Run 3 — printed failures to triage

Run 3 selected 74/149 API operations and found 108 unique failures. Most remaining failures are still G1 TRACE noise (59). New printed actionable failures:

| Group | Failure | Owner |
|---|---|---|
| G2b-1 | `GET /social/facebook/pending-pages` returns undocumented `400 INVALID_SESSION`; because `session_id` is arbitrary string in schema, Schemathesis treats bad session IDs as schema-compliant and expects 2xx/401/403/404/409/5xx, not 400. | ✅ Fixed by pi |
| G2b-2 | OAuth callback routes (`auth/google`, `gmail`, `google-calendar`, `youtube`, `tiktok`, `google-drive`, `google-business`, `gemini`, generic `{platform}`) are documented as `302` only, but Schemathesis follows the redirect to the SPA and observes `200 text/html`. | ✅ Fixed by pi |
| G2b-3 | `GET /strategy-workflows/{workflow_id}` returns undocumented `404 Workflow not found`. | ✅ Fixed by pi |
| G2b-4 | Stateful: `GET /campaigns/{campaign_id}` returns undocumented `404 Campaign not found`. | ✅ Already fixed in code (`responses={404}`) |
| G2b-5 | Stateful: `GET /runs/{run_id}/export` returns undocumented `404 Run not found`. | ✅ Already fixed in code (`responses={404}`) |
| G2b-6 | Stateful: `GET /memory/events?event_type=<unknown>` returns undocumented `400 Invalid memory event type`; schema currently documents arbitrary string. | ✅ Fixed by pi |
| G3-stateful | Stateful UUID path/query params were rejected with 422 while some schemas exposed unconstrained strings. `runs/{run_id}` routes now expose `format: uuid`; billing, campaign, and drive picker schemas also expose UUID format in current code. | ✅ Fixed/verified by pi |
| G6a | `GET /stream` accepts unknown query parameters, violating OpenAPI `additionalProperties`. | ✅ Fixed by pi |
| G6b | One additional accepted schema-violating request remained unprinted in Run 3. A follow-up negative-data scan after pi fixes passed 140/140 negative-data checks before hitting unrelated schema-generation errors on UUID path operations. | 🟢 pi investigating |
| G3/G6 | `GET /workspace/documents?status=<garbage>` returns 422 for arbitrary string status; either document `status` enum or relax validation. Current code documents `status` as a literal enum. | ✅ Fixed/verified by pi |
| G1 | TRACE still returns nginx `405` without `Allow` for 59 operations. | 🔵 Claude / blocked |
| G8 | Health check still fails once. Follow-up negative-data scan reproduced health/schema-generation noise on UUID path operations (`agent/context/{brand_id}`, `agent/review/{run_id}`, `brands/{brand_id}`) rather than an API 500. | 🟢 pi investigating |

## Run 4 — targeted non-TRACE rerun

A targeted non-TRACE unit run surfaced more undocumented/status/content cases. pi claimed and fixed the actionable set below.

| Group | Failure | Status |
|---|---|---|
| G2c-1 | `GET /agent/context/{brand_id}` returned undocumented `400 Invalid brand_id` for non-UUID path value. | ✅ Fixed by pi: path param is now UUID; 404 documented. |
| G2c-2 | `POST /agent/execute` returned undocumented `404 Module not found`. | ✅ Fixed by pi: 404/412 documented; `brand_id` body is UUID typed. |
| G2c-3 | `PATCH /agent/review/{run_id}` returned undocumented `400` for invalid action / invalid run ID. | ✅ Fixed by pi: action is now `Literal[approve,reject,flag]`, `run_id` path is UUID, 404 documented. |
| G2c-4 | `POST /brands` returned undocumented `409 Brand already exists`; empty name was schema-valid. | ✅ Fixed by pi: 409 documented; `BrandCreate.name` requires min length 1. |
| G2c-5 | `GET /modules/{module_id}` returned undocumented `404 Module not found`. | ✅ Fixed by pi: 404 documented. |
| G2c-6 | `POST /runs` returned undocumented `404 Module not found`. | ✅ Fixed by pi: 404/412 documented. |
| G7b | `POST /chat/stream` returns `text/event-stream` but OpenAPI documented JSON. | ✅ Fixed by pi: OpenAPI override documents `200 text/event-stream`; 401 preserved. |
| G2c-7 | `POST /chat/runs/{run_id}/revise` returned undocumented `400 Invalid run ID format`. | ✅ Fixed by pi: `run_id` path is UUID; 404/412 documented. |
| G2c-8 | Provider routes returned undocumented 400/404s (`/providers/keys`, `/providers/login`, `/providers/login/complete`, `/providers/auth/{provider}`, `/providers/check`). | ✅ Fixed by pi: expected 400/404/412 responses documented. |
| G2c-9 | `POST /memory/events` returned undocumented `400` when brand scope is required. | ✅ Fixed by pi: 400/412 documented. |
| G2c-10 | `DELETE /auth/keys/{key_id}` produced a 500 for non-UUID key IDs. | ✅ Fixed by pi: `key_id` path is UUID; 404 documented. |
| G8b | `POST /chat/stream` can still time out on some generated nonsense messages because it invokes the live chat pipeline. | ✅ Fixed by pi: pre-pipeline fuzzer-garbage validation added; 422 documented for chat stream. |

**Validation:** targeted rerun on fixed Run 4 routes, excluding live `chat/stream` timeout behavior, passed 120/120 checks. Manual `chat/stream` smoke confirmed `Content-Type: text/event-stream`. Follow-up targeted `chat/stream` Schemathesis run passed 20/20 checks after fuzzer-garbage validation and 422 docs.

---

## G1 — TRACE 405 missing `Allow` header ❌ BLOCKED

**Status:** Unfixable via nginx.conf. Exhaustively tested: server-level `if` blocks, `error_page 405 = @location` with a probe that returns 200 (confirmed never triggered), `add_header Allow ... always` at server level — all bypassed.

**Root cause (confirmed):** nginx generates the 405 for TRACE at the HTTP request-parsing phase, before ANY handler chain runs — before `if` evaluation, before `error_page` hooks, before `add_header` filters. No nginx.conf directive can intercept or modify this response. FastAPI handles TRACE correctly (returns `405 + Allow: GET`) but nginx never proxies TRACE to FastAPI.

**Options to fix (none trivial):**
- Replace nginx with Caddy/Traefik/HAProxy — all properly proxy TRACE so FastAPI's Allow header reaches the client
- Custom nginx build without TRACE blocking
- Accept 59 failures — TRACE is not used by real clients; only affects RFC compliance scoring

---

## G2 — Undocumented 404 responses ✅ Partial

**Status:** 3 of 36 undocumented status codes fixed (33 remain). The `responses={404: ...}` additions to `verticals.py`, `onboarding.py`, and `handoff.py` are confirmed working.

### G2a — `GET /workspace/documents/{document_id}` 🔵

**Test:** hOybRJ — returns 404 `{"detail":"Document not found"}` but 404 is not in the documented responses.

**File:** `api/routers/documents.py` — find the `GET /workspace/documents/{document_id}` route and add `responses={404: {"description": "Document not found"}}`.

### G2b — Remaining undocumented status codes (32 in Run 3) 🟢 / ⬜

Run 3 printed the actionable non-TRACE cases. pi fixed the small OpenAPI/status-code documentation fixes for social pending pages, OAuth callback followed redirects, strategy workflow 404s, and memory event-type validation. Campaign detail 404 and run export 404 were already fixed in code with `responses={404}`. Any unprinted cases still need another detailed run.

---

## G3 — UUID query params: `"null"` string → 422 🔵

**Status:** ❌ Made worse. Changing params from `Optional[str]` to `Optional[uuid.UUID]` (G3 from Run 1) caused FastAPI to reject the literal string `"null"` at the framework level before our code runs. The fuzzer sends `brand_id=null` and `objective_id=null` as a way to "clear" filters; this is schema-compliant from the fuzzer's perspective when the param is declared as plain `string`.

**Affected routes (new in Run 2):**
- `GET /verticals/{vertical}/modules?brand_id=null` → 422 (NkqMis)
- `GET /workspace/documents?brand_id=null` → 422 (6sMxFw)
- `GET /outcomes?objective_id=null` → 422 (9LW77f) — `outcomes` router, not yet touched

**Root tension:** `Optional[uuid.UUID]` declares `format: uuid` in OpenAPI (good — stops garbage from being "schema-compliant") but FastAPI rejects `"null"` before our code can handle it (bad). `Optional[str]` allows `"null"` handling but declares no format constraint (bad — makes all garbage schema-compliant).

**Correct fix:** A custom annotated type that (1) declares `format: uuid` in OpenAPI schema, (2) converts `"null"` / `""` → `None`, (3) parses valid UUIDs normally, (4) raises 422 for garbage. Implement once in `api/validation.py`, use everywhere.

```python
# api/validation.py
from typing import Annotated, Any
from uuid import UUID
from pydantic import BeforeValidator
from fastapi import Query

def _coerce_uuid(v: Any) -> Any:
    if v in (None, "", "null", "None"):
        return None
    return v  # let UUID parser handle the rest

NullableUUID = Annotated[UUID | None, BeforeValidator(_coerce_uuid)]
```

Then each param becomes:
```python
brand_id: NullableUUID = Query(None)
```

FastAPI sees `UUID | None` → emits `format: uuid` in schema. Pydantic runs `_coerce_uuid` first → `"null"` becomes `None` before UUID parsing.

**Files to update after adding `NullableUUID` to `validation.py`:**
- `api/routers/verticals.py` — `brand_id` on both routes + `_filter_dispatchable_modules`
- `api/routers/documents.py` — `brand_id`
- `api/routers/handoff.py` — `brand_id` in `list_pending_decisions`
- `api/routers/memory.py` — `brand_id`, `objective_id`
- `api/routers/decision_briefs.py` — `brand_id`, `objective_id` in `list_decision_briefs`
- `api/routers/outcomes.py` — `objective_id` (new — found in Run 2)

---

## G4 — `parse_optional_uuid` rejects garbage bytes → 422 🔵

**Status:** ❌ Not fixed. Test T5BEa6: `GET /decision-briefs?objective_id=<garbage bytes>` still returns 422.

After the Run 1 fix, `decision_briefs.py` now uses `Optional[str]` + `parse_optional_uuid`. But `parse_optional_uuid` itself raises 422 for non-UUID strings (that's its job). The problem is the OpenAPI schema still says `string` (no format), so the fuzzer considers garbage bytes schema-compliant — then the API rejects them.

**Fix:** Resolved by G3's `NullableUUID` type. Once `decision_briefs.py` uses `NullableUUID = Annotated[UUID | None, ...]`, the OpenAPI schema declares `format: uuid` and garbage bytes are no longer schema-compliant.

---

## G5 — Response violates schema (3 failures) ✅

**Status:** Fixed by pi. Focused reruns surfaced custom `HTTPException(status_code=422, detail="...")` responses whose string `detail` did not match FastAPI's documented `HTTPValidationError.detail[]` schema.

**Fixed endpoints:**
- `POST /onboarding/ingest` — missing `brand_id` in multi-brand workspace now returns validation-error array.
- `GET /onboarding/brand-kit/latest` — missing `brand_id` in multi-brand workspace now returns validation-error array.
- `GET /calendar/pages` and `GET /calendar/bookings` — UUID query params now use `NullableUUID`, so null-ish values are absent, OpenAPI advertises `format: uuid`, and 422 details remain schema-conformant.

**Validation:**
- Focused onboarding response-schema run: 60/60 passed.
- Focused calendar response-schema run: 180/180 passed.
- Broader response-schema run excluding known slow LLM endpoints: 1226/1226 passed.

---

## G6 — API accepted schema-violating request (2 failures) 🟢 / ⬜

**G6a — `GET /stream` unknown query params ✅ Fixed by pi:** `/stream` now rejects query keys outside `include_read` with schema-conformant 422 `extra_forbidden` details.

**G6b — second accepted-invalid request 🟢 pi investigating:** Summary reports 2 failures, but only `/stream` was printed. After the `/stream` fix, a negative-data scan passed 140/140 `negative_data_rejection` checks before Schemathesis stopped on unrelated schema-generation errors for UUID path operations. Needs a full rerun after remaining schema/health-check issues are quiet.

**Validation:** targeted Schemathesis run covering `/stream`, OAuth callbacks, `facebook/pending-pages`, and `strategy-workflows/{workflow_id}` passed 63/63 checks. Targeted run covering memory events, run detail/export, billing run detail, and campaign detail passed 50/50 checks. Targeted workspace documents run passed 10/10 checks.

---

## G7 — Undocumented Content-Type (2 failures) 🟢

**Status:** Fixed by pi. OAuth callback OpenAPI response docs now include followed-redirect `200 text/html` alongside `302` for `/social/*/callback` and `/auth/google/callback`.

---

## G8 — Failed Health Check (1 error) 🟢

**Status:** pi investigating. Follow-up negative-data scan reproduced Schemathesis health/schema-generation issues on UUID path operations (`agent/context/{brand_id}`, `agent/review/{run_id}`, `brands/{brand_id}`), not an API 500. With `filter_too_much` suppressed, Schemathesis still reports schema-generation errors for those UUID-path operations. This may be test-generation noise from negative data + UUID formats, but needs a full rerun after the remaining schema mismatches are quiet.

---

## Fix order

| # | Group | Owner | Blocker for |
|---|---|---|---|
| 1 | G1 — nginx TRACE Allow header | 🔵 Claude | nothing |
| 2 | G3 — `NullableUUID` type + apply everywhere | 🔵 Claude | G4 |
| 3 | G2a — document 404 on documents/{id} | 🔵 Claude | nothing |
| 4 | G4 — decision-briefs garbage bytes | 🔵 Claude | resolved by G3 |
| 5 | G5 — schema violations | ✅ Fixed by pi | nothing |
| 6 | G6a — `/stream` accepts unknown query params | ✅ Fixed by pi | nothing |
| 7 | G7 — OAuth callback followed-redirect `200 text/html` | ✅ Fixed by pi | nothing |
| 8 | G2b-6 — memory `event_type` schema mismatch | ✅ Fixed by pi | nothing |
| 9 | G3-stateful — run UUID path schema mismatch | ✅ Fixed by pi | nothing |
| 10 | G3/G6 — workspace documents status enum mismatch | ✅ Fixed/verified by pi | nothing |
| 11 | G6b — second accepted-invalid request | 🟢 pi investigating | needs full rerun after schema/health-check noise |
| 12 | G8 — health/schema-generation noise on UUID paths | 🟢 pi investigating | needs full rerun after schema fixes |
| 13 | G2c — Run 4 targeted non-TRACE undocumented/content cases | ✅ Fixed by pi | targeted fixed-route rerun passed 120/120 checks |
| 14 | G8b — live `chat/stream` timeout under fuzzing | ✅ Fixed by pi | targeted chat-stream rerun passed 20/20 checks |
