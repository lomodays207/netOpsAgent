import json
from types import SimpleNamespace

import pytest

from src.agent.hybrid_intent_router import HybridIntentRouter
from src.agent.llm_intent_router import LLMIntentClassifier
from src.agent.intent_types import LLMIntentResult
from src.agent.rule_intent_router import RuleIntentRouter


def make_session(status="completed", source="general_chat", target="general_chat", messages=None):
    task = SimpleNamespace(source=source, target=target)
    return SimpleNamespace(status=status, task=task, messages=messages or [])


class MappingLLMClient:
    def __init__(self, responder):
        self.responder = responder
        self.calls = []

    def invoke_with_json(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.responder, Exception):
            raise self.responder
        if callable(self.responder):
            return self.responder(kwargs)
        return self.responder


def make_classifier(responder):
    return LLMIntentClassifier(llm_client=MappingLLMClient(responder))


class RecordingLLMClassifier:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def classify(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def _json_response(route, confidence=0.91, reason="llm_reinforces_rule"):
    return json.dumps(
        {
            "route": route,
            "confidence": confidence,
            "reason": reason,
        },
        ensure_ascii=False,
    )


@pytest.mark.parametrize(
    "message,session,llm_responder,expected_route,expected_reason,expected_llm_calls",
    [
        (
            "web-01到db-01端口3306连接失败",
            None,
            AssertionError("LLM should not be called for hard-rule diagnosis"),
            "start_diagnosis",
            "structured_diagnosis_request",
            0,
        ),
        (
            "端口不通怎么排查",
            None,
            lambda _: _json_response(
                "general_chat",
                confidence=0.93,
                reason="reinforce_method_question",
            ),
            "general_chat",
            "reinforce_method_question",
            1,
        ),
        (
            "我现在访问不通",
            None,
            lambda _: _json_response(
                "general_chat",
                confidence=0.93,
                reason="llm_cannot_override_clarify",
            ),
            "clarify",
            "issue_report_without_enough_details",
            1,
        ),
        (
            "N-CRM和N-OA之间有哪些访问关系",
            None,
            AssertionError("LLM should not be called for access relation queries"),
            "general_chat",
            "access_relation_query",
            0,
        ),
        (
            "请帮我查询 XX 系统到 XX 系统之间是否已经开通访问关系。",
            None,
            AssertionError("LLM should not be called for access relation status queries"),
            "general_chat",
            "access_relation_query",
            0,
        ),
        (
            "访问关系如何开权限",
            None,
            lambda _: _json_response(
                "general_chat",
                confidence=0.94,
                reason="knowledge_method_question",
            ),
            "general_chat",
            "knowledge_method_question",
            1,
        ),
        (
            "访问关系如何进行开通提单？需要哪些权限、审批节点和必填信息？",
            None,
            lambda _: _json_response(
                "general_chat",
                confidence=0.94,
                reason="process_question",
            ),
            "general_chat",
            "process_question",
            1,
        ),
        (
            "目标机器上有防火墙",
            make_session(status="waiting_user", source="general_chat", target="general_chat"),
            AssertionError("LLM should not be called for waiting-user sessions"),
            "continue_diagnosis",
            "session_waiting_user",
            0,
        ),
    ],
)
def test_intent_routing_sample_matrix(
    message,
    session,
    llm_responder,
    expected_route,
    expected_reason,
    expected_llm_calls,
):
    router = HybridIntentRouter(
        rule_router=RuleIntentRouter(),
        llm_classifier=make_classifier(llm_responder),
    )

    decision = router.route_message(message, session=session)

    assert decision.route == expected_route
    assert decision.reason == expected_reason
    llm_client = router.llm_classifier.llm_client
    assert len(llm_client.calls) == expected_llm_calls


def test_recent_messages_are_bounded_and_dict_safe_for_llm_prompt():
    recent_messages = [
        {"role": "user", "content": f"message-{index}"} for index in range(7)
    ]
    llm_classifier = RecordingLLMClassifier(
        LLMIntentResult(
            route="general_chat",
            confidence=0.9,
            reason="ok",
        )
    )
    router = HybridIntentRouter(
        rule_router=RuleIntentRouter(),
        llm_classifier=llm_classifier,
    )
    session = make_session(messages=recent_messages)

    router.route_message("端口不通怎么排查", session=session)

    assert len(llm_classifier.calls) == 1
    assert len(llm_classifier.calls[0]["recent_messages"]) == 5
    assert llm_classifier.calls[0]["recent_messages"][0]["content"] == "message-2"
    assert llm_classifier.calls[0]["recent_messages"][-1]["content"] == "message-6"
