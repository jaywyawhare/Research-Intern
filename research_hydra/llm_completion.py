from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from collections.abc import Callable
from typing import Any

import certifi
import httpx

logger = logging.getLogger(__name__)

_LLM_RPM_LOCK = asyncio.Lock()
_LLM_LAST_START_MONO: list[float] = [0.0]


def _env_truthy(name: str) -> bool:
    v = os.environ.get(name, "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _resolve_api_key(explicit: str | None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    for k in ("OPENAI_API_KEY", "NVIDIA_API_KEY"):
        v = os.environ.get(k, "").strip()
        if v:
            return v
    return ""


def _optional_float(env_name: str, override: float | None) -> float | None:
    if override is not None:
        return override
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        logger.warning("Ignoring invalid %s=%r", env_name, raw)
        return None


def _optional_int(env_name: str, override: int | None) -> int | None:
    if override is not None:
        return override
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        return None
    try:
        return int(raw, 10)
    except ValueError:
        logger.warning("Ignoring invalid %s=%r", env_name, raw)
        return None


def _extra_body(override: dict[str, Any] | None) -> dict[str, Any]:
    raw = os.environ.get("OPENAI_EXTRA_BODY", "").strip()
    merged: dict[str, Any] = {}
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"OPENAI_EXTRA_BODY must be JSON: {e}") from e
        if not isinstance(parsed, dict):
            raise ValueError("OPENAI_EXTRA_BODY must be a JSON object")
        merged.update(parsed)
    if override:
        merged.update(override)
    return merged


def _openai_settings(
    *,
    api_key: str | None,
    model: str | None,
    base_url: str | None,
    temperature: float | None,
    top_p: float | None,
    max_tokens: int | None,
    timeout: float | None,
) -> tuple[str, str, str, float, float | None, int | None, float]:
    key = _resolve_api_key(api_key)
    m = (model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"
    base = (base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")).strip().rstrip("/")
    temp_raw = os.environ.get("OPENAI_TEMPERATURE", "").strip()
    if temperature is not None:
        temp = float(temperature)
    elif temp_raw:
        try:
            temp = float(temp_raw)
        except ValueError:
            temp = 0.3
    else:
        temp = 0.3
    tp = _optional_float("OPENAI_TOP_P", top_p)
    mt = _optional_int("OPENAI_MAX_TOKENS", max_tokens)
    to = timeout
    if to is None:
        tr = os.environ.get("OPENAI_TIMEOUT", "").strip()
        to = float(tr) if tr else 300.0
    return key, m, base, temp, tp, mt, float(to)


async def _throttle_openai_rpm() -> None:
    raw = os.environ.get("OPENAI_MAX_RPM", "").strip()
    if not raw:
        return
    try:
        rpm = float(raw)
    except ValueError:
        logger.warning("Ignoring invalid OPENAI_MAX_RPM=%r", raw)
        return
    if rpm <= 0:
        return
    interval = 60.0 / rpm
    async with _LLM_RPM_LOCK:
        now = time.monotonic()
        wait = interval - (now - _LLM_LAST_START_MONO[0])
        if wait > 0:
            await asyncio.sleep(wait)
        _LLM_LAST_START_MONO[0] = time.monotonic()


def _build_payload(
    model: str,
    prompt: str,
    temperature: float,
    top_p: float | None,
    max_tokens: int | None,
    extra: dict[str, Any],
    *,
    stream: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if top_p is not None:
        payload["top_p"] = top_p
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if stream:
        payload["stream"] = True
    for k, v in extra.items():
        if k in ("model", "messages"):
            continue
        payload[k] = v
    return payload


def _message_text(msg: dict[str, Any]) -> str:
    reasoning = msg.get("reasoning_content")
    content = msg.get("content")
    parts: list[str] = []
    if isinstance(reasoning, str) and reasoning.strip():
        parts.append(reasoning.strip())
    if isinstance(content, str) and content.strip():
        parts.append(content.strip())
    if parts:
        return "\n\n".join(parts)
    return ""


async def _complete_non_stream(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> str:
    r = await client.post(url, headers=headers, content=json.dumps(payload))
    if r.status_code >= 400:
        body = (r.text or "")[:500]
        logger.error("OpenAI-compatible API %s: %s", r.status_code, body)
        raise RuntimeError(f"LLM HTTP {r.status_code}: {body}")
    data = r.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("LLM response missing choices")
    c0 = choices[0] if isinstance(choices[0], dict) else {}
    msg = c0.get("message") if isinstance(c0.get("message"), dict) else {}
    text = _message_text(msg)
    if text:
        return text
    raise RuntimeError("LLM response missing message content")


async def _complete_stream(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    stream_sink: Callable[[str], None] | None,
) -> str:
    out: list[str] = []
    async with client.stream("POST", url, headers=headers, content=json.dumps(payload)) as r:
        if r.status_code >= 400:
            body = (await r.aread())[:500]
            t = body.decode("utf-8", errors="replace")
            logger.error("OpenAI-compatible API %s: %s", r.status_code, t)
            raise RuntimeError(f"LLM HTTP {r.status_code}: {t}")
        async for line in r.aiter_lines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            for choice in obj.get("choices") or []:
                if not isinstance(choice, dict):
                    continue
                delta = choice.get("delta")
                if not isinstance(delta, dict):
                    continue
                rc = delta.get("reasoning_content")
                if isinstance(rc, str) and rc:
                    out.append(rc)
                    if stream_sink:
                        stream_sink(rc)
                c = delta.get("content")
                if isinstance(c, str) and c:
                    out.append(c)
                    if stream_sink:
                        stream_sink(c)
    joined = "".join(out).strip()
    if not joined:
        raise RuntimeError("Empty streamed LLM response")
    return joined


async def run_analysis_completion(
    prompt: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    max_tokens: int | None = None,
    extra_body: dict[str, Any] | None = None,
    stream: bool | None = None,
    stream_sink: Callable[[str], None] | None = None,
    timeout: float | None = None,
) -> str:
    """
    Send ``prompt`` as a single user message; return assistant text (and optional reasoning).

    Uses ``OPENAI_API_KEY`` or ``NVIDIA_API_KEY`` (or ``api_key``), optional ``OPENAI_MODEL``,
    ``OPENAI_BASE_URL``, ``OPENAI_TOP_P``, ``OPENAI_MAX_TOKENS``, ``OPENAI_EXTRA_BODY`` (JSON
    object merged into the request body for providers like NVIDIA NIM), ``OPENAI_STREAM``,
    and ``OPENAI_MAX_RPM`` (spaces request starts, e.g. ``30`` for a 30 RPM tier).

    When ``stream`` is true, ``stream_sink`` receives token chunks as they arrive (e.g. print
    to stderr); the full concatenation is still returned.
    """
    if stream is None:
        stream = _env_truthy("OPENAI_STREAM")

    key, m, base, temp, tp, mt, to = _openai_settings(
        api_key=api_key,
        model=model,
        base_url=base_url,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    if not key:
        raise ValueError("Missing OPENAI_API_KEY / NVIDIA_API_KEY (or pass api_key=) for LLM completion")

    extra = _extra_body(extra_body)
    url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    await _throttle_openai_rpm()

    if stream and stream_sink is None:

        def stream_sink(s: str) -> None:
            sys.stderr.write(s)
            sys.stderr.flush()

    pl = _build_payload(m, prompt, temp, tp, mt, extra, stream=stream)

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(to),
        verify=certifi.where(),
        follow_redirects=True,
    ) as client:
        if stream:
            return await _complete_stream(client, url, headers, pl, stream_sink)
        return await _complete_non_stream(client, url, headers, pl)
