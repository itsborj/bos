"""Applies an intent contract's criteria against module output.

Rules evaluated locally:
  max_chars      — len(field) <= threshold
  must_mention   — field contains all required strings
  banned_phrases — field contains none of the banned strings

All other rule names pass with a note of "rule_not_implemented".
"""

from __future__ import annotations

from typing import Any


def _resolve_field(payload: dict, field_path: str) -> Any:
    parts = field_path.split(".")
    current: Any = payload
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _eval_criterion(criterion: dict, payload: dict, overrides: dict | None) -> dict:
    crit_id = criterion.get("id", "unknown")
    rule = criterion.get("rule", "")
    field_path = criterion.get("field", "")
    threshold = criterion.get("threshold")
    severity = criterion.get("severity", "warning")
    crit_type = criterion.get("type", "soft")

    if overrides and crit_id in overrides:
        threshold = overrides[crit_id]

    value = _resolve_field(payload, field_path)
    text = value if isinstance(value, str) else str(value or "")

    if rule == "max_chars":
        limit = int(threshold) if threshold is not None else 9999
        passed = len(text) <= limit
        detail = f"len={len(text)}, limit={limit}"
    elif rule == "must_mention":
        terms = threshold if isinstance(threshold, list) else []
        missing = [t for t in terms if t.lower() not in text.lower()]
        passed = len(missing) == 0
        detail = f"missing={missing}"
    elif rule == "banned_phrases":
        phrases = threshold if isinstance(threshold, list) else []
        found = [p for p in phrases if p.lower() in text.lower()]
        passed = len(found) == 0
        detail = f"found={found}"
    else:
        return {
            "id": crit_id, "rule": rule, "passed": True,
            "note": "rule_not_implemented", "severity": "warning", "type": crit_type,
        }

    return {"id": crit_id, "rule": rule, "passed": passed, "detail": detail, "severity": severity, "type": crit_type}


def evaluate(contract: dict, payload: dict, overrides: dict | None = None) -> dict:
    """Evaluate all criteria against payload. Returns verdict + per-criterion results."""
    criteria = contract.get("criteria_json") or contract.get("criteria", [])
    scoring = contract.get("scoring_json") or contract.get("scoring", {})
    soft_pass_cutoff = float(scoring.get("soft_pass_cutoff", 0.7))

    results = [_eval_criterion(c, payload, overrides) for c in criteria]
    hard_failures = [r for r in results if not r["passed"] and r.get("type") == "hard"]
    soft_failures = [r for r in results if not r["passed"] and r.get("type") == "soft"]
    soft_total = [r for r in results if r.get("type") == "soft"]
    soft_pass_rate = (len(soft_total) - len(soft_failures)) / len(soft_total) if soft_total else 1.0

    if hard_failures:
        verdict = "fail"
    elif soft_pass_rate < soft_pass_cutoff:
        verdict = "escalate"
    else:
        verdict = "pass"

    return {
        "verdict": verdict,
        "results": results,
        "hard_failures": hard_failures,
        "soft_failures": soft_failures,
    }
