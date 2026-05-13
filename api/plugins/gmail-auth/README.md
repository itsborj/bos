# Gmail Auth Channel Plugin

Direct-tool Klaroha channel plugin for Gmail send and receive operations.

## Install path

Copy or keep this directory at:

```text
api/plugins/gmail-auth/
```

Klaroha discovers the plugin by reading `channel.json` from this directory.

## OAuth/social connection expectation

This plugin declares:

```json
"requires_social_connection": ["gmail"]
```

Klaroha should inject the brand-level Gmail OAuth token into `brief["_channel_credentials"]` before dispatch.

The modules read the token from, in priority order:

1. `access_token`
2. `gmail_access_token`
3. `page_token`

Recommended Google OAuth scopes for this plugin:

```text
https://www.googleapis.com/auth/gmail.send
https://www.googleapis.com/auth/gmail.readonly
```

Use `gmail.modify` instead of `gmail.readonly` only if you add operations that mutate labels, read state, archive, trash, or similar mailbox state.

## Capabilities

- `marketing.channel.gmail_auth.email.send`
  - Sends an RFC 2822 email through Gmail API `users.messages.send`.
  - Brief fields: `to`, `subject`, `body`; optional `cc`, `bcc`, `reply_to`, `html_body`, `thread_id`.

- `marketing.channel.gmail_auth.email.receive`
  - Lists Gmail messages and returns metadata/snippets, optionally text bodies.
  - Brief fields: optional `query`/`q`, `label_ids`, `max_results`, `page_token`, `include_spam_trash`, `include_body`.

## Example send brief

```json
{
  "to": "customer@example.com",
  "subject": "Welcome",
  "body": "Thanks for signing up.",
  "_channel_credentials": {
    "access_token": "ya29..."
  }
}
```

## Example receive brief

```json
{
  "query": "is:unread newer_than:7d",
  "label_ids": ["INBOX"],
  "max_results": 10,
  "include_body": false,
  "_channel_credentials": {
    "access_token": "ya29..."
  }
}
```

## Static verification

```bash
find api/plugins/gmail-auth -type f | grep -v __pycache__ | sort
python -m json.tool api/plugins/gmail-auth/channel.json >/dev/null
```

Then run the Klaroha loader checks from the SDK in your host repo.
