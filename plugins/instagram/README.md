# Instagram Channel

Instagram workflow plugin built on Meta Graph API.

## Connection model

This plugin does **not** use standalone Instagram OAuth.
It reuses the existing Meta app and completes OAuth through:

- `/social/instagram/callback`
- Meta app credentials already configured for `channel.meta`

Current connect-only OAuth uses one of two paths:

1. **Preferred:** Meta Business Login configuration via optional `META_INSTAGRAM_CONFIG_ID`
2. **Fallback:** direct scope request with minimal connect scopes

Fallback scopes follow Meta's official Facebook Login requirements for connecting and discovering an Instagram professional account:

- `instagram_basic`
- `pages_show_list`

Existing connections must be reauthorized after scope changes; Meta does not add permissions to previously issued Page tokens.

The saved social connection is stored under platform `instagram` and contains:

- Instagram Business Account ID as the connection `page_id`
- Meta Page access token as the credential
- bridge metadata back to the Facebook Page in `token_meta_json`

## Current scope

Phase 1 is connection-first:

- `marketing.channel.instagram.connection.validate`

Connection validation is strictly read-only and never creates or publishes media.

Future publish / insights workflows should live in this plugin, not in `plugins/meta/`.
