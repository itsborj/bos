# Code Context

## Files Retrieved
1. `api/routers/social.py` (lines 165-215) - OAuth start endpoint; decides relay vs local flow and returns authorize URL used by Admin buttons.
2. `api/routers/social.py` (lines 617-772) - Google Drive callback and Picker config/root support.
3. `api/routers/social.py` (lines 906-1001) - Google Business Profile callback and handoff handling.
4. `api/routers/social.py` (lines 1124-1194) - Facebook callback, page discovery, and multi-page selection handoff.
5. `api/routers/social.py` (lines 1490-1565) - token refresh and `_store_connection` behavior.
6. `api/provider_auth.py` (lines 166-198, 498-592, 728-849, 852-996, 1498-1499) - Google/Facebook/GBP OAuth handlers, scopes, redirect URI derivation, relay platform list.
7. `relay/main.py` (lines 33-45, 81-121, 146-204) - central Google auth relay platform support and metadata handoff.
8. `web/src/pages/admin/AdminBrands.tsx` (lines 28-44, 88-112, 115-232, 370-395, 438-472, 760-810) - Brands page connect buttons, callback handling, Drive Picker launch, status rendering.
9. `web/src/pages/admin/AdminBrandDetail.tsx` (lines 617-786, 831-858) - brand detail Integrations tab connect and picker flow.
10. `web/src/api/client.ts` (lines 460-515) - frontend API methods used by social connect and Drive Picker.
11. `api/models/provider.py` (lines 33-44) and `api/migrations/versions/026_meta_oauth.py` (lines 1-22) - Facebook multi-page session storage width mismatch.
12. `api/config.py` (lines 33-74) - relevant env settings for Google Picker, Meta, relay, and frontend URL.
13. `plugins/meta/channel.json` (lines 31-48) - Meta plugin credential slots (`META_APP_ID`, `META_APP_SECRET`).
14. `nginx.conf` (lines 73-82) - `/social/*` callback proxy to API.

## Key Code

### Admin buttons all call `/api/social/connect/start`
`web/src/pages/admin/AdminBrands.tsx`:
```ts
// lines 370-389
const res = await api.startSocialConnect(brandId, 'google_drive');
window.location.href = res.authorize_url;
...
const res = await api.startSocialConnect(brandId, 'google_business');
window.location.href = res.authorize_url;
```
`api/routers/social.py`:
```py
# lines 178-201
if settings.klaroha_relay_url and body.platform in GOOGLE_RELAY_PLATFORMS:
    resp = await client.get(f"{relay}/relay/{body.platform}/start", ...)
    resp.raise_for_status()
    return ConnectStartResponse(...)
```

### Relay says API can relay GBP, but relay does not support GBP
`api/provider_auth.py`:
```py
# line 1499
GOOGLE_RELAY_PLATFORMS = frozenset({"gmail", "google_calendar", "youtube", "google_drive", "gemini", "google_business"})
```
`relay/main.py`:
```py
# lines 33-45: google_business is missing
_PLATFORM_SCOPES = { "gmail": ..., "google_calendar": ..., "youtube": ..., "google_drive": ... }
_PLATFORM_BOS_CALLBACK = { "gmail": ..., "google_calendar": ..., "youtube": ..., "google_drive": ... }
# lines 88-90
if platform not in _PLATFORM_SCOPES:
    raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")
```

### Drive Picker requires local app id even when relay mode says local Google client is not needed
`api/routers/social.py`:
```py
# lines 766-772
 token, _ = await get_page_token(db, str(brand_id), "google_drive", settings)
 if not settings.google_picker_api_key: raise HTTPException(...)
 app_id = (settings.google_client_id or "").split("-", 1)[0]
 return {"access_token": token, "api_key": settings.google_picker_api_key, "app_id": app_id}
```

### Facebook config and multi-page selection
`api/provider_auth.py`:
```py
# lines 732-741
if not META_APP_ID/META_APP_SECRET:
    raise ValueError("... not configured — add it via Admin → Plugins → Meta Channel")
```
`api/routers/social.py`:
```py
# lines 1189-1193
session.verifier_encrypted = encrypt_secret(json.dumps({"brand_id": brand_id or "", "pages": pages}), settings)
await db.commit()
```
But `api/models/provider.py` line 43 still maps `verifier_encrypted` as `String(1024)` while migration `026_meta_oauth.py` widens the DB column to `Text`.

### GBP only checks first account/location and refuses to store token with no first location
`api/provider_auth.py`:
```py
# lines 922-948
accounts = r.json().get("accounts", [])
if accounts:
    account_name = accounts[0]["name"]
...
locations = r.json().get("locations", [])
if locations:
    location_name = locations[0]["name"]
else:
    gbp_error = "no_location_returned"
```
`api/routers/social.py`:
```py
# lines 979-982
if not location_name:
    return _admin_brands_redirect(frontend, google_business="error", reason=metadata.get("gbp_error") or "no_location_returned")
```

## Architecture

Admin UI (`AdminBrands` and `AdminBrandDetail`) starts all social OAuth via `api.startSocialConnect()` -> `POST /api/social/connect/start`. The API validates brand/workspace, chooses either relay mode (`KLAROHA_RELAY_URL` and platform in `GOOGLE_RELAY_PLATFORMS`) or local provider handler, stores a `ProviderLoginSession`, then redirects the browser to the provider.

Provider callbacks arrive at `/social/*/callback` (nginx proxies `/social/` directly to API). Callback handlers store a `SocialConnection` with encrypted access token and metadata. Drive folder selection is separate: after `google_drive` connection exists, the UI calls `/api/social/drive/picker-config`, opens Google Picker in-browser, then stores the selected root via `/api/social/drive/root`.

## Prioritized fixes / likely blockers

1. **P0 - Google Business button is broken in relay mode.** `api/provider_auth.py` includes `google_business` in `GOOGLE_RELAY_PLATFORMS`, so `/social/connect/start` calls `relay/main.py /relay/google_business/start`; relay rejects it because `_PLATFORM_SCOPES` and `_PLATFORM_BOS_CALLBACK` do not include `google_business`. Fix either by adding GBP scope/callback and GBP metadata collection to `relay/main.py`, or by removing `google_business` from `GOOGLE_RELAY_PLATFORMS` so it uses local `GoogleBusinessOAuthHandler`.

2. **P0 - Drive folder picker can fail after relay-based Drive connect.** Relay mode comments say local `GOOGLE_CLIENT_ID/SECRET` are not needed, but `drive_picker_config()` derives Picker `app_id` from local `settings.google_client_id`. In relay-only installs, `app_id` is empty, so Picker can fail even though Drive OAuth succeeded. Add explicit `GOOGLE_PICKER_APP_ID`/project number config, return it from relay, or make docs/config require `GOOGLE_CLIENT_ID` for picker.

3. **P1 - Facebook connect likely blocked unless Meta plugin credentials are saved.** Current code requires `META_APP_ID` and `META_APP_SECRET` from plugin vars or env. Repo `.env` has no `META_APP_ID`/`META_APP_SECRET` entries; if Admin → Plugins → Meta Channel credentials are not saved, `/social/connect/start` returns 412. Exact functions: `FacebookOAuthHandler._app_id/_app_secret()` and `start_social_connect()`.

4. **P1 - Facebook multi-page selection can break if migration 026 is not applied / ORM remains narrow.** Multi-page callback stores encrypted JSON containing all page access tokens in `ProviderLoginSession.verifier_encrypted`. Migration widens DB to `Text`, but ORM model still declares `String(1024)`. Ensure migration `026_meta_oauth` is applied everywhere and update model to `Text` to avoid fresh/create_all or schema drift failures.

5. **P1 - GBP local handler can fail for valid accounts with multiple accounts/locations.** It only inspects `accounts[0]` and `locations[0]`, then callback refuses to store any connection if that first account has no location. Iterate all accounts/locations or add a selection flow like Facebook.

6. **P2 - Brands page Drive status renders `needs_reauth` as connected.** In `AdminBrands.tsx` lines 760-769, any `gdConn` shows `Connected` and `Choose folder`; if backend marked Drive `needs_reauth`, picker-config returns no token and the user gets a picker error instead of a reconnect button. Mirror the safer `AdminBrandDetail.tsx` logic that checks `c.status === 'connected'` before showing folder picker.

## Start Here
Open `api/provider_auth.py` and `relay/main.py` first. The highest-confidence connect-button blocker is the mismatch where BOS routes `google_business` through the relay but the relay does not implement it. Then inspect `api/routers/social.py:757-772` for the Drive Picker config dependency on local `GOOGLE_CLIENT_ID`.
