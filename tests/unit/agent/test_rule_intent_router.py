from types import SimpleNamespace

from src.agent.rule_intent_router import RuleIntentRouter


def make_session(status="completed", source="general_chat", target="general_chat"):
    task = SimpleNamespace(source=source, target=target)
    return SimpleNamespace(status=status, task=task)


def test_classify_structured_diagnosis_as_hard():
    router = RuleIntentRouter()

    result = router.classify("web-01到db-01端口3306连接失败")

    assert result.route == "start_diagnosis"
    assert result.certainty == "hard"
    assert result.signals["has_pair"] is True
    assert result.signals["has_failure"] is True


def test_classify_legacy_failure_phrase_as_hard_diagnosis():
    router = RuleIntentRouter()

    result = router.classify("web-01到db-01连不上")

    assert result.route == "start_diagnosis"
    assert result.certainty == "hard"
    assert result.signals["has_failure"] is True
    assert result.signals["source"] == "web-01"
    assert result.signals["target"] == "db-01"


def test_classify_connected_unreachable_phrase_keeps_clean_endpoints():
    router = RuleIntentRouter()

    result = router.classify("web-01到db-01连不通")

    assert result.route == "start_diagnosis"
    assert result.certainty == "hard"
    assert result.signals["has_failure"] is True
    assert result.signals["source"] == "web-01"
    assert result.signals["target"] == "db-01"


def test_classify_ambiguous_issue_as_soft_clarify():
    router = RuleIntentRouter()

    result = router.classify("我现在访问不通")

    assert result.route == "clarify"
    assert result.certainty == "soft"
    assert result.signals["has_pair"] is False
    assert "源主机" in result.clarify_message


def test_classify_waiting_user_session_as_hard_continue():
    router = RuleIntentRouter()
    session = make_session(status="waiting_user", source="10.0.1.10", target="10.0.2.20")

    result = router.classify("目标机器上有防火墙", session=session)

    assert result.route == "continue_diagnosis"
    assert result.certainty == "hard"
    assert result.reason == "session_waiting_user"
