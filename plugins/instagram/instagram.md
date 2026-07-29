# Instagram Plugin — Project Brief

## Objective

Create a standalone Instagram workflow plugin while reusing the existing Meta OAuth pipeline.

## Phase 1: connect and validate

Done when a brand can:

1. click **Instagram** in Brand Integrations
2. complete Meta OAuth
3. select a Meta Page that has a linked Instagram Business Account
4. save a brand-scoped `instagram` social connection
5. run `marketing.channel.instagram.connection.validate`

## Rules

- Do not build a separate Instagram auth stack.
- Reuse Meta app credentials from `channel.meta`.
- Store the Instagram connection under platform `instagram`.
- Treat missing linked IG Business Account as a setup blocker, not a silent success.

## Connection scope

The fallback OAuth flow requests only Meta's documented connection scopes:

- `instagram_basic`
- `pages_show_list`

Connection validation is read-only and must never create a media container or publish content.

## Connection investigation handoff

This section consolidates the live Meta/Instagram investigation so work can resume without reconstructing it from chat history.

### Objective for the current phase

Connect Klaroha's Instagram Professional account to BOS and prove that BOS can read its identity through Meta Graph API without publishing or otherwise mutating Instagram.

Success evidence:

1. Meta OAuth completes through Facebook Login for Business.
2. The linked Facebook Page is selected.
3. BOS stores a brand-scoped `SocialConnection` with platform `instagram`.
4. The connection stores the Instagram professional account ID with the Facebook Page access token.
5. `marketing.channel.instagram.connection.validate` reads the account profile successfully.
6. The validation result remains read-only with `changed_resources: []`.

### Confirmed identifiers

| Resource | Value | Status |
|---|---|---|
| Meta app | `2498513223943482` (`KlarohaHQ`) | Matches the app configured in BOS |
| Meta Business Portfolio | `2821262764906624` (`Klaroha`) | Confirmed through Graph API |
| Facebook Page | `1172728675913055` (`Klarohahq`) | Existing BOS Facebook connection is valid |
| Instagram account | `17841416776810076` (`@klarohahq`) | Professional account owned by Klaroha |
| Facebook Login for Business configuration | `1274299122428644` (`Instagram Onboarding`) | Saved in the local `channel.meta` plugin variables as `META_INSTAGRAM_CONFIG_ID` |
| BOS brand | `7b4c97aa-ee5c-42cd-8932-5779ed0f4590` (`Klaroha`) | Target brand for the connection |

The Business Portfolio UI showed two people assigned to the Instagram account with full access, including Junard Catingub and the Klaroha identity. This proves account ownership and people access, but it does **not** by itself prove that the Instagram account is linked to the Facebook Page.

### Known-working baseline

The existing Facebook integration is the baseline to reuse:

```text
Meta OAuth
→ exchange authorization code
→ long-lived Facebook user token
→ GET /me/accounts
→ Facebook Page access token
→ store encrypted brand-scoped connection
```

Both existing Facebook Page tokens were valid and issued by Meta app `2498513223943482`. The Klarohahq Page can be queried successfully. Instagram should extend the same flow:

```text
GET /me/accounts?fields=id,name,access_token,instagram_business_account
→ select Page 1172728675913055
→ resolve Instagram account 17841416776810076
→ store platform=instagram with the Page token
→ validate the Instagram profile
```

Do not build a second token store or a separate BOS authentication stack.

### Findings and current blocker

- No brand-scoped `instagram` row existed in `social_connections` at the last check.
- `channel.instagram` loaded successfully but was inactive for the Klaroha brand at the last check.
- Existing Facebook Page tokens had `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, and `business_management`, but did not have Instagram permissions.
- `GET /1172728675913055?fields=instagram_business_account` returned `instagram_business_account: null` using the existing Facebook token.
- Meta Business Settings confirms that `@klarohahq` is owned by Klaroha, but the **Connected assets** view still needs to prove that Facebook Page `1172728675913055` is attached to Instagram account `17841416776810076`.
- People assignments and full access to the Instagram account are not substitutes for the Page-to-Instagram asset link required by Facebook Login for Business.

Expected asset relationship:

```text
Facebook Page 1172728675913055 (Klarohahq)
        ↓ linked/connected asset
Instagram 17841416776810076 (@klarohahq)
```

### OAuth result and resolution

A direct OAuth request containing `scope=instagram_basic` failed with Meta's developer error `Invalid Scopes: instagram_basic`. The app is using Facebook Login for Business, where Meta recommends passing a configuration ID instead of ad-hoc scopes.

The configuration ID `1274299122428644` was added to the local encrypted `channel.meta` plugin variables. BOS then generated an authorization URL containing:

```text
client_id=2498513223943482
config_id=1274299122428644
response_type=code
redirect_uri=http://localhost:8090/social/instagram/callback
```

The URL reached Meta's login dialog without an invalid-scope or invalid-configuration error. Any previous OAuth session/state should be considered stale; generate a fresh session when work resumes.

`InstagramOAuthHandler` already supports this behavior: when `META_INSTAGRAM_CONFIG_ID` is present it sends `config_id` and omits `scope`. The classic fallback remains limited to connection scopes (`instagram_basic`, `pages_show_list`) and is not the active path for this Meta app.

### Security note

A Facebook access token was pasted into chat during troubleshooting. Treat it as compromised and revoke it before resuming. Never copy that token into documentation, source control, logs, or future tests. Generate a fresh token through Meta OAuth and store it only through BOS's encrypted social connection flow.

### Resume checklist

1. Revoke the access token exposed during troubleshooting.
2. In **Meta Business Settings → Accounts → Instagram accounts → @klarohahq → Connected assets**, verify that Facebook Page `1172728675913055` is listed. If absent, add the Page and grant full control.
3. Confirm the same relationship under **Klarohahq Page Settings → Linked accounts → Instagram**.
4. Generate a fresh BOS Instagram OAuth session. It must use configuration ID `1274299122428644` and must not send an ad-hoc `scope` parameter.
5. Complete the human Meta login and asset-selection dialog.
6. Verify that `/me/accounts` returns Page `1172728675913055` with `instagram_business_account.id = 17841416776810076`.
7. Verify that BOS stores an `instagram` social connection for brand `7b4c97aa-ee5c-42cd-8932-5779ed0f4590`.
8. Activate `channel.instagram` for the Klaroha brand if it remains inactive.
9. Run `marketing.channel.instagram.connection.validate` and confirm the returned username is `klarohahq`, the result is read-only, and `changed_resources` is empty.
10. Do not begin publishing work until this connection phase passes end to end.

### Connection-focused verification already added

`plugins/instagram/tests/test_instagram_plugin.py` covers OAuth configuration behavior, plugin registration, missing credentials, and successful read-only profile validation. The focused suite passed `5` tests in the local API container.

### Official Meta references

- [Instagram Platform Overview](https://developers.facebook.com/documentation/instagram-platform/overview)
- [Instagram API with Facebook Login — Get Started](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-facebook-login/get-started)
- [Facebook Login for Business — Invoke a login dialog](https://developers.facebook.com/documentation/facebook-login/facebook-login-for-business#invoke-a--login-dialog)
- [Connect or disconnect an Instagram professional account and a Facebook Page](https://www.facebook.com/business/help/898752960195806)

## Next phases

- Instagram post draft
- Instagram publish
- Instagram account/profile read
- Instagram comment workflows
- Instagram performance / insights
