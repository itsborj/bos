# Sample — Facebook Page Auth Management

**Context:** Admin → Brands → a brand card with no Facebook Page connected.

## Empty state

```text
📘 Facebook Page                         Connect
```

## Missing platform app config

When the operator clicks **Connect** and `FACEBOOK_APP_ID` is missing:

```text
⚠️ Could not start Facebook connect — FACEBOOK_APP_ID is not configured
```

API shape:

```json
{
  "detail": {
    "error": {
      "code": "PROVIDER_CONFIG_MISSING",
      "message": "FACEBOOK_APP_ID is not configured",
      "details": { "platform": "facebook" }
    }
  }
}
```

## Successful connect

Clicking **Connect** redirects the current browser window to Meta OAuth. If `FACEBOOK_LOGIN_CONFIG_ID` is set, Klaroha includes it as Meta's Login for Business `config_id`; otherwise it requests the Page scopes directly for classic/dev login. After approval, the callback redirects back to:

```text
/admin/brands?facebook=connected&brand_id=<brand_id>&page=<page_name>
```

The Admin Brands page shows:

```text
✅ Facebook Page "Klaroha Demo" connected

📘 Klaroha Demo             Connected     Disconnect
@klaroha.demo
```

## Multi-page account

If the Meta user manages multiple Pages, callback redirects to:

```text
/admin/brands?facebook=select_page&session=<session_id>&brand_id=<brand_id>
```

The page picker modal shows:

```text
Choose a Facebook Page
Your account manages multiple pages. Select one to connect.

📣 Klaroha Demo        @klaroha.demo
📣 Cebu Growth Lab     @cebugrowthlab

Cancel
```

Selecting a page stores the encrypted Page token and updates the brand card.

## Disconnect

Clicking **Disconnect** removes the stored social connection and returns the row to:

```text
📘 Facebook Page                         Connect
```
