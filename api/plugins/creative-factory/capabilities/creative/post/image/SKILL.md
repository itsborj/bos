---
id: creative.post.image
module_id: creative.post.image
name: facebook-post
description: THE default capability for "make/create a Facebook post" or "Instagram post". A post means a COMPLETE post — caption (copy) AND visual together — as one reviewable proof, stored in the brand's Drive. ALWAYS use this for any "make a post / create a post / post about X" request unless the user EXPLICITLY asks for copy/text only. Compose the post copy yourself and pass it as the `caption` param; pass an `image_prompt` describing the visual. Produces ONE post proof. Do NOT also dispatch marketing.channel.meta.posts.draft for the same request (that splits one post into two cards), and do NOT publish — publishing is a separate explicit approved action on the artifact.
scope: module
status: active
version: 1.1.0
allowed_from_chat: true
requires_intent:
  - generation
triggers:
  - make a facebook post
  - create a facebook post
  - facebook post
  - instagram post
  - make an instagram post
  - post for our facebook page
  - social media post
  - meta post
  - design a facebook post
  - creative for a facebook post
excluded_triggers:
  - publish
  - post it now
  - send to facebook
  - go live
  - schedule post
  - just the copy
  - copy only
  - write copy only
related_modules:
  - media.image.generate
  - marketing.channel.meta.posts.draft
quality_gates:
  - image_data_present
  - stored_to_drive
metadata:
  version: 1.0.0
  author: bos
  plugin_id: creative.factory
---

## When to activate

Activate when the user wants to **make a Facebook or Instagram post**. This produces the complete post — copy + visual — as ONE proof. When you dispatch, append the post copy and visual direction as params:

```
RUN: creative.post.image
caption: <the full post copy you composed, in the brand voice>
image_prompt: <a vivid description of the visual — scene, mood, no text/logos>
```

The host generates the image (third-party) before this module runs; the module bundles your caption with it and stores it in the brand's Drive. **Do not also dispatch `marketing.channel.meta.posts.draft` for the same request** — that would split one post into two cards. This is the single deliverable.

**After dispatch:** Tell the operator to review the proof in Stream and click **"Approve & Publish"** to publish it to Facebook with the image. Do NOT also dispatch `marketing.channel.meta.posts.publish` — the artifact button handles the publish handoff automatically.

Example CMO reply after dispatch:
```
Post proof created.
Review the image and caption in Stream → click Approve & Publish to go live on Facebook.
```

## When NOT to activate

- Publishing/sending/scheduling to a live platform — this only produces the post proof. Publishing is a separate explicit action after approval via the artifact button.
- Pure copy-only requests with no visual ("just write me copy") — use `marketing.channel.meta.posts.draft` instead.

## Requirements

- The active brand must have **Google Drive connected** with a **root folder selected** (Admin → Brands). Without it, the module returns a `drive_not_connected` / `no_root_folder` setup blocker.

## Output contract

Returns a `creative_post_asset` block with a publish action wired to `marketing.channel.meta.posts.publish`:

```json
{
  "type": "creative_post_asset",
  "status": "succeeded",
  "channel": "meta",
  "image_data_b64": "<base64 PNG for preview>",
  "mime_type": "image/png",
  "drive_file_mime": "image/png",
  "caption": "<post copy>",
  "message": "<post copy — same value, mapped for publish brief>",
  "drive_file_id": "<Drive file id>",
  "drive_web_view_link": "<shareable Drive link>",
  "drive_folder": "Creative Assets/Meta Posts",
  "reusable": true,
  "allowed_actions": ["publish", "regenerate", "dismiss"],
  "action_modules": {"publish": "marketing.channel.meta.posts.publish"}
}
```

The `publish` action routes through `POST /runs/{run_id}/actions/publish` — the generic action endpoint reads `drive_file_id` + `message` from the block and builds the publish brief automatically. No CMO re-dispatch needed.
