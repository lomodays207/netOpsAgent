"""Hybrid intent routing that merges rule and LLM decisions."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from .intent_types import IntentDecision, RuleIntentResult
from .llm_intent_router import LLMIntentClassificationError, LLMIntentClassifier
from .rule_intent_router import RuleIntentRouter


logger = logging.getLogger(__name__)
MESSAGE_PREVIEW_LIMIT = 120
MAX_DECISION_REASON_CHARS = 200
MAX_DECISION_CLARIFY_MESSAGE_CHARS = 500


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

        if llm_route == "continue_diagnosis":
            if not rule_result.signals.get("is_diagnostic_session"):
                return rule_result.to_decision(), "non_diagnostic_session"
            return self._decision_from_llm(llm_result), None

        if llm_route == "start_diagnosis":
            if not rule_result.signals.get("has_pair"):
                return self._clarify_decision(rule_result), "missing_pair"
            if not self._has_start_diagnosis_signal(rule_result):
                return rule_result.to_decision(), "missing_start_signal"
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

    def _has_start_diagnosis_signal(self, rule_result: RuleIntentResult) -> bool:
        signals = rule_result.signals
        return any(
            signals.get(name)
            for name in (
                "has_failure",
                "has_tool_cmd",
                "has_actionable",
                "has_ip",
                "has_port_or_service",
            )
        )

    def _decision_from_llm(self, llm_result: Any) -> IntentDecision:
        return IntentDecision(
            route=getattr(llm_result, "route", "general_chat"),
            confidence=float(getattr(llm_result, "confidence", 0.0) or 0.0),
            reason=self._truncate_text(
                getattr(llm_result, "reason", ""),
                MAX_DECISION_REASON_CHARS,
            ),
            clarify_message=self._truncate_optional_text(
                getattr(llm_result, "clarify_message", None),
                MAX_DECISION_CLARIFY_MESSAGE_CHARS,
            ),
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

        rule_reason = self._preview_field(rule_result.reason)
        llm_reason = self._preview_field(getattr(llm_result, "reason", None))
        log_payload = {
            "message_preview": self._preview_message(message),
            "message_length": len("" if message is None else str(message)),
            "rule": {
                "route": rule_result.route,
                "certainty": rule_result.certainty,
                "reason_preview": rule_reason["preview"],
                "reason_length": rule_reason["length"],
            },
            "llm": None
            if llm_result is None
            else {
                "route": getattr(llm_result, "route", None),
                "confidence": getattr(llm_result, "confidence", None),
                "reason_preview": llm_reason["preview"],
                "reason_length": llm_reason["length"],
            },
            "final_route": final_decision.route,
            "fallback_reason": fallback_reason,
        }
        logger.info(json.dumps(log_payload, ensure_ascii=False))

    def _preview_message(self, message: Any) -> str:
        text = "" if message is None else str(message)
        return text[:MESSAGE_PREVIEW_LIMIT]

    def _preview_field(self, value: Any) -> dict[str, Any]:
        text = "" if value is None else str(value)
        return {
            "preview": text[:MESSAGE_PREVIEW_LIMIT],
            "length": len(text),
        }

    def _truncate_text(self, value: Any, max_chars: int) -> str:
        text = "" if value is None else str(value)
        return text[:max_chars]

    def _truncate_optional_text(self, value: Any, max_chars: int) -> Optional[str]:
        if value is None:
            return None
        return self._truncate_text(value, max_chars)
