import json

import pytest

from src.agent.intent_types import RuleIntentResult
from src.agent.llm_intent_router import (
    LLMIntentClassificationError,
    LLMIntentClassifier,
)


class FakeLLMClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def invoke_with_json(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def make_rule_result():
    return RuleIntentResult(
        route="general_chat",
        confidence=0.78,
        reason="general_network_question",
        certainty="soft",
        signals={"has_question_style": True},
    )


def test_classify_valid_json_returns_llm_intent_result():
    llm_client = FakeLLMClient(
        """{
            "route": "general_chat",
            "confidence": 0.88,
            "reason": "question_style_general_network_topic",
            "detected_signals": {"has_question_style": true}
        }"""
    )
    classifier = LLMIntentClassifier(llm_client=llm_client, temperature=0.0)

    result = classifier.classify(
        message="端口不通怎么排查？",
        session=None,
        recent_messages=[
            {"role": "user", "content": "old-1"},
            {"role": "assistant", "content": "old-2"},
            {"role": "user", "content": "old-3"},
            {"role": "assistant", "content": "old-4"},
            {"role": "user", "content": "old-5"},
            {"role": "assistant", "content": "old-6"},
        ],
        rule_result=make_rule_result(),
    )

    assert result.route == "general_chat"
    assert result.confidence == 0.88
    assert result.detected_signals["has_question_style"] is True
    assert llm_client.calls[0]["temperature"] == 0.0

    prompt = json.loads(llm_client.calls[0]["prompt"])
    assert prompt["required_output_keys"] == ["route", "confidence", "reason"]
    assert prompt["optional_output_keys"] == [
        "clarify_message",
        "needs_more_detail",
        "detected_signals",
    ]
    assert "old-1" not in llm_client.calls[0]["prompt"]
    assert "old-2" in llm_client.calls[0]["prompt"]


def test_classify_invalid_json_raises_classification_error():
    classifier = LLMIntentClassifier(llm_client=FakeLLMClient("not json"))

    with pytest.raises(LLMIntentClassificationError):
        classifier.classify(
            message="端口不通怎么排查？",
            session=None,
            recent_messages=[],
            rule_result=make_rule_result(),
        )


def test_classify_llm_client_exception_raises_classification_error():
    classifier = LLMIntentClassifier(llm_client=FakeLLMClient(RuntimeError("boom")))

    with pytest.raises(LLMIntentClassificationError):
        classifier.classify(
            message="端口不通怎么排查？",
            session=None,
            recent_messages=[],
            rule_result=make_rule_result(),
        )


def test_classify_non_string_response_raises_classification_error():
    classifier = LLMIntentClassifier(llm_client=FakeLLMClient({"route": "general_chat"}))

    with pytest.raises(LLMIntentClassificationError):
        classifier.classify(
            message="端口不通怎么排查？",
            session=None,
            recent_messages=[],
            rule_result=make_rule_result(),
        )


def test_classify_unknown_route_raises_classification_error():
    llm_client = FakeLLMClient(
        """{
            "route": "diagnose_now",
            "confidence": 0.88,
            "reason": "unknown_route"
        }"""
    )
    classifier = LLMIntentClassifier(llm_client=llm_client)

    with pytest.raises(LLMIntentClassificationError):
        classifier.classify(
            message="端口不通怎么排查？",
            session=None,
            recent_messages=[],
            rule_result=make_rule_result(),
        )


@pytest.mark.parametrize(
    "response",
    [
        """{
            "route": "general_chat",
            "confidence": "0.88",
            "reason": "confidence_string"
        }""",
        """{
            "route": "general_chat",
            "confidence": true,
            "reason": "confidence_boolean"
        }""",
        """{
            "route": "general_chat",
            "confidence": 0.88,
            "reason": "needs_more_detail_string",
            "needs_more_detail": "yes"
        }""",
        """{
            "route": "general_chat",
            "confidence": 0.88,
            "reason": "extra_key",
            "unexpected": "value"
        }""",
    ],
)
def test_classify_malformed_payload_raises_classification_error(response):
    classifier = LLMIntentClassifier(llm_client=FakeLLMClient(response))

    with pytest.raises(LLMIntentClassificationError):
        classifier.classify(
            message="端口不通怎么排查？",
            session=None,
            recent_messages=[],
            rule_result=make_rule_result(),
        )


def test_build_prompt_truncates_current_and_recent_message_content():
    llm_client = FakeLLMClient(
        """{
            "route": "general_chat",
            "confidence": 0.88,
            "reason": "question_style_general_network_topic"
        }"""
    )
    classifier = LLMIntentClassifier(llm_client=llm_client)
    long_current = "m" * 1001
    long_recent = "r" * 501

    classifier.classify(
        message=long_current,
        session=None,
        recent_messages=[{"role": "user", "content": long_recent}],
        rule_result=make_rule_result(),
    )

    prompt = json.loads(llm_client.calls[0]["prompt"])
    assert prompt["message"] == "m" * 1000
    assert prompt["recent_messages"][0]["content"] == "r" * 500


def test_build_prompt_truncates_rule_result_signal_string_values():
    llm_client = FakeLLMClient(
        """{
            "route": "general_chat",
            "confidence": 0.88,
            "reason": "bounded_signals"
        }"""
    )
    classifier = LLMIntentClassifier(llm_client=llm_client)
    rule_result = RuleIntentResult(
        route="general_chat",
        confidence=0.78,
        reason="general_network_question",
        certainty="soft",
        signals={
            "source": "s" * 1001,
            "target": "t" * 1001,
            "nested": {"raw": "x" * 1001},
            "items": ["y" * 1001, 42, True],
            "tuple_items": ("z" * 1001,),
            "has_question_style": True,
            "score": 0.5,
        },
    )

    classifier.classify(
        message="端口不通怎么排查？",
        session=None,
        recent_messages=[],
        rule_result=rule_result,
    )

    signals = json.loads(llm_client.calls[0]["prompt"])["rule_result"]["signals"]
    assert signals["source"] == "s" * 500
    assert signals["target"] == "t" * 500
    assert signals["nested"]["raw"] == "x" * 500
    assert signals["items"] == ["y" * 500, 42, True]
    assert signals["tuple_items"] == ["z" * 500]
    assert signals["has_question_style"] is True
    assert signals["score"] == 0.5
