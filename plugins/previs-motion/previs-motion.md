# Previs Motion — Project Brief and Bug Tracker

## Project brief

Previs Motion is the live BOS video-generation plugin for converting approved Storyboard output into reviewable motion previs / animatic video artifacts through Seedance 2.0 via BytePlus ModelArk.

Operational intent:

- Consume approved Storyboard JSON plus approved image/video references.
- Generate final-cut candidate video artifacts for human review in Stream.
- Store generated video files durably in the selected Brand's Google Drive before exposing them as Stream artifacts.
- Fail loudly with an operator-facing setup/error artifact when required Drive storage or credentials are unavailable.

## Bug tracker

| Status | Issue | Notes |
|---|---|---|
| Done | Enforce Drive-first artifact persistence for generated videos | Video Stream playback must rely on Brand Google Drive as durable identity; `/tmp` is only an optional playback cache after Drive upload succeeds. |
| Done | Remove silent Drive-upload fallbacks | If Drive credentials/root are missing or upload fails, the plugin must fail and inform the operator rather than returning a successful local-only video artifact. |
| Done | Add required Drive/logo preflight before video generation | Previs now fails before generation if Brand Google Drive credentials, validated root folder, or official logo file ID are missing. |
| Open | Reduce image-generation bottleneck before video render | See bottleneck assessment below. |

---

# Previs Motion Pipeline — Bottleneck Assessment

## Pipeline Stages (End-to-End)

```
User types revision
  → CMO LLM chat completion (~30s–5min)
  → storyboard.create (text spec normalization, ~0s)
  → storyboard.render (OpenAI gpt-image-2, 80s–25000s)
  → storyboard.motion.render (Seedance i2v, 120s–400s)
  → Video artifact ready
```

## Stage 1: CMO Chat (Revision)

**What happens:**
- `chat_revise_run` sends revision feedback + history to CMO LLM
- For text storyboard revisions: LLM returns full revised markdown
- For image revisions: LLM returns short 1–2 line reply

**Bottleneck:** LLM inference time. Provider-dependent (OpenAI, Anthropic, etc.). Typical: 30s–5min for large context windows. Not a code issue — this is external API latency.

**Optimization opportunities:**
- Reduce chat history sent to LLM (already capped at last 8 messages, 2000 chars each)
- Skip LLM entirely for image revisions — the feedback goes directly to the image model, the CMO reply is decorative

---

## Stage 2: storyboard.create (Text Spec)

**What happens:**
- `spec_from_brief()` parses storyboard text into JSON spec
- `validate_spec()` checks structure
- Writes JSON + markdown to disk

**Bottleneck:** None. Runs in ~0ms. Pure deterministic Python.

---

## Stage 3: storyboard.render (Image Generation) ← PRIMARY BOTTLENECK

**What happens:**
- `render_storyboard()` in `json_image_storyboard.py`
- Calls OpenAI `images.edit` (revision) or `images.generate` (fresh)
- Model: `gpt-image-2`
- Writes PNG to `/tmp/bos-storyboard-runs/`

### Timing Data (from DB)

| Run | Elapsed | Attempt Latency | Gap | Mode |
|-----|---------|-----------------|-----|------|
| bcc67511 | 25,319s (7h) | 208s | 25,111s | edit |
| 6139de57 | 5,822s (1.6h) | 194s | 5,627s | edit |
| feb326e4 | 5,141s (1.4h) | 186s | 4,955s | generate |
| ba92d636 | 4,802s (1.3h) | 239s | 4,564s | edit |
| 16db311d | 3,438s (57min) | 210s | 3,228s | edit |
| 444f6f91 | 2,822s (47min) | 211s | 2,611s | edit |
| ca903d7a | 1,413s (24min) | 82s | 1,331s | generate |
| 02ed7a06 | 366s (6min) | — | — | edit |
| ac2484aa | 145s (2.4min) | — | — | generate |

### Key Finding: Massive Gap Between API Latency and Run Elapsed

The OpenAI API call itself takes **80–240 seconds** (stored as `latency_ms` in `run_attempts`). But the run's total elapsed time is **5× to 120× longer**.

**The gap is NOT:**
- Retries (only 1 attempt per run)
- DB writes (sub-second)
- Parent→child queuing (gap is 0s for most)
- Prompt construction (deterministic, sub-second)

**Likely causes of the gap:**
1. **OpenAI rate limiting / queueing** — `gpt-image-2` has strict rate limits. The SDK call blocks until OpenAI accepts the request. The 200s `latency_ms` may only measure the actual generation time, not the queue wait.
2. **Container I/O** — The prompt is ~32KB text + ~3MB base64 image. Writing/reading these to `/tmp` in a Docker container may be slow under load.
3. **`images.edit` with large source image** — The 3MB base64 source image must be uploaded to OpenAI. The `latency_ms` may not include upload time.
4. **No timeout on the OpenAI call** — `_call_openai_edit()` has no explicit timeout. If OpenAI hangs or rate-limits, the call blocks indefinitely.

### Prompt Size
- Typical prompt: ~32,000 chars (just under the 32K limit)
- Image: ~3MB base64 PNG
- The prompt is truncated at 31,900 chars as a safety measure

---

## Stage 4: storyboard.motion.render (Video Generation)

**What happens:**
- `PrevisMotionRenderModule.execute_tool_result()`
- Builds target JSON + prompt (~68K chars)
- Sends to Seedance via ModelArk API
- Polls every 10s for up to 900s (90 polls)

### Timing Data

| Run | Elapsed | Mode | Task ID |
|-----|---------|------|---------|
| 4c74ab54 | 1,330s (22min) | i2v | cgt-20260620134255-268pj |
| cf810edc | 403s (6.7min) | v2v | cgt-20260624024911-v49xx |
| ee058079 | 344s (5.7min) | i2v | cgt-20260624024316-mbscw |
| 7723a965 | 119s (2min) | i2v | FAILED (audio moderation) |
| 3be5a7fe | 330s (5.5min) | — | FAILED |

**Direct test result:** Same prompt + image sent directly to Seedance completed in **150s** (2.5min).

### Bottlenecks:
1. **Seedance generation time** — 120–400s is normal for video generation. Not fixable.
2. **Poll interval** — 10s polling adds up to 90s of unnecessary wait for fast completions.
3. **Prompt size / prompt shaping** — direct Seedance 2.0 T2V accepts long Markdown story prompts as a single text content item. The risky path is not large text by itself; it is wrapping/splitting the prompt in ways that drop sound/music/brand/timing instructions or using the wrong endpoint/model ID.
4. **Audio moderation failures** — Non-deterministic. Same content passes sometimes, fails others.

### Direct T2V large-prompt learning

A direct text-to-video resend of the Widower 15s Markdown prompt succeeded when sent to ModelArk as:

- endpoint: `POST /api/v3/contents/generations/tasks`
- model: `dreamina-seedance-2-0-260128`
- content: exactly one `{"type":"text","text":"<long Markdown prompt>"}` item
- `generate_audio`: snake_case boolean
- no image/video references

Previs now preserves explicit direct T2V prompts (`seedance_prompt`, `raw_prompt`, `direct_prompt`, `text_to_video_prompt`, or `prompt` with `mode=text_to_video`) instead of running them through the normal blueprint splitter/sanitizer. This keeps `Sound:`, `Music:`, exact visible-text constraints, and client brand wording intact.

---

## Stage 5: Post-Generation (Drive Upload)

**What happens:**
- `_store_in_drive()` uploads the generated video to Google Drive
- Happens synchronously after video download

**Bottleneck:** Minor. Drive upload of ~4MB video takes a few seconds.

---

## Summary of Bottlenecks (Ranked by Impact)

| Rank | Stage | Issue | Typical Delay | Fix Difficulty |
|------|-------|-------|---------------|----------------|
| 1 | storyboard.render | OpenAI rate-limit queueing / blocking | 5min–7h | Medium |
| 2 | storyboard.render | No timeout on `_call_openai_edit` | Indefinite | Easy |
| 3 | CMO Chat | Unnecessary LLM call for image revisions | 30s–5min | Easy |
| 4 | storyboard.motion.render | 68K prompt includes full spec + blueprint | Adds latency | Medium |
| 5 | storyboard.motion.render | 10s poll interval | Up to 90s waste | Easy |
| 6 | storyboard.motion.render | Audio moderation failures | Wastes entire run | Fixed (generateAudio:false) |
| 7 | storyboard.render | 3MB base64 image in prompt | Upload time | Medium |

## Quick Wins (Low Effort, High Impact)

1. **Add timeout to `_call_openai_edit()` and `_call_openai_generate()`** — Currently they block forever. A 300s timeout with retry would prevent the 7-hour hangs.

2. **Skip CMO LLM for image revisions** — When revising a `storyboard.render` artifact, the CMO reply is decorative ("Revised storyboard draft is ready for review."). The feedback goes directly to the image model. Skip the LLM call and use a canned reply.

3. **Reduce poll interval for Seedance** — Change from 10s to 5s. Saves ~75s on a typical 150s completion.

4. **Use direct prompt preservation for explicit T2V** — Large text is acceptable when sent as one text content item. Avoid redundant canonical JSON and avoid splitter/sanitizer passes for operator-authored T2V prompts.

## Deeper Fixes (Higher Effort)

5. **Investigate OpenAI rate limiting** — The 200s API latency vs 25000s run elapsed suggests the SDK is blocking on rate limits. Consider:
   - Adding explicit retry with backoff
   - Checking `Retry-After` headers
   - Using a queue-based approach instead of blocking

6. **Compress source image before upload** — The 3MB base64 storyboard image could be resized/compressed before sending to OpenAI. The model doesn't need full resolution for edits.
