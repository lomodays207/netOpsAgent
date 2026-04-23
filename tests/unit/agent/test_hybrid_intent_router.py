from types import SimpleNamespace

import pytest

from src.agent.hybrid_intent_router import HybridIntentRouter
from src.agent.intent_types import IntentDecision, RuleIntentResult


def make_session(
    status="completed",
    source="general_chat",
    target="general_chat",
    messages=None,
):
    task = SimpleNamespace(source=source, target=target)
    return SimpleNamespace(status=status, task=task, messages=messages or [])


def make_rule_result(
    route="general_chat",
    confidence=0.78,
    reason="general_network_question",
    certainty="soft",
    clarify_message=None,
    signals=None,
):
    return RuleIntentResult(
        route=route,
        confidence=confidence,
        reason=reason,
        certainty=certainty,
        clarify_message=clarify_message,
        signals=signals or {},
    )


class FakeRuleRouter:
    def __init__(self, rule_result):
        self.rule_result = rule_result
        self.calls = []

    def classify(self, message, session=None):
        self.calls.append((message, session))
        return self.rule_result


class FakeLLMClassifier:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def classify(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_hard_rule_result_bypasses_llm():
    rule_result = make_rule_result(
        route="start_diagnosis",
        confidence=0.92,
        reason="structured_diagnosis_request",
        certainty="hard",
        signals={"has_pair": True},
    )
    rule_router = FakeRuleRouter(rule_result)
    llm_classifier = FakeLLMClassifier(
        IntentDecision(
            route="general_chat",
            confidence=0.99,
            reason="should_not_be_used",
        )
    )
    router = HybridIntentRouter(rule_router=rule_router, llm_classifier=llm_classifier)

    decision = router.route_message("web-01 db-01 connection failed")

    assert decision.route == "start_diagnosis"
    assert decision.reason == "structured_diagnosis_request"
    assert rule_router.calls == [("web-01 db-01 connection failed", None)]
    assert llm_classifier.calls == []


def test_low_confidence_llm_result_falls_back_to_rule():
    rule_result = make_rule_result(
        route="general_chat",
        confidence=0.78,
        reason="general_network_question",
        certainty="soft",
        clarify_message=None,
        signals={"has_question_style": True},
    )
    rule_router = FakeRuleRouter(rule_result)
    llm_classifier = FakeLLMClassifier(
        IntentDecision(
            route="general_chat",
            confidence=0.55,
            reason="llm_low_confidence",
            clarify_message="llm_clarify",
        )
    )
    router = HybridIntentRouter(rule_router=rule_router, llm_classifier=llm_classifier)

    decision = router.route_message("how do I check port 3306?")

    assert decision.route == "general_chat"
    assert decision.reason == "general_network_question"
    assert decision.confidence == 0.78
    assert llm_classifier.calls[0]["rule_result"] is rule_result


def test_conservative_merge_prefers_clarify_over_diagnosis_without_pair():
    rule_result = make_rule_result(
        route="clarify",
        confidence=0.82,
        reason="issue_report_without_enough_details",
        certainty="soft",
        clarify_message="Please provide source, target, and port.",
        signals={"has_pair": False, "has_failure": True, "has_question_style": False},
    )
    rule_router = FakeRuleRouter(rule_result)
    llm_classifier = FakeLLMClassifier(
        IntentDecision(
            route="start_diagnosis",
            confidence=0.97,
            reason="llm_pushes_diagnosis",
        )
    )
    router = HybridIntentRouter(rule_router=rule_router, llm_classifier=llm_classifier)

    decision = router.route_message("the service is down")

    assert decision.route == "clarify"
    assert decision.reason == "issue_report_without_enough_details"
    assert decision.clarify_message == "Please provide source, target, and port."

