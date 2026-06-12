#!/usr/bin/env python3
"""
CMO Agent Loop — monitor → prioritize → delegate → report

Stress test mode:   python3 cmo_loop.py --dry-run
Production mode:    python3 cmo_loop.py
Specific brand:     python3 cmo_loop.py --brand <brand_id>

The loop:
  1. GET /agent/state        — find brands with pending work
  2. GET /agent/context      — load brand profile for brief building
  3. GET /agent/capabilities — pick the right module for each job
  4. POST /agent/execute     — dispatch; result lands at pending_review
  5. Report what was done; human reviews via workspace UI

Agent never approves its own output. Always stops at pending_review.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Optional
import urllib.error
import urllib.request

# ── Config ────────────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:8000"
API_KEY  = "change-me-before-deploying"

# Modules the loop will dispatch autonomously (read-only and safe drafts only)
LOOP_MODULES = [
    "marketing.channel.clickup.tasks.read",
]

# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _req(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return {"_error": exc.code, "_body": exc.read().decode()}
    except Exception as exc:
        return {"_error": str(exc)}


def get(path: str) -> dict:
    return _req("GET", path)

def post(path: str, body: dict) -> dict:
    return _req("POST", path, body)

def patch(path: str, body: dict) -> dict:
    return _req("PATCH", path, body)


# ── Loop logic ────────────────────────────────────────────────────────────────

def run_loop(dry_run: bool = False, target_brand_id: Optional[str] = None) -> None:
    print(f"\n{'[DRY RUN] ' if dry_run else ''}CMO Agent Loop — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("─" * 60)

    # 1. Monitor
    state = get("/agent/state")
    if "_error" in state:
        print(f"ERROR: /agent/state → {state}")
        sys.exit(1)

    print(f"Workspace: {state['workspace_name']}")
    print(f"Total pending approvals: {state['total_pending']}")
    print()

    brands = state["brands"]
    if target_brand_id:
        brands = [b for b in brands if b["brand_id"] == target_brand_id]
        if not brands:
            print(f"ERROR: brand {target_brand_id} not found in state")
            sys.exit(1)

    # 2. Load capabilities once
    caps = get("/agent/capabilities")
    if "_error" in caps:
        print(f"ERROR: /agent/capabilities → {caps}")
        sys.exit(1)
    available_modules = {c["module_id"] for c in caps}
    runnable = [m for m in LOOP_MODULES if m in available_modules]

    if not runnable:
        print("No runnable modules found in installed capabilities.")
        return

    print(f"Runnable modules this loop: {runnable}")
    print()

    results: list[dict] = []

    for brand in brands:
        brand_id   = brand["brand_id"]
        brand_name = brand["name"]
        pending    = brand["pending_approvals"]
        pm_enabled = brand["pm_sync_enabled"]

        print(f"Brand: {brand_name}")
        print(f"  Pending approvals : {pending}")
        print(f"  PM sync enabled   : {pm_enabled}")

        # 3. Load context
        ctx = get(f"/agent/context/{brand_id}")
        if "_error" in ctx:
            print(f"  SKIP: context error → {ctx}")
            print()
            continue

        print(f"  Voice: {ctx.get('voice') or '—'}  |  Tone: {ctx.get('tone') or '—'}")

        # 4. Delegate — run each module for this brand
        for module_id in runnable:
            print(f"  → {module_id}")

            if dry_run:
                print("     [dry-run] would POST /agent/execute")
                results.append({"brand": brand_name, "module": module_id, "status": "dry_run"})
                continue

            t0 = time.perf_counter()
            result = post("/agent/execute", {
                "module_id": module_id,
                "brand_id": brand_id,
                "brief": {},
            })
            elapsed = round((time.perf_counter() - t0) * 1000)

            if "_error" in result:
                print(f"     FAILED ({elapsed}ms): {result}")
                results.append({"brand": brand_name, "module": module_id, "status": "error", "detail": result})
                continue

            run_id        = result.get("run_id")
            run_status    = result.get("status")
            approval      = result.get("approval_status")
            self_check    = (result.get("result") or {}).get("self_check")
            content_snip  = ((result.get("result") or {}).get("content") or "")[:80].replace("\n", " ")

            print(f"     run_id       : {run_id}")
            print(f"     status       : {run_status}  |  self_check: {self_check}  |  approval: {approval}")
            print(f"     preview      : {content_snip}…")
            print(f"     latency      : {elapsed}ms")

            results.append({
                "brand": brand_name,
                "module": module_id,
                "run_id": run_id,
                "status": run_status,
                "self_check": self_check,
                "approval_status": approval,
                "latency_ms": elapsed,
            })

        print()

    # 5. Report
    print("─" * 60)
    print(f"Summary: {len(results)} dispatched")
    ok      = [r for r in results if r.get("status") == "success"]
    partial = [r for r in results if r.get("status") == "partial"]
    failed  = [r for r in results if r.get("status") in ("error", "failed")]
    dry     = [r for r in results if r.get("status") == "dry_run"]

    if ok:      print(f"  succeeded    : {len(ok)}")
    if partial: print(f"  partial      : {len(partial)}")
    if failed:  print(f"  failed       : {len(failed)}")
    if dry:     print(f"  dry-run      : {len(dry)}")

    if failed:
        print("\nFailures:")
        for r in failed:
            print(f"  {r['brand']} / {r['module']} → {r.get('detail')}")

    pending_review = [r for r in results if r.get("approval_status") == "pending"]
    if pending_review:
        print(f"\n{len(pending_review)} run(s) waiting for your review:")
        for r in pending_review:
            print(f"  run_id: {r['run_id']}  [{r['brand']} / {r['module']}]")
        print("\nReview via workspace UI or:")
        for r in pending_review:
            print(f"  curl -s -X PATCH {BASE_URL}/agent/review/{r['run_id']} \\")
            print(f"    -H 'X-API-Key: {API_KEY}' \\")
            print("    -H 'Content-Type: application/json' \\")
            print("    -d '{\"action\":\"approve\"}'")  # noqa: Q000

# ── Error injection tests ─────────────────────────────────────────────────────

def run_error_tests() -> None:
    """Test failure modes — validates harness handles bad input cleanly."""
    print("\nError injection tests")
    print("─" * 60)

    cases = [
        ("bad module_id",    "POST", "/agent/execute",
         {"module_id": "does.not.exist", "brand_id": None, "brief": {}}),
        ("bad brand_id",     "POST", "/agent/execute",
         {"module_id": "marketing.channel.clickup.tasks.read", "brand_id": "not-a-uuid", "brief": {}}),
        ("bad review action","PATCH", "/agent/review/00000000-0000-0000-0000-000000000000",
         {"action": "explode"}),
        ("unknown run_id",   "PATCH", "/agent/review/00000000-0000-0000-0000-000000000000",
         {"action": "approve"}),
        ("unknown brand ctx","GET",   "/agent/context/00000000-0000-0000-0000-000000000000", None),
    ]

    all_passed = True
    for label, method, path, body in cases:
        if method == "GET":
            result = get(path)
        elif method == "POST":
            result = post(path, body)
        else:
            result = patch(path, body)

        error_code = result.get("_error") or (result.get("detail") and "error")
        passed = "_error" in result or "detail" in result
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  [{status}] {label}: {error_code or result}")

    print(f"\nError tests: {'all passed' if all_passed else 'FAILURES ABOVE'}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CMO agent loop")
    parser.add_argument("--dry-run",    action="store_true", help="Plan without executing")
    parser.add_argument("--brand",      metavar="ID",        help="Run for one brand only")
    parser.add_argument("--error-test", action="store_true", help="Run error injection tests only")
    args = parser.parse_args()

    if args.error_test:
        run_error_tests()
    else:
        run_loop(dry_run=args.dry_run, target_brand_id=args.brand)
        if not args.dry_run:
            print()
            run_error_tests()
