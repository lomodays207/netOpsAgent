"""Utility helpers for tracing."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from .constants import REDACTED_VALUE, TRUNCATED_SUFFIX

_SENSITIVE_KEYWORDS = (
    "password",
    "passwd",
    "secret",
    "token",
    "apikey",
    "api_key",
    "accesskey",
    "access_key",
    "privatekey",
    "private_key",
    "credential",
    "credentials",
)


def build_trace_id(now: datetime | None = None) -> str:
    current = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
    return f"trace_{current.strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _is_sensitive_key(key: str) -> bool:
    normalized = _normalize_key(key)
    return any(keyword in normalized for keyword in _SENSITIVE_KEYWORDS)


def mask_sensitive_data(payload: Any) -> Any:
    if isinstance(payload, dict):
        masked: dict[str, Any] = {}
        for key, value in payload.items():
            if _is_sensitive_key(str(key)):
                masked[key] = REDACTED_VALUE
            else:
                masked[key] = mask_sensitive_data(value)
        return masked
    if isinstance(payload, list):
        return [mask_sensitive_data(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(mask_sensitive_data(item) for item in payload)
    return payload


def _truncate_bytes(content: str, max_bytes: int) -> str:
    encoded = content.encode("utf-8")
    if len(encoded) <= max_bytes:
        return content

    suffix = TRUNCATED_SUFFIX.encode("utf-8")
    if len(suffix) >= max_bytes:
        return suffix[:max_bytes].decode("utf-8", errors="ignore")

    truncated = encoded[: max_bytes - len(suffix)]
    while truncated:
        try:
            prefix = truncated.decode("utf-8")
            return prefix + TRUNCATED_SUFFIX
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    return TRUNCATED_SUFFIX[:max_bytes]


def truncate_text(content: Any, max_bytes: int) -> str:
    if content is None:
        return ""
    return _truncate_bytes(str(content), max_bytes=max_bytes)


def truncate_json_payload(payload: Any, max_bytes: int) -> str:
    if payload is None:
        return "{}"
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return _truncate_bytes(serialized, max_bytes=max_bytes)


def calculate_total_time(started_at: datetime | None, completed_at: datetime | None) -> float | None:
    if not started_at or not completed_at:
        return None
    return round((completed_at - started_at).total_seconds(), 2)
