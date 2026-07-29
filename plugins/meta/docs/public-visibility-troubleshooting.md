# Facebook Page Post Public Visibility Troubleshooting

Use this when a Facebook Page post succeeds through Graph API but is not visible to logged-out/incognito users.

## Symptom

A publish call returns success and Graph shows the post as public, for example:

```json
{
  "is_published": true,
  "is_hidden": false,
  "privacy": { "value": "EVERYONE", "description": "Public" }
}
```

But a logged-out/incognito viewer cannot see the post on the Page or post permalink.

This can happen for **text-only `/feed` posts too**. If a text-only control post is hidden from logged-out users, the issue is not `/photos`, image upload, album routing, or `attached_media`.

## Known live-debug finding

On Klarohahq, a text-only control post created through `POST /{page_id}/feed` returned:

- `is_published: true`
- `is_hidden: false`
- `privacy.value: EVERYONE`
- valid `/posts/...` permalink

The logged-out user still could not see it. That points to Meta app/page visibility restrictions rather than publish endpoint shape.

## Most likely cause: app is not live/approved for public users

Meta App Modes documentation states that apps in Development mode can create test data/posts visible to app role users, but that data is not visible to non-role users until the app is switched to Live mode.

Check the Meta Developer Dashboard for the app that minted the Page token:

1. App mode is **Live**, not Development.
2. Required permissions have approved/active access:
   - `pages_manage_posts`
   - `pages_read_engagement`
   - `pages_show_list`
3. Business verification is complete if Meta requires it.
4. No app age/country restrictions block public viewers.
5. The Page itself has no age/country restrictions or unpublished status.

## Diagnostic steps

### 1. Confirm this is not an image endpoint issue

Create a text-only Page feed post:

```bash
POST https://graph.facebook.com/v21.0/{page_id}/feed
message="BOS text-only visibility control"
access_token={page_token}
```

Then read it back:

```bash
GET https://graph.facebook.com/v21.0/{post_id}?fields=id,message,permalink_url,is_hidden,is_published,privacy
```

If Graph returns public/published but incognito cannot see it, stop debugging image upload paths and check Meta app/page visibility.

### 2. Inspect the Page token

```bash
GET https://graph.facebook.com/v21.0/debug_token
  ?input_token={page_token}
  &access_token={page_token}
```

Look for:

- `type: PAGE`
- `is_valid: true`
- `app_id` and `application`
- scopes including `pages_manage_posts` and `pages_read_engagement`

Use the `app_id` to verify app mode/review in Meta Developer Dashboard.

### 3. Confirm Page status

```bash
GET https://graph.facebook.com/v21.0/{page_id}?fields=id,name,username,is_published,verification_status,fan_count,followers_count
```

Expected baseline:

- `is_published: true`

Note: `is_published: true` on the Page and `privacy: EVERYONE` on the post are necessary but not sufficient if the app is still restricted to role users.

## Endpoint guidance

For normal public image URL posts, prefer a Page feed post:

```bash
POST /{page_id}/feed
message=...
link=https://.../image.jpg
```

This creates a `/posts/...` object with an image/link preview and avoids creating a Photo object.

Avoid direct image publishing with:

```bash
POST /{page_id}/photos
published=true
```

That creates a Photo object and can surface primarily in the Page Photos album.

Private Drive/binary images are different: Meta does not accept multipart binary image bytes as `/feed source`; a private binary image must either be exposed through a temporary public URL first or use the unpublished `/photos` + `/feed attached_media` fallback.

## What success looks like

A successful public Page post should be visible to logged-out/incognito users and have:

- A `/posts/...` permalink, not `photo/?fbid=...&set=a...`
- Present in `/{page_id}/posts`
- `is_published: true`
- `is_hidden: false`
- `privacy.value: EVERYONE`
- Visible on the Page timeline/feed to a non-role public viewer

If all Graph fields look correct but incognito still cannot see it, escalate to Meta app mode/app review/Page restriction checks.
