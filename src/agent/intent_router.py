"""Backward-compatible facade for intent routing."""

from .intent_types import IntentDecision, LLMIntentResult, RuleIntentResult
from .rule_intent_router import RuleIntentRouter

IntentRouter = RuleIntentRouter

__all__ = [
    "IntentDecision",
    "RuleIntentResult",
    "LLMIntentResult",
    "RuleIntentRouter",
    "IntentRouter",
]
