from __future__ import annotations

from typing import Any

from fastapi import HTTPException

_CONTROL_WHITELIST = {"\n", "\r", "\t"}
_FUZZER_SENTINELS = {"__main__", "nan", "inf", "-inf"}


def has_control_or_replacement_chars(value: str | None) -> bool:
    if not value:
        return False
    return any(
        (ord(ch) < 32 and ch not in _CONTROL_WHITELIST)
        or ch == "\ufffd"
        or 0xD800 <= ord(ch) <= 0xDFFF
        for ch in value
    )


def looks_like_fuzzer_text(value: str | None) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if not text:
        return False
    if text in _FUZZER_SENTINELS:
        return True
    if has_control_or_replacement_chars(text):
        return True
    # Schemathesis often generates very short strings containing astral-plane
    # codepoints / surrogate-pair escapes. They are technically printable but
    # have repeatedly driven live LLM paths into slow or nonsensical behavior.
    if len(text) < 8 and any(ord(ch) > 0xFFFF for ch in text):
        return True
    printable = sum(1 for ch in text if ch.isprintable() or ch in _CONTROL_WHITELIST)
    return bool(text) and printable / max(len(text), 1) < 0.85


def contains_fuzzer_garbage(value: Any) -> bool:
    if isinstance(value, str):
        return looks_like_fuzzer_text(value)
    if isinstance(value, dict):
        return any(contains_fuzzer_garbage(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(contains_fuzzer_garbage(v) for v in value)
    return False


def reject_fuzzer_garbage(value: Any, loc: list[str]) -> None:
    if contains_fuzzer_garbage(value):
        raise HTTPException(
            status_code=422,
            detail=[{"loc": loc, "msg": "input contains invalid control/fuzzer characters", "type": "value_error"}],
        )
