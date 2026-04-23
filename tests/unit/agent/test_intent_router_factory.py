import subprocess
import sys
from types import SimpleNamespace

def test_build_intent_router_defaults_to_rule_router(monkeypatch):
    monkeypatch.delenv("INTENT_ROUTER_MODE", raising=False)

    from src.agent.intent_router import RuleIntentRouter, build_intent_router

    router = build_intent_router()

    assert isinstance(router, RuleIntentRouter)


def test_build_intent_router_rule_mode_returns_rule_router(monkeypatch):
    monkeypatch.setenv("INTENT_ROUTER_MODE", "rule")

    from src.agent.intent_router import RuleIntentRouter, build_intent_router

    router = build_intent_router()

    assert isinstance(router, RuleIntentRouter)


def test_build_intent_router_hybrid_mode_uses_injected_llm_client(monkeypatch):
    monkeypatch.setenv("INTENT_ROUTER_MODE", "hybrid")
    monkeypatch.setenv("INTENT_LLM_MIN_CONFIDENCE", "0.91")
    monkeypatch.setenv("INTENT_LLM_DIAGNOSIS_MIN_CONFIDENCE", "0.93")
    monkeypatch.setenv("INTENT_LOG_DECISIONS", "true")

    from src.agent.hybrid_intent_router import HybridIntentRouter
    from src.agent.intent_router import build_intent_router

    fake_llm_client = object()
    router = build_intent_router(llm_client=fake_llm_client)

    assert isinstance(router, HybridIntentRouter)
    assert router.llm_classifier.llm_client is fake_llm_client
    assert router.min_confidence == 0.91
    assert router.diagnosis_min_confidence == 0.93
    assert router.log_decisions is True


def test_build_intent_router_hybrid_falls_back_when_default_llm_client_creation_fails(monkeypatch):
    monkeypatch.setenv("INTENT_ROUTER_MODE", "hybrid")

    from src.agent.intent_router import RuleIntentRouter, build_intent_router

    def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr("src.agent.intent_router._create_default_llm_client", boom)

    router = build_intent_router()

    assert isinstance(router, RuleIntentRouter)


def test_factory_imports_do_not_eagerly_load_hybrid_modules():
    script = (
        "import sys; "
        "import src.agent; "
        "import src.agent.intent_router; "
        "print('src.agent.hybrid_intent_router' in sys.modules, 'src.agent.llm_intent_router' in sys.modules); "
        "from src.agent import build_intent_router; "
        "print(callable(build_intent_router))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    lines = completed.stdout.strip().splitlines()
    assert lines[0] == "False False"
    assert lines[1] == "True"
