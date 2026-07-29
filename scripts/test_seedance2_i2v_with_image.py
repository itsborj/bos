from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"
TASKS_URL = f"{BASE_URL}/contents/generations/tasks"
DEFAULT_MODEL = "dreamina-seedance-2-0-260128"
DEFAULT_PROMPT_FILE = Path(__file__).resolve().parent / "testdata" / "THE_WIDOWER_15SEC_STORYBOARD_REFINED.json"
DEFAULT_IMAGE_PATH = Path("/home/ubu/bos/plugins/Widower - 6-30.png")
TERMINAL_STATUSES = {"succeeded", "failed", "expired", "cancelled"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_prompt_text(path: Path) -> str:
    raw = path.expanduser().read_text(encoding="utf-8")
    # Keep the exact raw JSON text as the prompt, but validate that it is JSON.
    json.loads(raw)
    return raw


def _image_data_url(path: Path) -> str:
    p = path.expanduser()
    raw = p.read_bytes()
    mime = mimetypes.guess_type(str(p))[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def _build_payload(
    prompt_text: str,
    image_path: Path,
    *,
    model: str,
    resolution: str,
    ratio: str,
    duration: int,
    generate_audio: bool,
    watermark: bool,
    image_role: str,
) -> dict:
    return {
        "model": model,
        "content": [
            {"type": "text", "text": prompt_text},
            {
                "type": "image_url",
                "image_url": {"url": _image_data_url(image_path)},
                "role": image_role,
            },
        ],
        "resolution": resolution,
        "ratio": ratio,
        "duration": duration,
        "generate_audio": generate_audio,
        "watermark": watermark,
    }


def _redact_payload(payload: dict) -> dict:
    redacted = json.loads(json.dumps(payload))
    for item in redacted.get("content", []):
        url = str(item.get("image_url", {}).get("url", ""))
        if item.get("type") == "image_url" and url.startswith("data:"):
            mime = url.split(";", 1)[0].removeprefix("data:")
            item["image_url"]["url"] = f"<embedded {mime} base64 image data>"
    return redacted


def _api_key() -> str | None:
    for key in ("ARK_API_KEY", "BYTEPLUS_API_KEY", "BYTEPLUS_MODELARK_API_KEY"):
        value = os.environ.get(key)
        if value and value.strip():
            return value.strip()
    key_file = Path("/tmp/ark_api_key_for_pi")
    if key_file.exists():
        value = key_file.read_text(encoding="utf-8").strip()
        if value:
            return value
    return None


def _request_json(method: str, url: str, api_key: str, *, body: dict | None = None, timeout: int = 180) -> dict:
    with httpx.Client(timeout=timeout) as client:
        response = client.request(
            method,
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "BOS-Seedance2-I2V-SmokeTest/0.1",
            },
        )
    if not response.is_success:
        try:
            detail = response.json()
        except Exception:
            detail = {"raw": response.text}
        raise RuntimeError(f"ModelArk HTTP {response.status_code}: {json.dumps(detail, ensure_ascii=False)}")
    return response.json() if response.text else {}


def _poll_task(api_key: str, task_id: str, *, poll_seconds: int, poll_interval: int) -> dict:
    deadline = time.time() + poll_seconds
    last_status = None
    while time.time() < deadline:
        task = _request_json("GET", f"{TASKS_URL}/{quote(task_id)}", api_key, timeout=120)
        status = str(task.get("status") or "")
        if status != last_status:
            print(f"[{_now_iso()}] status={status}", file=sys.stderr)
            last_status = status
        if status in TERMINAL_STATUSES:
            return task
        time.sleep(poll_interval)
    return {"id": task_id, "status": "timeout", "message": f"Task did not finish within {poll_seconds}s"}


def _extract_video_url(task: dict) -> str | None:
    content = task.get("content") if isinstance(task, dict) else None
    if isinstance(content, dict):
        return content.get("video_url") or content.get("videoUrl") or content.get("file_url")
    return task.get("video_url") or task.get("videoUrl") or task.get("file_url")


def _download(url: str, dest: Path) -> int:
    with httpx.Client(timeout=300) as client:
        response = client.get(url, headers={"User-Agent": "BOS-Seedance2-I2V-SmokeTest/0.1"})
    response.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(response.content)
    return len(response.content)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Standalone Seedance 2.0 I2V/reference-image smoke test. "
            "Does not use or modify Previs Motion piping."
        )
    )
    parser.add_argument("--prompt-file", type=Path, default=DEFAULT_PROMPT_FILE)
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE_PATH)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--resolution", default="480p", choices=["480p", "720p", "1080p", "4k"])
    parser.add_argument("--ratio", default="3:4")
    parser.add_argument("--duration", type=int, default=15)
    parser.add_argument("--image-role", default="reference_image", choices=["reference_image", "first_frame"])
    parser.add_argument("--silent", action="store_true", help="Set generate_audio=false. Default is audio on.")
    parser.add_argument("--watermark", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=900)
    parser.add_argument("--poll-interval", type=int, default=5)
    parser.add_argument("--no-poll", action="store_true")
    parser.add_argument("--download", action="store_true", help="Download final MP4 into the run directory.")
    parser.add_argument("--dry-run", action="store_true", help="Write/print payload only; do not call ModelArk.")
    parser.add_argument("--output-dir", type=Path, help="Run artifact directory. Default: /tmp/seedance2-i2v-<timestamp>.")
    parser.add_argument("--print-full-payload", action="store_true", help="Print embedded base64 payload. Large output.")
    args = parser.parse_args()

    if not args.prompt_file.expanduser().is_file():
        parser.error(f"Prompt file not found: {args.prompt_file}")
    if not args.image.expanduser().is_file():
        parser.error(f"Image file not found: {args.image}")

    started = time.perf_counter()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = (args.output_dir or Path("/tmp") / f"seedance2-i2v-{stamp}").expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    prompt_text = _load_prompt_text(args.prompt_file)
    payload = _build_payload(
        prompt_text,
        args.image,
        model=args.model,
        resolution=args.resolution,
        ratio=args.ratio,
        duration=args.duration,
        generate_audio=not args.silent,
        watermark=args.watermark,
        image_role=args.image_role,
    )

    (out_dir / "payload.redacted.json").write_text(json.dumps(_redact_payload(payload), indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "prompt.json.txt").write_text(prompt_text, encoding="utf-8")

    print(f"run_dir={out_dir}", file=sys.stderr)
    print(
        "profile: "
        f"model={args.model} resolution={args.resolution} ratio={args.ratio} "
        f"duration={args.duration}s generate_audio={not args.silent} image_role={args.image_role}",
        file=sys.stderr,
    )
    print(f"profile: prompt_bytes={len(prompt_text.encode('utf-8'))} image_bytes={args.image.expanduser().stat().st_size}", file=sys.stderr)

    if args.dry_run:
        printable = payload if args.print_full_payload else _redact_payload(payload)
        print(json.dumps(printable, indent=2, ensure_ascii=False))
        return 0

    api_key = _api_key()
    if not api_key:
        parser.error("Set ARK_API_KEY, BYTEPLUS_API_KEY, or BYTEPLUS_MODELARK_API_KEY before submitting.")

    create_started = time.perf_counter()
    created = _request_json("POST", TASKS_URL, api_key, body=payload, timeout=180)
    create_elapsed = time.perf_counter() - create_started
    (out_dir / "created.json").write_text(json.dumps(created, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(created, indent=2, ensure_ascii=False))
    print(f"profile: create_elapsed_s={create_elapsed:.2f}", file=sys.stderr)

    task_id = created.get("id")
    if args.no_poll or not task_id:
        return 0

    poll_started = time.perf_counter()
    final_task = _poll_task(api_key, str(task_id), poll_seconds=args.poll_seconds, poll_interval=args.poll_interval)
    poll_elapsed = time.perf_counter() - poll_started
    (out_dir / "task.json").write_text(json.dumps(final_task, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(final_task, indent=2, ensure_ascii=False))

    video_url = _extract_video_url(final_task)
    if video_url:
        (out_dir / "video_url.txt").write_text(video_url + "\n", encoding="utf-8")
        print(f"video_url={video_url}", file=sys.stderr)
        if args.download:
            size = _download(video_url, out_dir / "output.mp4")
            print(f"downloaded={out_dir / 'output.mp4'} bytes={size}", file=sys.stderr)

    total_elapsed = time.perf_counter() - started
    usage = final_task.get("usage") if isinstance(final_task, dict) else None
    if usage:
        print(f"profile: usage={json.dumps(usage, ensure_ascii=False)}", file=sys.stderr)
    print(f"profile: poll_elapsed_s={poll_elapsed:.2f} total_elapsed_s={total_elapsed:.2f}", file=sys.stderr)
    return 0 if final_task.get("status") == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
