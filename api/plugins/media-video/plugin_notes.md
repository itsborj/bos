# media-video Plugin Notes

## 2026-05-27 - Video specialist extraction

Video generation now lives in its own plugin instead of Creative Factory.

- Stable module ID: `media.video.generate`
- Legacy alias: `creative.shortform.video`
- Provider config: `VIDEO_GEN_PROVIDER`, `VIDEO_GEN_API_URL`, `VIDEO_GEN_API_KEY`
- Storage: optional Google Drive upload when a brand Drive root is connected

The module supports a generic HTTP provider contract. If `VIDEO_GEN_API_URL` is an HTTP URL, BOS posts a JSON video brief and accepts either binary `video/mp4` bytes or JSON containing `video_data_b64`, `video_url`, or `url`. If no usable HTTP provider is configured, it falls back to local FFmpeg rendering so the workflow remains testable.
