"""Backward-compatible facade and factory for intent routing."""

from __future__ import annotations

import os
import math
from typing import Optional

from .intent_types import IntentDecision, LLMIntentResult, RuleIntentResult
from .rule_intent_router import RuleIntentRouter

IntentRouter = RuleIntentRouter


def _parse_bool_env(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default

    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        return default

    return value


def _create_default_llm_client():
    from ..integrations.llm_client import LLMClient

    return LLMClient()


def build_intent_router(llm_client=None):
    mode = (os.getenv("INTENT_ROUTER_MODE") or "rule").strip().lower()
    if mode != "hybrid":
        return RuleIntentRouter()

    try:
        from .hybrid_intent_router import HybridIntentRouter
        from .llm_intent_router import LLMIntentClassifier

        client = llm_client if llm_client is not None else _create_default_llm_client()
        classifier = LLMIntentClassifier(llm_client=client)
        return HybridIntentRouter(
            rule_router=RuleIntentRouter(),
            llm_classifier=classifier,
            min_confidence=_parse_float_env("INTENT_LLM_MIN_CONFIDENCE", 0.80),
            diagnosis_min_confidence=_parse_float_env(
                "INTENT_LLM_DIAGNOSIS_MIN_CONFIDENCE",
                0.85,
            ),
            log_decisions=_parse_bool_env(os.getenv("INTENT_LOG_DECISIONS"), False),
        )
    except Exception:
        return RuleIntentRouter()


__all__ = [
    "IntentDecision",
    "RuleIntentResult",
    "LLMIntentResult",
    "RuleIntentRouter",
    "IntentRouter",
    "build_intent_router",
]
