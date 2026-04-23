"""Shared intent routing result types."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class IntentDecision:
    route: str
    confidence: float
    reason: str
    clarify_message: Optional[str] = None


@dataclass
class RuleIntentResult:
    route: str
    confidence: float
    reason: str
    certainty: str
    clarify_message: Optional[str] = None
    signals: Dict[str, Any] = field(default_factory=dict)

    def to_decision(self) -> IntentDecision:
        return IntentDecision(
            route=self.route,
            confidence=self.confidence,
            reason=self.reason,
            clarify_message=self.clarify_message,
        )


@dataclass
class LLMIntentResult:
    route: str
    confidence: float
    reason: str
    clarify_message: Optional[str] = None
    needs_more_detail: bool = False
    detected_signals: Dict[str, Any] = field(default_factory=dict)

    def to_decision(self) -> IntentDecision:
        return IntentDecision(
            route=self.route,
            confidence=self.confidence,
            reason=self.reason,
            clarify_message=self.clarify_message,
        )
