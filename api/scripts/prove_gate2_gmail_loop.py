#!/usr/bin/env python3
"""Gate 2.6 proof harness: Gmail-only objective loop.

Runs the primitive loop through the public API:
Objective → Gmail draft artifact → approval → manual outcome → MemoryEvent → DecisionBrief → Stream cards.

Environment:
  BOS_BASE_URL       default http://localhost:8000
  API_SECRET_KEY     required unless --api-key is passed
  BOS_BRAND_ID       optional; defaults to first brand returned by /brands

This script intentionally creates records tagged with created_from/source_ref=gate2_proof_script.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _request(base: str, key: str, method: str, path: str, body: dict | None = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base.rstrip("/") + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "X-API-Key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        raise RuntimeError(f"{method} {path} failed {exc.code}: {raw}") from exc


def _brand_id(base: str, key: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    brands = _request(base, key, "GET", "/brands")
    rows = brands.get("brands") or []
    if not rows:
        raise RuntimeError("No brand found. Create/connect a brand before proving Gate 2.")
    return rows[0]["id"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("BOS_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.getenv("API_SECRET_KEY"))
    parser.add_argument("--brand-id", default=os.getenv("BOS_BRAND_ID"))
    parser.add_argument("--skip-artifact", action="store_true", help="Skip Gmail draft execution; useful when provider credentials are unavailable")
    args = parser.parse_args()

    if not args.api_key:
        print("API key required via --api-key or API_SECRET_KEY", file=sys.stderr)
        return 2

    brand_id = _brand_id(args.base_url, args.api_key, args.brand_id)
    print(f"brand_id={brand_id}")

    objective = _request(args.base_url, args.api_key, "POST", "/objectives", {
        "brand_id": brand_id,
        "status": "active",
        "summary": "Generate pipeline from dormant prospects through Gmail",
        "success_metric": "Proof of pipeline/reply movement from Gmail-only outreach",
        "horizon": "Gate 2 proof",
        "created_from": "gate2_proof_script",
    })
    objective_id = objective["id"]
    print(f"objective_id={objective_id}")

    run_id = None
    if not args.skip_artifact:
        run = _request(args.base_url, args.api_key, "POST", "/runs", {
            "module_id": "marketing.channel.gmail.outreach.draft",
            "policy": "balanced",
            "brand_id": brand_id,
            "payload": {
                "brief": {
                    "product_name": "Klaroha BOS",
                    "audience": "dormant prospects who previously showed interest",
                    "tone": "clear, concise, proof-led",
                    "key_benefit": "turn scattered marketing signals into a decision-ready operating loop",
                    "objective_id": objective_id,
                }
            },
        })
        run_id = run["run_id"]
        print(f"gmail_draft_run_id={run_id}")
        _request(args.base_url, args.api_key, "PATCH", f"/runs/{run_id}/approve")
        print("gmail_draft_approved=true")
    else:
        print("gmail_draft_skipped=true")

    outcome = _request(args.base_url, args.api_key, "POST", "/outcomes/evaluate", {
        "brand_id": brand_id,
        "objective_id": objective_id,
        "source_ref": f"gate2_proof_script:{run_id or 'manual_gmail_send_registered'}",
        "summary": "Gate 2 proof outcome: Gmail proof step produced reply movement and one booked conversation",
        "metrics": {"sent": 15, "replies": 3, "booked_calls": 1, "pipeline": "$6k"},
        "topic_tags": ["outcome", "commitment"],
        "confidence_source": "manually_reported",
        "full_record": {"proof_run": True, "gmail_only": True, "artifact_run_id": run_id},
    })
    print(f"outcome_id={outcome['outcome']['id']} memory_event_id={outcome['memory_event_id']}")

    brief = _request(args.base_url, args.api_key, "POST", "/decision-briefs/generate", {
        "brand_id": brand_id,
        "objective_id": objective_id,
    })
    print(f"decision_brief_id={brief['id']} confidence={brief['confidence']}")

    refresh = _request(args.base_url, args.api_key, "POST", "/stream/refresh")
    print(f"stream_refresh={refresh['message']}")

    stream = _request(args.base_url, args.api_key, "GET", "/stream?include_read=true")
    updates = stream.get("updates") or []
    objective_cards = [u for u in updates if (u.get("data_json") or {}).get("objective_ref") == objective_id]
    has_outcome = any(u.get("type") == "outcome" for u in objective_cards)
    has_decision = any(u.get("type") == "decision_brief" for u in objective_cards)
    if not has_outcome or not has_decision:
        raise RuntimeError(
            f"Gate 2 proof failed: stream cards missing outcome={has_outcome} decision_brief={has_decision}"
        )

    print("PASS gate2_gmail_loop_proof=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
