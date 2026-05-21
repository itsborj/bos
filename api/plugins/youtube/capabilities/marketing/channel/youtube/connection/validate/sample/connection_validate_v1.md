# YouTube Connection Validation — Sample Output v1

## Allowed outcome — connected

**User intent:** "Validate the YouTube API pipeline for this brand."

**Artifact/block:** `youtube_connection_check`

```json
{
  "type": "youtube_connection_check",
  "platform": "youtube",
  "status": "succeeded",
  "read_only": true,
  "channel": {
    "channel_id": "UC123",
    "title": "Klaroha Official",
    "custom_url": "@klaroha",
    "privacy_status": "public",
    "view_count": "1000",
    "subscriber_count": "250",
    "video_count": "12"
  },
  "quota": {
    "endpoint": "channels.list",
    "estimated_units": 1
  },
  "changed_resources": [],
  "allowed_actions": ["view_channel", "dismiss"]
}
```

Visible summary may say:

```text
YouTube connection validated.
Channel: Klaroha Official
No YouTube resources were changed.
```

## Allowed outcome — blocked/missing setup

```json
{
  "type": "youtube_connection_check",
  "platform": "youtube",
  "status": "failed",
  "reason_code": "missing_credentials",
  "message": "YouTube OAuth access token is not connected for this brand",
  "read_only": true,
  "changed_resources": [],
  "allowed_actions": ["connect_youtube", "retry", "dismiss"]
}
```

## Forbidden outcomes

- Do not upload a video while validating the connection.
- Do not update channel metadata.
- Do not change visibility, schedule time, thumbnails, playlists, comments, or descriptions.
- Do not return fake channel IDs, fake URLs, or fake quota status.
- Do not mark validation as successful if the YouTube API did not return a channel.
- Do not use workspace-wide credentials when an active Brand is set.
