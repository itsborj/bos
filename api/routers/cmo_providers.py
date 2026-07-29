"""
CMO provider interface — unified LLM calls + provider resolution.

Two functions:
  resolve_provider(db, ws, settings) -> dict | None
  call_cmo(messages, config, tools, on_text) -> dict

The agent doesn't know which LLM is running.
The provider doesn't know what the agent is doing.

Pattern: Smith's providers.py, adapted for async FastAPI.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ai_provider_registry import get_all_api_configs, get_default_model, get_platform_key, get_provider_api_config
from model_overrides import get_backend_override, parse_model_ref
from provider_auth import resolve_stored_provider_credential
from routers.backend_settings import resolve_backend_override

logger = logging.getLogger("bos.cmo_providers")


async def _provider_config_for(
    db: AsyncSession,
    ws,
    settings,
    provider: str,
    model: str,
) -> dict | None:
    """Resolve credentials for a configured CMO provider/model."""
    if not get_provider_api_config(provider):
        logger.warning("CMO v2 provider '%s' is not supported by native tool loop", provider)
        return None

    if ws:
        key, auth_mode = await resolve_stored_provider_credential(
            db, ws.id, provider, settings, tolerate_decryption_failure=True)
        if key and (auth_mode in {None, "api_key"}):
            return {"provider": provider, "model": model, "api_key": key, "auth_mode": auth_mode or "api_key", "max_tokens": 4096}
        # Admin OpenAI login stores a ChatGPT/Codex OAuth token and validates it
        # against chatgpt.com, not api.openai.com. Preserve that auth surface so
        # chat uses the same endpoint that Admin validated instead of silently
        # falling back to another key/provider.
        if key and provider == "openai" and auth_mode == "oauth":
            return {"provider": provider, "model": model, "api_key": key, "auth_mode": "oauth", "max_tokens": 4096}

    platform_key = get_platform_key(provider, settings)
    if not platform_key and provider == "anthropic":
        platform_key = getattr(settings, "platform_anthropic_key", "") or None
    if platform_key:
        return {"provider": provider, "model": model, "api_key": platform_key, "max_tokens": 4096}
    return None


def _provider_key(cfg: dict) -> tuple[str | None, str | None]:
    return cfg.get("provider"), cfg.get("model")


def _runtime_surface_key(cfg: dict) -> tuple[str | None, ...]:
    """Identify the endpoint/auth surface used by a runtime candidate.

    OpenAI OAuth models all use the same ChatGPT/Codex endpoint and credential.
    A registry-default OpenAI model is therefore not an independent fallback and
    may not even be supported by that endpoint.
    """
    provider = cfg.get("provider")
    auth_mode = cfg.get("auth_mode") or "api_key"
    if auth_mode == "oauth":
        return provider, auth_mode
    return provider, auth_mode, cfg.get("model")


def _with_runtime_fallbacks(primary: dict, fallbacks: list[dict]) -> dict:
    """Attach independent runtime fallbacks while preserving the provider contract."""
    seen = {_runtime_surface_key(primary)}
    usable: list[dict] = []
    for fallback in fallbacks:
        key = _runtime_surface_key(fallback)
        if key in seen:
            continue
        clean = dict(fallback)
        clean.pop("fallbacks", None)
        usable.append(clean)
        seen.add(key)
    if not usable:
        return primary
    cfg = dict(primary)
    cfg["fallbacks"] = usable
    return cfg


async def _available_provider_configs(db: AsyncSession, ws, settings) -> list[dict]:
    configs: list[dict] = []
    seen: set[tuple[str | None, str | None]] = set()
    for provider in ("anthropic", "openai", "gemini", "openrouter"):
        model = get_default_model(provider)
        if not model:
            continue
        cfg = await _provider_config_for(db, ws, settings, provider, model)
        if not cfg:
            continue
        key = _provider_key(cfg)
        if key in seen:
            continue
        configs.append(cfg)
        seen.add(key)
    return configs


async def resolve_provider(db: AsyncSession, ws, settings) -> dict | None:
    """Return provider config for call_cmo().

    Chat v2 must follow Admin → AI Providers → CMO Brain, stored as the
    `cmo.main` execution backend override. When that override is non-strict,
    attach runtime fallbacks so transient provider 429s can fail over before the
    operator sees an error.
    """
    configured = None
    if ws:
        configured = await resolve_backend_override(db, ws.id, "cmo.main")
    configured = configured or get_backend_override(settings, "cmo.main") or parse_model_ref(getattr(settings, "cmo_chat_model", ""))

    if configured:
        if configured.modality != "text":
            logger.error("Configured CMO backend must use text modality, got '%s'", configured.modality)
            return None
        if configured.model_id:
            cfg = await _provider_config_for(db, ws, settings, configured.provider, configured.model_id)
            if cfg:
                if configured.strict:
                    return cfg
                fallbacks = await _available_provider_configs(db, ws, settings)
                return _with_runtime_fallbacks(cfg, fallbacks)
            if configured.strict:
                return None

    # Auto-select fallback when no usable CMO Brain override is configured.
    configs = await _available_provider_configs(db, ws, settings)
    if not configs:
        return None
    return _with_runtime_fallbacks(configs[0], configs[1:])

# ── Provider registry ────────────────────────────────────────────────────────
# Derived from ai_provider_registry — the single source of truth.

PROVIDERS = get_all_api_configs()


# ── Tool schema builders ─────────────────────────────────────────────────────

def _build_tool_schema_anthropic(tools: dict) -> list[dict]:
    """Build Anthropic-format tool schemas from a {name: ToolDef} dict."""
    result = []
    for name, tool in tools.items():
        schema: dict[str, Any] = {
            "name": name,
            "description": tool["description"],
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": tool.get("required", []),
            },
        }
        for pname, pdef in tool.get("parameters", {}).items():
            schema["input_schema"]["properties"][pname] = {
                "type": pdef.get("type", "string"),
                "description": pdef.get("description", ""),
            }
            if "enum" in pdef:
                schema["input_schema"]["properties"][pname]["enum"] = pdef["enum"]
        result.append(schema)
    return result


def _build_tool_schema_openai(tools: dict) -> list[dict]:
    """Build OpenAI-format tool schemas from a {name: ToolDef} dict."""
    result = []
    for name, tool in tools.items():
        properties = {}
        for pname, pdef in tool.get("parameters", {}).items():
            prop: dict[str, Any] = {
                "type": pdef.get("type", "string"),
                "description": pdef.get("description", ""),
            }
            if "enum" in pdef:
                prop["enum"] = pdef["enum"]
            properties[pname] = prop
        result.append({
            "type": "function",
            "function": {
                "name": name,
                "description": tool["description"],
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": tool.get("required", []),
                },
            },
        })
    return result


# ── Message conversion ───────────────────────────────────────────────────────

def _to_anthropic_messages(messages: list[dict]) -> list[dict]:
    """Convert OpenAI-format messages to Anthropic format."""
    result = []
    for msg in messages:
        role = msg["role"]
        if role == "system":
            continue  # system goes separately
        if role == "tool":
            result.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id", ""),
                    "content": str(msg.get("content", "")),
                }],
            })
        elif role == "assistant" and msg.get("tool_calls"):
            content_blocks = []
            for tc in msg["tool_calls"]:
                fn = tc.get("function", tc)
                try:
                    args = json.loads(fn.get("arguments", "{}")) if isinstance(fn.get("arguments"), str) else fn.get("arguments", {})
                except (json.JSONDecodeError, TypeError):
                    args = {}
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc.get("id", ""),
                    "name": fn.get("name", ""),
                    "input": args,
                })
            result.append({"role": "assistant", "content": content_blocks})
        else:
            result.append({"role": role, "content": str(msg.get("content", ""))})
    return result


def _to_openai_messages(messages: list[dict], system_prompt: str) -> list[dict]:
    """Build OpenAI-format messages with system prompt."""
    result = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        role = msg["role"]
        if role == "system":
            continue
        if role == "tool":
            result.append({
                "role": "tool",
                "tool_call_id": msg.get("tool_call_id", ""),
                "content": str(msg.get("content", "")),
            })
        elif role == "assistant" and msg.get("tool_calls"):
            result.append({
                "role": "assistant",
                "content": msg.get("content"),
                "tool_calls": msg["tool_calls"],
            })
        else:
            result.append({"role": role, "content": str(msg.get("content", ""))})
    return result


# ── Response parsing ─────────────────────────────────────────────────────────

def _parse_anthropic_response(data: dict) -> dict:
    """Parse Anthropic response → {"type": "text", "text": "..."} or {"type": "tool_calls", "tool_calls": [...]}"""
    text_parts = []
    tool_calls = []

    for block in data.get("content", []):
        if block.get("type") == "text":
            text_parts.append(str(block.get("text", "")))
        elif block.get("type") == "tool_use":
            tool_calls.append({
                "id": block.get("id", ""),
                "name": block.get("name", ""),
                "args": block.get("input", {}),
            })

    if tool_calls:
        return {"type": "tool_calls", "tool_calls": tool_calls}
    return {"type": "text", "text": "".join(text_parts).strip()}


def _parse_openai_response(data: dict) -> dict:
    """Parse OpenAI/OpenRouter response → {"type": "text", "text": "..."} or {"type": "tool_calls", "tool_calls": [...]}"""
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message", {})
    text = str(msg.get("content") or "").strip()
    tool_calls = []

    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function", {})
        try:
            args = json.loads(fn.get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError):
            args = {}
        tool_calls.append({
            "id": tc.get("id", ""),
            "name": fn.get("name", ""),
            "args": args,
        })

    if tool_calls:
        return {"type": "tool_calls", "tool_calls": tool_calls}
    return {"type": "text", "text": text}


# ── Streaming ────────────────────────────────────────────────────────────────

async def _raise_for_stream_status(resp: httpx.Response) -> None:
    """Raise HTTPStatusError for streamed responses without losing the body.

    httpx streaming responses do not expose `.text` until the body has been
    read. `call_cmo()` logs HTTP error previews, so provider streaming paths
    must buffer error bodies before raising or the original provider error gets
    masked by `ResponseNotRead`.
    """
    if not resp.is_error:
        return
    try:
        await resp.aread()
    except Exception:
        # Preserve the HTTPStatusError even if the body cannot be buffered.
        pass
    resp.raise_for_status()


async def _response_error_preview(resp: httpx.Response) -> str:
    """Return a safe, short error-body preview for logging."""
    try:
        if not resp.is_stream_consumed and not resp.is_closed:
            await resp.aread()
        return resp.text[:300]
    except Exception as exc:
        return f"<response body unavailable: {type(exc).__name__}: {exc}>"


async def _stream_anthropic(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    body: dict,
    on_text,
) -> dict:
    """Stream Anthropic SSE, calling on_text(delta) for each text chunk."""
    body["stream"] = True
    text_parts = []
    tool_calls: list[dict] = []

    async with client.stream("POST", url, headers=headers, json=body, timeout=300) as resp:
        await _raise_for_stream_status(resp)
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            data_str = line[6:]
            try:
                event = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            if event.get("type") == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    text = delta.get("text", "")
                    text_parts.append(text)
                    if on_text:
                        on_text(text)
                elif delta.get("type") == "input_json_delta":
                    idx = event.get("index", 0)
                    while len(tool_calls) <= idx:
                        tool_calls.append({"id": "", "name": "", "args_str": ""})
                    tool_calls[idx]["args_str"] += delta.get("partial_json", "")

            elif event.get("type") == "content_block_start":
                block = event.get("content_block", {})
                if block.get("type") == "tool_use":
                    idx = event.get("index", 0)
                    while len(tool_calls) <= idx:
                        tool_calls.append({"id": "", "name": "", "args_str": ""})
                    tool_calls[idx]["id"] = block.get("id", "")
                    tool_calls[idx]["name"] = block.get("name", "")

            elif event.get("type") == "message_stop":
                break

    # Parse accumulated args_str into args dicts
    parsed_calls = []
    for tc in tool_calls:
        try:
            args = json.loads(tc["args_str"]) if tc["args_str"] else {}
        except json.JSONDecodeError:
            args = {}
        parsed_calls.append({"id": tc["id"], "name": tc["name"], "args": args})

    if parsed_calls:
        return {"type": "tool_calls", "tool_calls": parsed_calls}
    return {"type": "text", "text": "".join(text_parts).strip()}


async def _stream_openai(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    body: dict,
    on_text,
) -> dict:
    """Stream OpenAI SSE, calling on_text(delta) for each text chunk."""
    body["stream"] = True
    text_parts = []
    tool_calls: list[dict] = []

    async with client.stream("POST", url, headers=headers, json=body, timeout=300) as resp:
        await _raise_for_stream_status(resp)
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str == "[DONE]":
                break
            try:
                delta = json.loads(data_str).get("choices", [{}])[0].get("delta", {})
            except json.JSONDecodeError:
                continue

            if delta.get("content"):
                text_parts.append(delta["content"])
                if on_text:
                    on_text(delta["content"])

            for tc_delta in delta.get("tool_calls", []):
                idx = tc_delta.get("index", 0)
                while len(tool_calls) <= idx:
                    tool_calls.append({"id": "", "name": "", "args_str": ""})
                if "id" in tc_delta:
                    tool_calls[idx]["id"] = tc_delta["id"]
                if fn := tc_delta.get("function"):
                    if "name" in fn:
                        tool_calls[idx]["name"] = fn["name"]
                    if "arguments" in fn:
                        tool_calls[idx]["args_str"] += fn["arguments"]

    parsed_calls = []
    for tc in tool_calls:
        try:
            args = json.loads(tc["args_str"]) if tc["args_str"] else {}
        except json.JSONDecodeError:
            args = {}
        parsed_calls.append({"id": tc["id"], "name": tc["name"], "args": args})

    if parsed_calls:
        return {"type": "tool_calls", "tool_calls": parsed_calls}
    return {"type": "text", "text": "".join(text_parts).strip()}


# ── Non-streaming ────────────────────────────────────────────────────────────

async def _nonstream_call(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    body: dict,
    provider: str,
    on_text,
) -> dict:
    """Non-streaming call. Calls on_text with full text if provided."""
    body["stream"] = False
    resp = await client.post(url, headers=headers, json=body, timeout=300)
    resp.raise_for_status()
    data = resp.json()

    if provider == "anthropic":
        result = _parse_anthropic_response(data)
    else:
        result = _parse_openai_response(data)

    if on_text and result["type"] == "text" and result["text"]:
        on_text(result["text"])
    return result


# ── Retry wrapper ────────────────────────────────────────────────────────────

async def _with_retry(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    body: dict,
    provider: str,
    on_text,
    max_retries: int = 4,
) -> dict:
    """Retry on 429 with exponential backoff. Tries streaming first, falls back to non-streaming."""
    for attempt in range(max_retries):
        try:
            return await _stream_anthropic(client, url, headers, dict(body), on_text) if provider == "anthropic" else \
                   await _stream_openai(client, url, headers, dict(body), on_text)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning("Rate limited (429), retrying in %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
                await asyncio.sleep(wait)
                continue
            # On last attempt, try non-streaming
            if attempt == max_retries - 1:
                try:
                    return await _nonstream_call(client, url, headers, dict(body), provider, on_text)
                except Exception:
                    pass
            raise
        except Exception:
            if attempt == max_retries - 1:
                raise
            # Streaming failed — try non-streaming
            try:
                return await _nonstream_call(client, url, headers, dict(body), provider, on_text)
            except Exception:
                if attempt < max_retries - 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
    raise RuntimeError("Rate limited after all retries")


# ── Main interface ───────────────────────────────────────────────────────────

_RETRYABLE_RUNTIME_STATUSES = {429, 500, 502, 503, 504, 529}


def _provider_error_message(status_code: int) -> str:
    if status_code == 429:
        return "Provider rate limited (429). Try again shortly or switch the CMO Brain provider/model."
    return f"Provider error ({status_code})"


def _build_tool_schema_responses(tools: dict) -> list[dict]:
    """Build OpenAI Responses/Codex function tool schemas."""
    result: list[dict] = []
    for name, tool in tools.items():
        properties = {}
        for pname, pdef in tool.get("parameters", {}).items():
            prop: dict[str, Any] = {
                "type": pdef.get("type", "string"),
                "description": pdef.get("description", ""),
            }
            if "enum" in pdef:
                prop["enum"] = pdef["enum"]
            properties[pname] = prop
        result.append({
            "type": "function",
            "name": name,
            "description": tool.get("description", ""),
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": tool.get("required", []),
            },
        })
    return result


def _to_responses_input(messages: list[dict], system_prompt: str) -> tuple[str, list[dict]]:
    """Convert the CMO loop's OpenAI-format transcript to Responses input."""
    instructions: list[str] = [system_prompt] if system_prompt else []
    input_items: list[dict] = []
    for msg in messages:
        role = msg.get("role")
        content = str(msg.get("content") or "")
        if role == "system":
            if content.strip():
                instructions.append(content.strip())
            continue
        if role == "tool":
            input_items.append({
                "type": "function_call_output",
                "call_id": msg.get("tool_call_id") or msg.get("id") or "",
                "output": content,
            })
            continue
        if role == "assistant" and msg.get("tool_calls"):
            if content:
                input_items.append({"role": "assistant", "content": content})
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function", tc)
                args = fn.get("arguments", {})
                if not isinstance(args, str):
                    args = json.dumps(args)
                input_items.append({
                    "type": "function_call",
                    "call_id": tc.get("id") or fn.get("call_id") or "",
                    "name": fn.get("name", ""),
                    "arguments": args,
                })
            continue
        if role in {"user", "assistant"}:
            input_items.append({"role": role, "content": content})
        else:
            input_items.append({"role": "user", "content": content})
    return "\n\n".join(p for p in instructions if p).strip() or "Respond concisely.", input_items


def _parse_responses_function_call(item: dict, pending_args: dict[str, str]) -> dict | None:
    if not isinstance(item, dict) or item.get("type") != "function_call":
        return None
    call_id = str(item.get("call_id") or item.get("id") or "")
    raw_args = item.get("arguments")
    if raw_args is None:
        raw_args = pending_args.get(call_id, "") or pending_args.get(str(item.get("id") or ""), "")
    if not isinstance(raw_args, str):
        raw_args = json.dumps(raw_args or {})
    try:
        args = json.loads(raw_args or "{}")
    except (json.JSONDecodeError, TypeError):
        args = {}
    return {"id": call_id or str(item.get("id") or ""), "name": str(item.get("name") or ""), "args": args}


async def _call_openai_codex_oauth(
    messages: list[dict],
    config: dict,
    tools: dict,
    on_text,
) -> dict:
    """Call OpenAI through the same ChatGPT/Codex OAuth endpoint Admin validates."""
    from providers.openai_codex import _codex_model, _extract_account_id

    api_key = config.get("api_key", "")
    model = _codex_model(config.get("model", ""))
    instructions, input_items = _to_responses_input(messages, config.get("system_prompt", ""))
    headers = {
        "Authorization": f"Bearer {api_key}",
        "chatgpt-account-id": _extract_account_id(api_key),
        "originator": "pi",
        "OpenAI-Beta": "responses=experimental",
        "accept": "text/event-stream",
        "content-type": "application/json",
        "User-Agent": "pi (browser)",
    }
    body: dict[str, Any] = {
        "model": model,
        "store": False,
        "stream": True,
        "input": input_items,
        "instructions": instructions,
        "text": {"verbosity": "low"},
        "include": ["reasoning.encrypted_content"],
        "tool_choice": "auto",
        "parallel_tool_calls": False,
    }
    tool_defs = _build_tool_schema_responses(tools)
    if tool_defs:
        body["tools"] = tool_defs

    text_parts: list[str] = []
    tool_calls: list[dict] = []
    pending_items: dict[str, dict] = {}
    pending_args: dict[str, str] = {}

    async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=30)) as client:
        async with client.stream("POST", "https://chatgpt.com/backend-api/codex/responses", headers=headers, json=body) as resp:
            await _raise_for_stream_status(resp)
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                event_type = data.get("type")
                if event_type == "error":
                    raise RuntimeError(data.get("message") or data.get("code") or json.dumps(data)[:300])
                if event_type == "response.failed":
                    response = data.get("response") if isinstance(data.get("response"), dict) else {}
                    error = response.get("error") if isinstance(response, dict) else None
                    message = error.get("message") if isinstance(error, dict) else None
                    raise RuntimeError(message or json.dumps(data)[:300])
                if event_type == "response.output_text.delta" and isinstance(data.get("delta"), str):
                    text_parts.append(data["delta"])
                    if on_text:
                        on_text(data["delta"])
                    continue
                if event_type == "response.output_text.done" and isinstance(data.get("text"), str) and not text_parts:
                    text_parts.append(data["text"])
                    continue
                if event_type == "response.output_item.added" and isinstance(data.get("item"), dict):
                    item = data["item"]
                    item_id = str(item.get("id") or item.get("call_id") or data.get("output_index") or len(pending_items))
                    pending_items[item_id] = item
                    continue
                if event_type == "response.function_call_arguments.delta":
                    item_id = str(data.get("item_id") or data.get("call_id") or data.get("output_index") or "")
                    if item_id:
                        pending_args[item_id] = pending_args.get(item_id, "") + str(data.get("delta") or "")
                    continue
                if event_type == "response.function_call_arguments.done":
                    item_id = str(data.get("item_id") or data.get("call_id") or data.get("output_index") or "")
                    if item_id:
                        pending_args[item_id] = str(data.get("arguments") or pending_args.get(item_id, ""))
                    continue
                if event_type == "response.output_item.done" and isinstance(data.get("item"), dict):
                    parsed = _parse_responses_function_call(data["item"], pending_args)
                    if parsed:
                        tool_calls.append(parsed)
                    continue
                if event_type in {"message", "response.completed", "response.done", "response.incomplete"}:
                    response = data.get("response") if isinstance(data.get("response"), dict) else data
                    output_items = response.get("output", []) or [] if isinstance(response, dict) else []
                    for item in output_items:
                        parsed = _parse_responses_function_call(item, pending_args)
                        if parsed:
                            tool_calls.append(parsed)

    # Some streams only send argument deltas plus output_item.added. Finalize any
    # pending function-call items that did not receive output_item.done.
    seen_ids = {tc.get("id") for tc in tool_calls}
    for item_id, item in pending_items.items():
        parsed = _parse_responses_function_call(item, {**pending_args, item.get("call_id") or item_id: pending_args.get(item_id, "")})
        if parsed and parsed.get("id") not in seen_ids:
            tool_calls.append(parsed)
            seen_ids.add(parsed.get("id"))

    if tool_calls:
        return {"type": "tool_calls", "tool_calls": tool_calls, "provider": "openai", "model": config.get("model", model)}
    return {"type": "text", "text": "".join(text_parts).strip(), "provider": "openai", "model": config.get("model", model)}


async def _try_runtime_fallbacks(
    messages: list[dict],
    config: dict,
    tools: dict,
    on_text,
    status_code: int,
) -> dict | None:
    fallbacks = list(config.get("fallbacks") or [])
    if not fallbacks or status_code not in _RETRYABLE_RUNTIME_STATUSES:
        return None

    failed_provider = config.get("provider")
    failed_model = config.get("model")
    for fallback in fallbacks:
        fallback_config = dict(fallback)
        fallback_config["system_prompt"] = config.get("system_prompt", "")
        fallback_config.pop("fallbacks", None)
        logger.warning(
            "CMO provider %s/%s failed with HTTP %s; trying fallback %s/%s",
            failed_provider,
            failed_model,
            status_code,
            fallback_config.get("provider"),
            fallback_config.get("model"),
        )
        result = await call_cmo(messages, fallback_config, tools, on_text)
        if result.get("type") != "error":
            result.setdefault("provider", fallback_config.get("provider"))
            result.setdefault("model", fallback_config.get("model"))
            return result
    return None


async def call_cmo(
    messages: list[dict],
    config: dict,
    tools: dict,
    on_text=None,
) -> dict:
    """
    Send one turn to the CMO LLM. Streams by default, falls back to non-streaming.

    Args:
        messages: OpenAI-format message list [{role, content}, ...]
        config: {"provider": "anthropic", "model": "...", "api_key": "...", "system_prompt": "..."}
        tools: {"tool_name": {"description": "...", "parameters": {...}, "required": [...]}}
        on_text: optional callback(text) for real-time text display

    Returns:
        {"type": "text", "text": "..."}
        {"type": "tool_calls", "tool_calls": [{"id": "...", "name": "...", "args": {...}}]}
        {"type": "error", "text": "..."}
    """
    provider = config["provider"]
    if provider == "openai" and config.get("auth_mode") == "oauth":
        oauth_attempts = 3
        for attempt in range(oauth_attempts):
            try:
                return await _call_openai_codex_oauth(messages, config, tools, on_text)
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                if status_code in _RETRYABLE_RUNTIME_STATUSES and attempt < oauth_attempts - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        "CMO OpenAI OAuth provider returned HTTP %s; retrying in %ds (attempt %d/%d)",
                        status_code, wait, attempt + 1, oauth_attempts,
                    )
                    await asyncio.sleep(wait)
                    continue
                preview = await _response_error_preview(e.response)
                logger.error("CMO OpenAI OAuth provider error %s: %s", status_code, preview)
                fallback_result = await _try_runtime_fallbacks(messages, config, tools, on_text, status_code)
                if fallback_result:
                    return fallback_result
                return {"type": "error", "text": _provider_error_message(status_code)}
            except Exception as e:
                logger.error("CMO OpenAI OAuth provider exception: %s", e)
                return {"type": "error", "text": str(e)}

    cfg = PROVIDERS.get(provider)
    if not cfg:
        return {"type": "error", "text": f"Unknown provider: {provider}"}

    api_key = config.get("api_key", "")
    model = config.get("model", "")
    system_prompt = config.get("system_prompt", "")

    # Build headers
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if cfg.get("header_prefix"):
        headers[cfg["header_key"]] = f"{cfg['header_prefix']}{api_key}"
    else:
        headers[cfg["header_key"]] = api_key
    if cfg.get("header_version"):
        headers[cfg["header_version"]] = cfg["version_value"]
    for k, v in cfg.get("extra_headers", {}).items():
        headers[k] = v

    # Build body
    if provider == "anthropic":
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": config.get("max_tokens", 4096),
            "system": system_prompt,
            "messages": _to_anthropic_messages(messages),
            "tools": _build_tool_schema_anthropic(tools),
        }
    else:
        body = {
            "model": model,
            "max_tokens": config.get("max_tokens", 4096),
            "messages": _to_openai_messages(messages, system_prompt),
            "tools": _build_tool_schema_openai(tools),
            "tool_choice": "auto",
            "parallel_tool_calls": False,
        }

    url = cfg["base_url"]

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=30)) as client:
            result = await _with_retry(client, url, headers, body, provider, on_text)
            if result.get("type") != "error":
                result.setdefault("provider", provider)
                result.setdefault("model", model)
            return result
    except httpx.HTTPStatusError as e:
        preview = await _response_error_preview(e.response)
        logger.error("CMO provider error %s: %s", e.response.status_code, preview)
        fallback_result = await _try_runtime_fallbacks(messages, config, tools, on_text, e.response.status_code)
        if fallback_result:
            return fallback_result
        return {"type": "error", "text": _provider_error_message(e.response.status_code)}
    except Exception as e:
        logger.error("CMO provider exception: %s", e)
        return {"type": "error", "text": str(e)}
