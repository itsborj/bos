from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"
TASKS_URL = f"{BASE_URL}/contents/generations/tasks"
DEFAULT_MODEL = "dreamina-seedance-2-0-260128"
DEFAULT_PROMPT_FILE = Path(__file__).resolve().parent / "testdata" / "THE_WIDOWER_15SEC_STORYBOARD_REFINED.json"
POLL_INTERVAL_SECONDS = 5
TERMINAL_STATUSES = {"succeeded", "failed", "expired", "cancelled"}


def _load_prompt_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    json.loads(raw)
    return raw


def _build_payload(
    prompt_text: str,
    *,
    model: str,
    resolution: str,
    ratio: str,
    duration: int,
    generate_audio: bool,
    watermark: bool,
) -> dict:
    return {
        "model": model,
        "content": [{"type": "text", "text": prompt_text}],
        "resolution": resolution,
        "ratio": ratio,
        "duration": duration,
        "generate_audio": generate_audio,
        "watermark": watermark,
    }


def _submit_task(api_key: str, payload: dict) -> dict:
    with httpx.Client(timeout=180) as client:
        response = client.post(
            TASKS_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "BOS-Seedance-Endpoint-Test/0.1",
            },
        )
    response.raise_for_status()
    return response.json()


def _poll_task(api_key: str, task_id: str, poll_seconds: int) -> dict:
    deadline = time.time() + poll_seconds
    last_status = None
    while time.time() < deadline:
        with httpx.Client(timeout=60) as client:
            response = client.get(
                f"{TASKS_URL}/{task_id}",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "BOS-Seedance-Endpoint-Test/0.1",
                },
            )
        response.raise_for_status()
        task = response.json()
        status = str(task.get("status") or "")
        if status != last_status:
            print(f"status={status}", file=sys.stderr)
            last_status = status
        if status in TERMINAL_STATUSES:
            return task
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"Task {task_id} did not finish within {poll_seconds}s")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Submit the exact THE_WIDOWER_15SEC_STORYBOARD_REFINED JSON file as the text prompt "
            "to the same Seedance 2.0 ModelArk endpoint used by previs-motion."
        )
    )
    parser.add_argument("--prompt-file", type=Path, default=DEFAULT_PROMPT_FILE)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--resolution", default="720p")
    parser.add_argument("--ratio", default="3:4")
    parser.add_argument("--duration", type=int, default=15)
    parser.add_argument("--generate-audio", action="store_true", help="Enable audio generation.")
    parser.add_argument("--watermark", action="store_true", help="Enable the visible AI watermark.")
    parser.add_argument("--poll-seconds", type=int, default=900)
    parser.add_argument("--no-poll", action="store_true", help="Submit only and stop after the task is created.")
    parser.add_argument("--dry-run", action="store_true", help="Print the request payload without calling ModelArk.")
    parser.add_argument(
        "--write-payload",
        type=Path,
        help="Optional file path to save the final request payload for inspection.",
    )
    args = parser.parse_args()

    prompt_text = _load_prompt_text(args.prompt_file)
    payload = _build_payload(
        prompt_text,
        model=args.model,
        resolution=args.resolution,
        ratio=args.ratio,
        duration=args.duration,
        generate_audio=args.generate_audio,
        watermark=args.watermark,
    )

    if args.write_payload:
        args.write_payload.parent.mkdir(parents=True, exist_ok=True)
        args.write_payload.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    api_key = os.environ.get("BYTEPLUS_API_KEY") or os.environ.get("BYTEPLUS_MODELARK_API_KEY")
    if not api_key:
        parser.error("Set BYTEPLUS_API_KEY or BYTEPLUS_MODELARK_API_KEY before submitting the test.")

    created = _submit_task(api_key, payload)
    print(json.dumps(created, indent=2, ensure_ascii=False))

    task_id = created.get("id")
    if args.no_poll or not task_id:
        return 0

    final_task = _poll_task(api_key, str(task_id), args.poll_seconds)
    print(json.dumps(final_task, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
