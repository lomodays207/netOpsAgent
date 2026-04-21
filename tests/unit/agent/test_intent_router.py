from types import SimpleNamespace

from src.agent.intent_router import IntentRouter


def make_session(status="completed", source="general_chat", target="general_chat"):
    task = SimpleNamespace(source=source, target=target)
    return SimpleNamespace(status=status, task=task)


class TestIntentRouter:
    def test_routes_structured_hostname_issue_to_diagnosis(self):
        router = IntentRouter()

        decision = router.route_message("web-01到db-01端口3306连接失败")

        assert decision.route == "start_diagnosis"

    def test_routes_method_question_to_general_chat(self):
        router = IntentRouter()

        decision = router.route_message("端口不通怎么排查")

        assert decision.route == "general_chat"

    def test_routes_ambiguous_live_issue_to_clarify(self):
        router = IntentRouter()

        decision = router.route_message("我现在访问不通")

        assert decision.route == "clarify"
        assert "源主机" in decision.clarify_message

    def test_waiting_user_session_continues_diagnosis(self):
        router = IntentRouter()
        session = make_session(status="waiting_user", source="10.0.1.10", target="10.0.2.20")

        decision = router.route_message("目标机器上有防火墙", session=session)

        assert decision.route == "continue_diagnosis"

    def test_diagnostic_session_defaults_to_continue_for_follow_up(self):
        router = IntentRouter()
        session = make_session(status="completed", source="10.0.1.10", target="10.0.2.20")

        decision = router.route_message("为什么判断是防火墙问题", session=session)

        assert decision.route == "continue_diagnosis"

    def test_access_relation_question_stays_in_general_chat(self):
        router = IntentRouter()
        session = make_session(status="completed")

        decision = router.route_message("N-CRM和N-OA之间有哪些访问关系", session=session)

        assert decision.route == "general_chat"
