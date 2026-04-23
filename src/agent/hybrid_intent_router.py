"""Hybrid intent routing that merges rule and LLM decisions."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from .intent_types import IntentDecision, RuleIntentResult
from .llm_intent_router import LLMIntentClassificationError, LLMIntentClassifier
from .rule_intent_router import RuleIntentRouter


logger = logging.getLogger(__name__)


class HybridIntentRouter:
    """Route using rules first, then optionally refine with an LLM."""

    def __init__(
        self,
        rule_router: Optional[RuleIntentRouter] = None,
        llm_classifier: Optional[LLMIntentClassifier] = None,
        min_confidence: float = 0.80,
        diagnosis_min_confidence: float = 0.85,
        log_decisions: bool = False,
    ) -> None:
        self.rule_router = rule_router or RuleIntentRouter()
        self.llm_classifier = llm_classifier
        self.min_confidence = min_confidence
        self.diagnosis_min_confidence = diagnosis_min_confidence
        self.log_decisions = log_decisions

    def route_message(self, message: str, session: Optional[Any] = None) -> IntentDecision:
        rule_result = self.rule_router.classify(message, session=session)

        if rule_result.certainty == "hard":
            final_decision = rule_result.to_decision()
            self._log_decision(message, rule_result, None, final_decision, None)
            return final_decision

        if self.llm_classifier is None:
            final_decision = rule_result.to_decision()
            self._log_decision(message, rule_result, None, final_decision, "no_llm_classifier")
            return final_decision

        try:
            llm_result = self.llm_classifier.classify(
                message=message,
                session=session,
                recent_messages=self._recent_messages(session),
                rule_result=rule_result,
            )
        except LLMIntentClassificationError:
            final_decision = rule_result.to_decision()
            self._log_decision(
                message,
                rule_result,
                None,
                final_decision,
                "llm_classification_error",
            )
            return final_decision
        except Exception:
            final_decision = rule_result.to_decision()
            self._log_decision(
                message,
                rule_result,
                None,
                final_decision,
                "llm_classification_unexpected_error",
            )
            return final_decision

        final_decision, fallback_reason = self._merge(rule_result, llm_result)
        self._log_decision(message, rule_result, llm_result, final_decision, fallback_reason)
        return final_decision

    def _merge(
        self,
        rule_result: RuleIntentResult,
        llm_result: Any,
    ) -> tuple[IntentDecision, Optional[str]]:
        llm_route = getattr(llm_result, "route", None)
        llm_confidence = float(getattr(llm_result, "confidence", 0.0) or 0.0)

        threshold = (
            self.diagnosis_min_confidence
            if llm_route in {"start_diagnosis", "continue_diagnosis"}
            else self.min_confidence
        )

        if llm_confidence < threshold:
            return rule_result.to_decision(), "llm_below_threshold"

        if llm_route == "start_diagnosis":
            if not rule_result.signals.get("has_pair"):
                return self._clarify_decision(rule_result), "missing_pair"
            if rule_result.route == "clarify":
                return rule_result.to_decision(), "rule_prefers_clarify"
            if rule_result.route == "general_chat":
                if rule_result.signals.get("has_question_style"):
                    return rule_result.to_decision(), "general_chat_question_style"
                return self._clarify_decision(rule_result), "general_chat_needs_clarify"

        if rule_result.route == "clarify" and llm_route == "general_chat" and rule_result.signals.get("has_failure"):
            return rule_result.to_decision(), "failure_signal_keeps_clarify"

        if llm_route == "continue_diagnosis" and rule_result.route == "clarify":
            return rule_result.to_decision(), "rule_prefers_clarify"

        return self._decision_from_llm(llm_result), None

    def _decision_from_llm(self, llm_result: Any) -> IntentDecision:
        return IntentDecision(
            route=getattr(llm_result, "route", "general_chat"),
            confidence=float(getattr(llm_result, "confidence", 0.0) or 0.0),
            reason=getattr(llm_result, "reason", ""),
            clarify_message=getattr(llm_result, "clarify_message", None),
        )

    def _clarify_decision(self, rule_result: RuleIntentResult) -> IntentDecision:
        clarify_message = rule_result.clarify_message or (
            "Please provide the source host, target host, and the failure symptom or port/service involved."
        )
        return IntentDecision(
            route="clarify",
            confidence=rule_result.confidence,
            reason=rule_result.reason,
            clarify_message=clarify_message,
        )

    def _recent_messages(self, session: Optional[Any]) -> list[dict[str, Any]]:
        if not session or not hasattr(session, "messages"):
            return []

        recent_messages = getattr(session, "messages", None) or []
        output: list[dict[str, Any]] = []
        for message in recent_messages[-5:]:
            if isinstance(message, dict):
                output.append(
                    {
                        "role": message.get("role"),
                        "content": message.get("content"),
                    }
                )
            else:
                output.append(
                    {
                        "role": getattr(message, "role", None),
                        "content": getattr(message, "content", None),
                    }
                )
        return output

    def _log_decision(
        self,
        message: str,
        rule_result: RuleIntentResult,
        llm_result: Any,
        final_decision: IntentDecision,
        fallback_reason: Optional[str],
    ) -> None:
        if not self.log_decisions:
            return

        log_payload = {
            "message": message,
            "rule": {
                "route": rule_result.route,
                "certainty": rule_result.certainty,
                "reason": rule_result.reason,
            },
            "llm": None
            if llm_result is None
            else {
                "route": getattr(llm_result, "route", None),
                "confidence": getattr(llm_result, "confidence", None),
                "reason": getattr(llm_result, "reason", None),
            },
            "final_route": final_decision.route,
            "fallback_reason": fallback_reason,
        }
        logger.info(json.dumps(log_payload, ensure_ascii=False))

