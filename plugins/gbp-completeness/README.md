# GBP Profile Completeness Plugin

Status: **parked until Google approves GBP API quota**.

## What success looks like

The plugin is not considered working until a real Klaroha run returns:

```json
{
  "type": "gbp_completeness_result",
  "status": "pending_review",
  "self_check": "pass",
  "score": 75,
  "rating": "Good",
  "raw_score": 12,
  "max_score": 16,
  "fields": [
    { "name": "Primary category", "status": "present", "points": 1 },
    { "name": "Business hours", "status": "optimized", "points": 2 }
  ],
  "data_source": "Google Business Profile API v1"
}
```

Anything with `status: failed`, `setup_blocker`, missing score fields, or a quota/API error is **not success**.

## Current Klaroha state — 2026-06-08

BOS can complete OAuth, but GBP API reads are blocked by Google Cloud quota:

- Brand: Klaroha
- OAuth account: `jvcatingub@gmail.com`
- OAuth scope present: `https://www.googleapis.com/auth/business.manage`
- BOS connection status: `needs_setup`
- Google Cloud project: `1029575754786`
- Blocker: GBP API quotas are `0`

Observed Google response:

```text
429 RESOURCE_EXHAUSTED
quota_limit_value: 0
service: mybusinessaccountmanagement.googleapis.com
```

Google Cloud console also shows quota `0` for:

- `mybusinessaccountmanagement.googleapis.com` — Requests per minute
- `mybusinessbusinessinformation.googleapis.com` — Requests per minute

Google's docs note that quota `0` after enabling the API requires requesting GBP API access.

## Required external action

Request Google Business Profile API access/quota:

https://developers.google.com/my-business/content/prereqs#request-access

After approval, retry validation. Do not mark this plugin working until the account and location endpoints return `200` and the CMO produces a scored `gbp_completeness_result`.

## Validation commands

From `/home/ubu/bos`:

```bash
docker compose exec -T api python - <<'PY'
import asyncio, httpx, json
from db import get_session_factory
from config import get_settings
from routers.social import get_page_token

BRAND='c1cb6603-e8d4-4e63-8995-640453d5b50b'

async def main():
    settings=get_settings()
    async with get_session_factory()() as db:
        token, page_id = await get_page_token(db, BRAND, 'google_business', settings)
        print('token_present', bool(token), 'page_id', page_id)
        if not token:
            return
        async with httpx.AsyncClient(timeout=30) as client:
            accounts = await client.get(
                'https://mybusinessaccountmanagement.googleapis.com/v1/accounts',
                headers={'Authorization': f'Bearer {token}'},
            )
            print('accounts_status', accounts.status_code)
            print(json.dumps(accounts.json(), indent=2)[:3000])
PY
```

Expected before success: `429` with quota `0`.

Expected after Google approval: `200` with an `accounts[]` list, followed by a successful locations read from `mybusinessbusinessinformation.googleapis.com`.
