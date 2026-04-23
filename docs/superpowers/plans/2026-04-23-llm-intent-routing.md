# LLM Intent Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current single-layer regex intent router with a rule-first hybrid router that invokes the LLM only for low-certainty messages while preserving the existing four-route API contract.

**Architecture:** Extract the current regex logic into a dedicated `RuleIntentRouter` that can emit both backward-compatible `IntentDecision` objects and richer `RuleIntentResult` metadata. Add an `LLMIntentClassifier` for JSON-only classification, then compose both in a `HybridIntentRouter` with conservative merge rules, environment-driven thresholds, structured decision logging, and safe fallback to pure rule routing when the LLM is unavailable or low-confidence.

**Tech Stack:** FastAPI, Python dataclasses, Pydantic v2, existing `LLMClient`, pytest, monkeypatch-based unit tests

---

## File Structure

- `src/agent/intent_types.py`
  - New shared dataclasses for `IntentDecision`, `RuleIntentResult`, and `LLMIntentResult`.
- `src/agent/rule_intent_router.py`
  - New home for the existing regex routing logic, upgraded to emit `hard`/`soft` certainty plus signals.
- `src/agent/llm_intent_router.py`
  - New JSON-only classifier that wraps `LLMClient.invoke_with_json()`, validates payloads, and raises controlled errors on malformed output.
- `src/agent/hybrid_intent_router.py`
  - New orchestrator that calls the rule router first, selectively invokes the LLM classifier, and applies conservative merge rules.
- `src/agent/intent_router.py`
  - Backward-compatible public facade that exports `IntentRouter`, `IntentDecision`, and `build_intent_router()`.
- `src/agent/__init__.py`
  - Export the new router types and factory.
- `src/api.py`
  - Replace the direct `IntentRouter()` global with `build_intent_router()` and keep `/api/v1/chat/stream` unchanged.
- `.env.example`
  - Document `INTENT_ROUTER_MODE`, confidence thresholds, and decision logging toggle.
- `tests/unit/agent/test_rule_intent_router.py`
  - New rule-router tests for `hard`/`soft` certainty and signal extraction.
- `tests/unit/agent/test_llm_intent_router.py`
  - New classifier tests for valid JSON, invalid JSON, and schema rejection.
- `tests/unit/agent/test_hybrid_intent_router.py`
  - New hybrid-router tests for hard bypass, fallback, and conservative merge rules.
- `tests/unit/agent/test_intent_router_factory.py`
  - New factory tests for `rule`, `hybrid`, and hybrid-to-rule fallback when `LLMClient` cannot be created.
- `tests/unit/agent/test_intent_routing_samples.py`
  - New regression matrix for representative user prompts across diagnosis, clarify, general chat, and continuation.
- `tests/unit/test_chat_stream.py`
  - Existing API entrypoint regression; re-run unchanged to confirm the global router swap does not break routing.

### Task 1: Extract Shared Intent Types And Rule Router

**Files:**
- Create: `src/agent/intent_types.py`
- Create: `src/agent/rule_intent_router.py`
- Modify: `src/agent/intent_router.py`
- Modify: `src/agent/__init__.py`
- Create: `tests/unit/agent/test_rule_intent_router.py`
- Test: `tests/unit/agent/test_rule_intent_router.py`
- Test: `tests/unit/agent/test_intent_router.py`

- [ ] **Step 1: Write the failing rule-router tests**

Create `tests/unit/agent/test_rule_intent_router.py` with:

```python
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
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run:

```powershell
python -m pytest tests/unit/agent/test_rule_intent_router.py tests/unit/agent/test_intent_router.py -q
```

Expected:

```text
ERROR tests/unit/agent/test_rule_intent_router.py
E   ModuleNotFoundError: No module named 'src.agent.rule_intent_router'
```

- [ ] **Step 3: Create the shared intent dataclasses**

Create `src/agent/intent_types.py` with:

```python
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
```

- [ ] **Step 4: Move the regex routing logic into `RuleIntentRouter`**

Create `src/agent/rule_intent_router.py` with:

```python
import re
from typing import Any, Optional

from ..utils.input_validator import extract_endpoint_pair
from .intent_types import IntentDecision, RuleIntentResult

ACCESS_RELATION_RE = re.compile(
    r"(访问关系|哪些系统访问|谁访问|被哪些系统访问|之间.*访问关系)",
    re.IGNORECASE,
)
QUESTION_STYLE_RE = re.compile(
    r"(怎么|如何|为什么|什么是|哪些|步骤|原理|思路|办法|请问|\?)",
    re.IGNORECASE,
)
FAILURE_RE = re.compile(
    r"(不通|失败|超时|拒绝|访问不了|访问失败|无法访问|连不上|连接失败|timeout|refused|"
    r"connection reset|no route|故障|异常)",
    re.IGNORECASE,
)
ACTIONABLE_RE = re.compile(
    r"(帮我|请帮|麻烦|排查|诊断|查一下|查下|看一下|看下|看看|定位|处理一下|处理|报障)",
    re.IGNORECASE,
)
LIVE_ISSUE_RE = re.compile(
    r"(现在|目前|刚刚|今天|线上|生产|我们这边|这里|有个问题|出现问题)",
    re.IGNORECASE,
)
TOOL_CMD_RE = re.compile(r"\b(ping|traceroute|telnet|curl|nc|ss)\b", re.IGNORECASE)
PORT_OR_SERVICE_RE = re.compile(
    r"(端口|port\b|http|https|mysql|redis|postgres|postgresql|ssh|dns)",
    re.IGNORECASE,
)
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

GENERIC_ENDPOINTS = {
    "我",
    "我们",
    "我现在",
    "现在",
    "目前",
    "这里",
    "这边",
    "不通",
    "失败",
    "超时",
    "异常",
    "问题",
    "访问",
    "连接",
}


class RuleIntentRouter:
    """Regex-first intent router that emits certainty and signals."""

    def classify(self, message: str, session: Optional[Any] = None) -> RuleIntentResult:
        text = (message or "").strip()
        session_status = getattr(session, "status", None)

        if session_status == "waiting_user":
            return RuleIntentResult(
                route="continue_diagnosis",
                confidence=0.99,
                reason="session_waiting_user",
                certainty="hard",
                signals={"session_status": session_status},
            )

        source, target = extract_endpoint_pair(text)
        has_pair = self._has_specific_pair(source, target)
        has_ip = bool(IP_RE.search(text))
        has_failure = bool(FAILURE_RE.search(text))
        has_actionable = bool(ACTIONABLE_RE.search(text))
        has_live_issue = bool(LIVE_ISSUE_RE.search(text))
        has_question_style = bool(QUESTION_STYLE_RE.search(text))
        has_tool_cmd = bool(TOOL_CMD_RE.search(text))
        has_port_or_service = bool(PORT_OR_SERVICE_RE.search(text))
        is_access_relation_query = bool(ACCESS_RELATION_RE.search(text))

        signals = {
            "source": source,
            "target": target,
            "has_pair": has_pair,
            "has_ip": has_ip,
            "has_failure": has_failure,
            "has_actionable": has_actionable,
            "has_live_issue": has_live_issue,
            "has_question_style": has_question_style,
            "has_tool_cmd": has_tool_cmd,
            "has_port_or_service": has_port_or_service,
            "is_access_relation_query": is_access_relation_query,
            "is_diagnostic_session": self._is_diagnostic_session(session),
        }

        if signals["is_diagnostic_session"]:
            if has_pair and (has_failure or has_tool_cmd or has_actionable or has_ip):
                return RuleIntentResult(
                    route="start_diagnosis",
                    confidence=0.90,
                    reason="new_diagnosis_in_diagnostic_session",
                    certainty="hard",
                    signals=signals,
                )
            return RuleIntentResult(
                route="continue_diagnosis",
                confidence=0.75,
                reason="follow_up_in_diagnostic_session",
                certainty="soft",
                signals=signals,
            )

        if is_access_relation_query:
            return RuleIntentResult(
                route="general_chat",
                confidence=0.95,
                reason="access_relation_query",
                certainty="hard",
                signals=signals,
            )

        if has_pair and (has_failure or has_tool_cmd or has_actionable or has_ip):
            return RuleIntentResult(
                route="start_diagnosis",
                confidence=0.92,
                reason="structured_diagnosis_request",
                certainty="hard",
                signals=signals,
            )

        if has_tool_cmd and has_ip:
            return RuleIntentResult(
                route="start_diagnosis",
                confidence=0.86,
                reason="specific_diagnostic_command",
                certainty="hard",
                signals=signals,
            )

        if has_question_style:
            return RuleIntentResult(
                route="general_chat",
                confidence=0.78,
                reason="general_network_question",
                certainty="soft",
                signals=signals,
            )

        if has_failure and (has_actionable or has_live_issue):
            return RuleIntentResult(
                route="clarify",
                confidence=0.82,
                reason="issue_report_without_enough_details",
                certainty="soft",
                clarify_message=self._build_clarify_message(
                    has_pair=has_pair,
                    has_port_or_service=has_port_or_service,
                ),
                signals=signals,
            )

        if has_failure and not has_pair:
            return RuleIntentResult(
                route="clarify",
                confidence=0.70,
                reason="failure_signal_without_endpoints",
                certainty="soft",
                clarify_message=self._build_clarify_message(
                    has_pair=has_pair,
                    has_port_or_service=has_port_or_service,
                ),
                signals=signals,
            )

        if has_tool_cmd or has_port_or_service:
            return RuleIntentResult(
                route="general_chat",
                confidence=0.68,
                reason="general_network_topic",
                certainty="soft",
                signals=signals,
            )

        return RuleIntentResult(
            route="general_chat",
            confidence=0.55,
            reason="default_general_chat",
            certainty="soft",
            signals=signals,
        )

    def route_message(self, message: str, session: Optional[Any] = None) -> IntentDecision:
        return self.classify(message, session=session).to_decision()

    def _is_diagnostic_session(self, session: Optional[Any]) -> bool:
        if not session or not getattr(session, "task", None):
            return False

        task = session.task
        return not (
            getattr(task, "source", None) == "general_chat"
            and getattr(task, "target", None) == "general_chat"
        )

    def _has_specific_pair(self, source: Optional[str], target: Optional[str]) -> bool:
        return self._is_specific_endpoint(source) and self._is_specific_endpoint(target)

    def _is_specific_endpoint(self, endpoint: Optional[str]) -> bool:
        if not endpoint:
            return False

        normalized = endpoint.strip().lower()
        if len(normalized) < 2:
            return False

        if normalized in GENERIC_ENDPOINTS:
            return False

        if any(token in normalized for token in ("现在", "目前", "这边", "这里")) and len(normalized) <= 4:
            return False

        return True

    def _build_clarify_message(self, has_pair: bool, has_port_or_service: bool) -> str:
        if has_pair and has_port_or_service:
            return (
                "如果你是想让我直接开始诊断，请补充更具体的上下文。"
                "请提供源主机、目标主机和实际故障现象；"
                "如果你只是想了解排查方法，我也可以先说明思路。"
            )

        if has_pair:
            return (
                "如果你是想让我直接开始诊断，请再补充端口或更具体的故障现象；"
                "如果你只是想了解排查方法，我也可以先说明思路。"
            )

        return (
            "这句话更像是在描述一个待排查的问题。"
            "如果要我直接开始诊断，请提供源主机、目标主机和端口；"
            "如果你只是想了解排查方法，我也可以先说明思路。"
        )
```

- [ ] **Step 5: Turn `intent_router.py` into a backward-compatible facade**

Replace `src/agent/intent_router.py` with:

```python
"""Public intent-router facade for backward compatibility."""

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
```

Update `src/agent/__init__.py` to:

```python
"""
Agent核心模块

提供任务规划、执行、分析和报告生成功能
"""
from .analyzer import DiagnosticAnalyzer
from .executor import Executor
from .intent_router import IntentRouter
from .rule_intent_router import RuleIntentRouter
from .nlu import NLU
from .planner import TaskPlanner
from .reporter import ReportGenerator

__all__ = [
    "TaskPlanner",
    "Executor",
    "DiagnosticAnalyzer",
    "ReportGenerator",
    "IntentRouter",
    "RuleIntentRouter",
    "NLU",
]
```

- [ ] **Step 6: Run the rule-router and compatibility tests**

Run:

```powershell
python -m pytest tests/unit/agent/test_rule_intent_router.py tests/unit/agent/test_intent_router.py -q
```

Expected:

```text
.........                                                                [100%]
```

- [ ] **Step 7: Commit the rule-router extraction**

```powershell
git add src/agent/intent_types.py src/agent/rule_intent_router.py src/agent/intent_router.py src/agent/__init__.py tests/unit/agent/test_rule_intent_router.py
git commit -m "refactor: extract rule intent router"
```

### Task 2: Add The JSON-Validated LLM Intent Classifier

**Files:**
- Create: `src/agent/llm_intent_router.py`
- Create: `tests/unit/agent/test_llm_intent_router.py`
- Test: `tests/unit/agent/test_llm_intent_router.py`

- [ ] **Step 1: Write the failing classifier tests**

Create `tests/unit/agent/test_llm_intent_router.py` with:

```python
import json

import pytest

from src.agent.intent_types import RuleIntentResult
from src.agent.llm_intent_router import (
    LLMIntentClassificationError,
    LLMIntentClassifier,
)


class FakeLLMClient:
    def __init__(self, payload):
        self.payload = payload

    def invoke_with_json(self, prompt, system_prompt=None, temperature=0.3):
        return self.payload


def make_rule_result():
    return RuleIntentResult(
        route="clarify",
        confidence=0.70,
        reason="failure_signal_without_endpoints",
        certainty="soft",
        clarify_message="请补充源主机、目标主机和端口。",
        signals={
            "has_pair": False,
            "has_failure": True,
            "has_question_style": False,
        },
    )


def test_classifier_returns_validated_result():
    payload = json.dumps(
        {
            "route": "general_chat",
            "confidence": 0.88,
            "reason": "method_question",
            "clarify_message": None,
            "needs_more_detail": False,
            "detected_signals": {"has_question_style": True},
        },
        ensure_ascii=False,
    )
    classifier = LLMIntentClassifier(llm_client=FakeLLMClient(payload))

    result = classifier.classify(
        message="端口不通怎么排查",
        session=None,
        recent_messages=[],
        rule_result=make_rule_result(),
    )

    assert result.route == "general_chat"
    assert result.confidence == 0.88
    assert result.detected_signals["has_question_style"] is True


def test_classifier_rejects_invalid_json():
    classifier = LLMIntentClassifier(llm_client=FakeLLMClient("not-json"))

    with pytest.raises(LLMIntentClassificationError):
        classifier.classify(
            message="我现在访问不通",
            session=None,
            recent_messages=[],
            rule_result=make_rule_result(),
        )


def test_classifier_rejects_unknown_route():
    payload = json.dumps(
        {
            "route": "diagnose_now",
            "confidence": 0.95,
            "reason": "bad_route",
            "clarify_message": None,
            "needs_more_detail": False,
            "detected_signals": {},
        },
        ensure_ascii=False,
    )
    classifier = LLMIntentClassifier(llm_client=FakeLLMClient(payload))

    with pytest.raises(LLMIntentClassificationError):
        classifier.classify(
            message="我现在访问不通",
            session=None,
            recent_messages=[],
            rule_result=make_rule_result(),
        )
```

- [ ] **Step 2: Run the classifier tests and confirm they fail**

Run:

```powershell
python -m pytest tests/unit/agent/test_llm_intent_router.py -q
```

Expected:

```text
ERROR tests/unit/agent/test_llm_intent_router.py
E   ModuleNotFoundError: No module named 'src.agent.llm_intent_router'
```

- [ ] **Step 3: Implement the LLM classifier and schema validation**

Create `src/agent/llm_intent_router.py` with:

```python
import json
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from ..integrations.llm_client import LLMClient
from .intent_types import LLMIntentResult, RuleIntentResult


ALLOWED_ROUTES = (
    "start_diagnosis",
    "continue_diagnosis",
    "clarify",
    "general_chat",
)


class LLMIntentClassificationError(Exception):
    """Raised when the classifier cannot produce a valid routing payload."""


class _LLMIntentPayload(BaseModel):
    route: Literal["start_diagnosis", "continue_diagnosis", "clarify", "general_chat"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    clarify_message: Optional[str] = None
    needs_more_detail: bool = False
    detected_signals: Dict[str, Any] = Field(default_factory=dict)


class LLMIntentClassifier:
    SYSTEM_PROMPT = """你不是聊天助手，你是消息路由分类器。

你的唯一任务是输出 JSON，并把用户消息分类到以下四类之一：
- start_diagnosis
- continue_diagnosis
- clarify
- general_chat

规则：
1. 信息不足时优先 clarify，不要激进地进入诊断
2. 方法咨询、知识问答、访问关系知识问题优先 general_chat
3. 只有在诊断对象和上下文较明确时，才给 start_diagnosis
4. 只有在当前消息明显是诊断会话追答时，才给 continue_diagnosis
5. 只输出 JSON，不输出额外解释文本
"""

    def __init__(self, llm_client: LLMClient, temperature: float = 0.0):
        self.llm_client = llm_client
        self.temperature = temperature

    def classify(
        self,
        message: str,
        session: Optional[Any],
        recent_messages: List[Dict[str, Any]],
        rule_result: RuleIntentResult,
    ) -> LLMIntentResult:
        prompt = self._build_prompt(
            message=message,
            session=session,
            recent_messages=recent_messages,
            rule_result=rule_result,
        )
        raw = self.llm_client.invoke_with_json(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            temperature=self.temperature,
        )
        try:
            payload = json.loads(raw)
            data = _LLMIntentPayload.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise LLMIntentClassificationError(str(exc)) from exc

        return LLMIntentResult(
            route=data.route,
            confidence=data.confidence,
            reason=data.reason,
            clarify_message=data.clarify_message,
            needs_more_detail=data.needs_more_detail,
            detected_signals=data.detected_signals,
        )

    def _build_prompt(
        self,
        message: str,
        session: Optional[Any],
        recent_messages: List[Dict[str, Any]],
        rule_result: RuleIntentResult,
    ) -> str:
        session_status = getattr(session, "status", None)
        task = getattr(session, "task", None)
        is_diagnostic_session = bool(
            task
            and not (
                getattr(task, "source", None) == "general_chat"
                and getattr(task, "target", None) == "general_chat"
            )
        )
        trimmed_history = recent_messages[-5:]

        return json.dumps(
            {
                "message": message,
                "session_status": session_status,
                "is_diagnostic_session": is_diagnostic_session,
                "recent_messages": [
                    {"role": item.get("role"), "content": item.get("content")}
                    for item in trimmed_history
                ],
                "rule_result": {
                    "route": rule_result.route,
                    "confidence": rule_result.confidence,
                    "reason": rule_result.reason,
                    "certainty": rule_result.certainty,
                    "clarify_message": rule_result.clarify_message,
                    "signals": rule_result.signals,
                },
                "required_output_keys": [
                    "route",
                    "confidence",
                    "reason",
                    "clarify_message",
                    "needs_more_detail",
                    "detected_signals",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
```

- [ ] **Step 4: Run the classifier tests and verify they pass**

Run:

```powershell
python -m pytest tests/unit/agent/test_llm_intent_router.py -q
```

Expected:

```text
...                                                                      [100%]
```

- [ ] **Step 5: Commit the LLM classifier**

```powershell
git add src/agent/llm_intent_router.py tests/unit/agent/test_llm_intent_router.py
git commit -m "feat: add LLM intent classifier"
```

### Task 3: Implement Hybrid Routing, Fallback, And Conservative Merge Rules

**Files:**
- Create: `src/agent/hybrid_intent_router.py`
- Modify: `src/agent/__init__.py`
- Create: `tests/unit/agent/test_hybrid_intent_router.py`
- Test: `tests/unit/agent/test_hybrid_intent_router.py`

- [ ] **Step 1: Write the failing hybrid-router tests**

Create `tests/unit/agent/test_hybrid_intent_router.py` with:

```python
from src.agent.hybrid_intent_router import HybridIntentRouter
from src.agent.intent_types import LLMIntentResult, RuleIntentResult


class StubRuleRouter:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def classify(self, message, session=None):
        self.calls += 1
        return self.result


class StubLLMClassifier:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def classify(self, message, session, recent_messages, rule_result):
        self.calls += 1
        return self.result


def test_hard_rule_result_bypasses_llm():
    rule_result = RuleIntentResult(
        route="start_diagnosis",
        confidence=0.92,
        reason="structured_diagnosis_request",
        certainty="hard",
        clarify_message=None,
        signals={"has_pair": True, "has_failure": True},
    )
    router = HybridIntentRouter(
        rule_router=StubRuleRouter(rule_result),
        llm_classifier=StubLLMClassifier(
            LLMIntentResult(route="general_chat", confidence=0.99, reason="unused")
        ),
    )

    decision = router.route_message("web-01到db-01端口3306连接失败")

    assert decision.route == "start_diagnosis"
    assert router.llm_classifier.calls == 0


def test_low_confidence_llm_result_falls_back_to_rule():
    rule_result = RuleIntentResult(
        route="general_chat",
        confidence=0.78,
        reason="general_network_question",
        certainty="soft",
        clarify_message=None,
        signals={"has_question_style": True},
    )
    router = HybridIntentRouter(
        rule_router=StubRuleRouter(rule_result),
        llm_classifier=StubLLMClassifier(
            LLMIntentResult(route="general_chat", confidence=0.60, reason="too_low")
        ),
        min_confidence=0.80,
        diagnosis_min_confidence=0.85,
    )

    decision = router.route_message("端口不通怎么排查")

    assert decision.route == "general_chat"
    assert decision.reason == "general_network_question"


def test_conservative_merge_prefers_clarify_over_diagnosis_without_pair():
    rule_result = RuleIntentResult(
        route="clarify",
        confidence=0.82,
        reason="issue_report_without_enough_details",
        certainty="soft",
        clarify_message="请提供源主机、目标主机和端口。",
        signals={"has_pair": False, "has_failure": True},
    )
    router = HybridIntentRouter(
        rule_router=StubRuleRouter(rule_result),
        llm_classifier=StubLLMClassifier(
            LLMIntentResult(
                route="start_diagnosis",
                confidence=0.95,
                reason="aggressive_diagnosis",
                clarify_message=None,
                needs_more_detail=True,
                detected_signals={"has_specific_endpoints": False},
            )
        ),
        min_confidence=0.80,
        diagnosis_min_confidence=0.85,
    )

    decision = router.route_message("我现在访问不通")

    assert decision.route == "clarify"
    assert "源主机" in decision.clarify_message
```

- [ ] **Step 2: Run the hybrid-router tests and confirm they fail**

Run:

```powershell
python -m pytest tests/unit/agent/test_hybrid_intent_router.py -q
```

Expected:

```text
ERROR tests/unit/agent/test_hybrid_intent_router.py
E   ModuleNotFoundError: No module named 'src.agent.hybrid_intent_router'
```

- [ ] **Step 3: Implement the hybrid router with conservative merge and JSON decision logging**

Create `src/agent/hybrid_intent_router.py` with:

```python
import json
import logging
from typing import Any, Dict, List, Optional

from .intent_types import IntentDecision, LLMIntentResult, RuleIntentResult
from .llm_intent_router import LLMIntentClassificationError, LLMIntentClassifier
from .rule_intent_router import RuleIntentRouter

logger = logging.getLogger(__name__)


class HybridIntentRouter:
    """Rule-first router that escalates soft cases to the LLM."""

    def __init__(
        self,
        rule_router: Optional[RuleIntentRouter] = None,
        llm_classifier: Optional[LLMIntentClassifier] = None,
        min_confidence: float = 0.80,
        diagnosis_min_confidence: float = 0.85,
        log_decisions: bool = False,
    ):
        self.rule_router = rule_router or RuleIntentRouter()
        self.llm_classifier = llm_classifier
        self.min_confidence = min_confidence
        self.diagnosis_min_confidence = diagnosis_min_confidence
        self.log_decisions = log_decisions

    def route_message(self, message: str, session: Optional[Any] = None) -> IntentDecision:
        rule_result = self.rule_router.classify(message, session=session)
        if rule_result.certainty == "hard":
            decision = rule_result.to_decision()
            self._log_decision(message, rule_result, None, decision, fallback_reason=None)
            return decision

        if self.llm_classifier is None:
            decision = rule_result.to_decision()
            self._log_decision(message, rule_result, None, decision, fallback_reason="llm_unavailable")
            return decision

        recent_messages = self._recent_messages(session)
        try:
            llm_result = self.llm_classifier.classify(
                message=message,
                session=session,
                recent_messages=recent_messages,
                rule_result=rule_result,
            )
        except LLMIntentClassificationError:
            decision = rule_result.to_decision()
            self._log_decision(message, rule_result, None, decision, fallback_reason="llm_invalid_output")
            return decision
        except Exception:
            decision = rule_result.to_decision()
            self._log_decision(message, rule_result, None, decision, fallback_reason="llm_exception")
            return decision

        decision = self._merge(rule_result, llm_result)
        self._log_decision(message, rule_result, llm_result, decision, fallback_reason=None)
        return decision

    def _merge(self, rule_result: RuleIntentResult, llm_result: LLMIntentResult) -> IntentDecision:
        threshold = (
            self.diagnosis_min_confidence
            if llm_result.route in {"start_diagnosis", "continue_diagnosis"}
            else self.min_confidence
        )
        if llm_result.confidence < threshold:
            return rule_result.to_decision()

        has_pair = bool(rule_result.signals.get("has_pair"))
        has_failure = bool(rule_result.signals.get("has_failure"))
        has_question_style = bool(rule_result.signals.get("has_question_style"))

        if llm_result.route == "start_diagnosis" and not has_pair:
            return IntentDecision(
                route="clarify",
                confidence=rule_result.confidence,
                reason="conservative_missing_endpoints",
                clarify_message=rule_result.clarify_message,
            )

        if rule_result.route == "clarify" and llm_result.route == "start_diagnosis":
            return IntentDecision(
                route="clarify",
                confidence=rule_result.confidence,
                reason="conservative_clarify_over_diagnosis",
                clarify_message=rule_result.clarify_message,
            )

        if rule_result.route == "general_chat" and llm_result.route == "start_diagnosis":
            if has_question_style:
                return rule_result.to_decision()
            return IntentDecision(
                route="clarify",
                confidence=rule_result.confidence,
                reason="conservative_question_or_low_context",
                clarify_message="如果要直接开始诊断，请提供源主机、目标主机和端口。",
            )

        if rule_result.route == "clarify" and llm_result.route == "general_chat":
            if has_failure:
                return rule_result.to_decision()
            return llm_result.to_decision()

        return llm_result.to_decision()

    def _recent_messages(self, session: Optional[Any]) -> List[Dict[str, Any]]:
        if not session or not getattr(session, "messages", None):
            return []
        return [
            {"role": item.get("role"), "content": item.get("content")}
            for item in session.messages[-5:]
        ]

    def _log_decision(
        self,
        message: str,
        rule_result: RuleIntentResult,
        llm_result: Optional[LLMIntentResult],
        decision: IntentDecision,
        fallback_reason: Optional[str],
    ) -> None:
        if not self.log_decisions:
            return

        logger.info(
            json.dumps(
                {
                    "message": message,
                    "rule_route": rule_result.route,
                    "rule_certainty": rule_result.certainty,
                    "rule_reason": rule_result.reason,
                    "llm_route": llm_result.route if llm_result else None,
                    "llm_confidence": llm_result.confidence if llm_result else None,
                    "llm_reason": llm_result.reason if llm_result else None,
                    "final_route": decision.route,
                    "fallback_reason": fallback_reason,
                },
                ensure_ascii=False,
            )
        )
```

Update `src/agent/__init__.py` to export the new router:

```python
from .hybrid_intent_router import HybridIntentRouter

__all__ = [
    "TaskPlanner",
    "Executor",
    "DiagnosticAnalyzer",
    "ReportGenerator",
    "IntentRouter",
    "RuleIntentRouter",
    "HybridIntentRouter",
    "NLU",
]
```

- [ ] **Step 4: Run the hybrid-router tests and verify they pass**

Run:

```powershell
python -m pytest tests/unit/agent/test_hybrid_intent_router.py -q
```

Expected:

```text
...                                                                      [100%]
```

- [ ] **Step 5: Commit the hybrid routing logic**

```powershell
git add src/agent/hybrid_intent_router.py src/agent/__init__.py tests/unit/agent/test_hybrid_intent_router.py
git commit -m "feat: add hybrid intent router"
```

### Task 4: Wire The Router Factory Into The API And Add Configurable Fallback

**Files:**
- Modify: `src/agent/intent_router.py`
- Modify: `src/agent/__init__.py`
- Modify: `src/api.py`
- Modify: `.env.example`
- Create: `tests/unit/agent/test_intent_router_factory.py`
- Test: `tests/unit/agent/test_intent_router_factory.py`
- Test: `tests/unit/test_chat_stream.py`

- [ ] **Step 1: Write the failing factory tests**

Create `tests/unit/agent/test_intent_router_factory.py` with:

```python
from types import SimpleNamespace

from src.agent.hybrid_intent_router import HybridIntentRouter
from src.agent.intent_router import build_intent_router
from src.agent.rule_intent_router import RuleIntentRouter


class FakeLLMClient:
    pass


def test_build_router_defaults_to_rule(monkeypatch):
    monkeypatch.delenv("INTENT_ROUTER_MODE", raising=False)

    router = build_intent_router()

    assert isinstance(router, RuleIntentRouter)


def test_build_router_returns_hybrid_when_enabled(monkeypatch):
    monkeypatch.setenv("INTENT_ROUTER_MODE", "hybrid")

    router = build_intent_router(llm_client=FakeLLMClient())

    assert isinstance(router, HybridIntentRouter)
    assert router.llm_classifier is not None


def test_build_router_falls_back_to_rule_when_llm_client_creation_fails(monkeypatch):
    monkeypatch.setenv("INTENT_ROUTER_MODE", "hybrid")

    def raising_client():
        raise ValueError("missing API key")

    monkeypatch.setattr("src.agent.intent_router.LLMClient", raising_client)

    router = build_intent_router()

    assert isinstance(router, RuleIntentRouter)
```

- [ ] **Step 2: Run the factory and API regression tests and confirm the new factory test fails**

Run:

```powershell
python -m pytest tests/unit/agent/test_intent_router_factory.py tests/unit/test_chat_stream.py -q
```

Expected:

```text
ERROR tests/unit/agent/test_intent_router_factory.py
E   ImportError: cannot import name 'build_intent_router' from 'src.agent.intent_router'
```

- [ ] **Step 3: Add the router factory, switch the API to it, and document the env vars**

Update `src/agent/intent_router.py` to:

```python
"""Public intent-router facade and factory."""

import os

from ..integrations import LLMClient
from .hybrid_intent_router import HybridIntentRouter
from .intent_types import IntentDecision, LLMIntentResult, RuleIntentResult
from .llm_intent_router import LLMIntentClassifier
from .rule_intent_router import RuleIntentRouter

IntentRouter = RuleIntentRouter


def build_intent_router(llm_client=None):
    mode = os.getenv("INTENT_ROUTER_MODE", "rule").lower()
    min_confidence = float(os.getenv("INTENT_LLM_MIN_CONFIDENCE", "0.80"))
    diagnosis_min_confidence = float(os.getenv("INTENT_LLM_DIAGNOSIS_MIN_CONFIDENCE", "0.85"))
    log_decisions = os.getenv("INTENT_LOG_DECISIONS", "false").lower() == "true"

    if mode != "hybrid":
        return RuleIntentRouter()

    try:
        client = llm_client or LLMClient()
    except Exception:
        return RuleIntentRouter()

    return HybridIntentRouter(
        rule_router=RuleIntentRouter(),
        llm_classifier=LLMIntentClassifier(llm_client=client),
        min_confidence=min_confidence,
        diagnosis_min_confidence=diagnosis_min_confidence,
        log_decisions=log_decisions,
    )


__all__ = [
    "IntentDecision",
    "RuleIntentResult",
    "LLMIntentResult",
    "RuleIntentRouter",
    "HybridIntentRouter",
    "IntentRouter",
    "build_intent_router",
]
```

Update the import and router initialization near the top of `src/api.py`:

```python
from .agent import build_intent_router, NLU

session_manager = get_session_manager()
intent_router = build_intent_router()
```

Update `src/agent/__init__.py` to export `build_intent_router`:

```python
from .intent_router import IntentRouter, build_intent_router

__all__ = [
    "TaskPlanner",
    "Executor",
    "DiagnosticAnalyzer",
    "ReportGenerator",
    "IntentRouter",
    "RuleIntentRouter",
    "HybridIntentRouter",
    "build_intent_router",
    "NLU",
]
```

Append these env vars to `.env.example`:

```dotenv
# Intent Router 配置
INTENT_ROUTER_MODE=rule  # rule | hybrid
INTENT_LLM_MIN_CONFIDENCE=0.80
INTENT_LLM_DIAGNOSIS_MIN_CONFIDENCE=0.85
INTENT_LOG_DECISIONS=false
```

- [ ] **Step 4: Run the factory tests plus chat-stream regression**

Run:

```powershell
python -m pytest tests/unit/agent/test_intent_router_factory.py tests/unit/test_chat_stream.py -q
```

Expected:

```text
......                                                                   [100%]
```

- [ ] **Step 5: Commit the API and config wiring**

```powershell
git add src/agent/intent_router.py src/agent/__init__.py src/api.py .env.example tests/unit/agent/test_intent_router_factory.py
git commit -m "feat: wire hybrid intent routing"
```

### Task 5: Add A Regression Prompt Matrix For Representative Routing Scenarios

**Files:**
- Create: `tests/unit/agent/test_intent_routing_samples.py`
- Modify: `src/agent/hybrid_intent_router.py`
- Test: `tests/unit/agent/test_intent_routing_samples.py`
- Test: `tests/unit/agent/test_hybrid_intent_router.py`

- [ ] **Step 1: Write the failing regression matrix**

Create `tests/unit/agent/test_intent_routing_samples.py` with:

```python
import json
from types import SimpleNamespace

import pytest

from src.agent.hybrid_intent_router import HybridIntentRouter
from src.agent.llm_intent_router import LLMIntentClassifier
from src.agent.rule_intent_router import RuleIntentRouter


class MappingLLMClient:
    def __init__(self, mapping):
        self.mapping = mapping

    def invoke_with_json(self, prompt, system_prompt=None, temperature=0.3):
        for needle, payload in self.mapping.items():
            if needle in prompt:
                return json.dumps(payload, ensure_ascii=False)
        raise AssertionError(f"Unexpected prompt: {prompt}")


def make_session(status="completed", source="general_chat", target="general_chat", messages=None):
    task = SimpleNamespace(source=source, target=target)
    return SimpleNamespace(status=status, task=task, messages=messages or [])


@pytest.mark.parametrize(
    ("message", "session", "expected_route"),
    [
        ("web-01到db-01端口3306连接失败", None, "start_diagnosis"),
        ("端口不通怎么排查", None, "general_chat"),
        ("我现在访问不通", None, "clarify"),
        ("N-CRM和N-OA之间有哪些访问关系", None, "general_chat"),
        (
            "目标机器上有防火墙",
            make_session(status="waiting_user", source="10.0.1.10", target="10.0.2.20"),
            "continue_diagnosis",
        ),
    ],
)
def test_hybrid_router_regression_matrix(message, session, expected_route):
    llm_client = MappingLLMClient(
        {
            "端口不通怎么排查": {
                "route": "general_chat",
                "confidence": 0.92,
                "reason": "method_question",
                "clarify_message": None,
                "needs_more_detail": False,
                "detected_signals": {"has_question_style": True},
            },
            "我现在访问不通": {
                "route": "clarify",
                "confidence": 0.94,
                "reason": "missing_endpoints",
                "clarify_message": "请提供源主机、目标主机和端口。",
                "needs_more_detail": True,
                "detected_signals": {"has_specific_endpoints": False},
            },
        }
    )
    router = HybridIntentRouter(
        rule_router=RuleIntentRouter(),
        llm_classifier=LLMIntentClassifier(llm_client=llm_client),
        min_confidence=0.80,
        diagnosis_min_confidence=0.85,
    )

    decision = router.route_message(message, session=session)

    assert decision.route == expected_route
```

- [ ] **Step 2: Run the regression matrix and confirm the targeted case fails if merge behavior is incomplete**

Run:

```powershell
python -m pytest tests/unit/agent/test_intent_routing_samples.py tests/unit/agent/test_hybrid_intent_router.py -q
```

Expected:

```text
F....                                                                    [100%]
E   AssertionError: assert 'start_diagnosis' == 'clarify'
```

- [ ] **Step 3: Tighten the recent-message handling and conservative merge branches**

Update `src/agent/hybrid_intent_router.py` so `_merge()` and `_recent_messages()` match the regression matrix exactly:

```python
    def _merge(self, rule_result: RuleIntentResult, llm_result: LLMIntentResult) -> IntentDecision:
        threshold = (
            self.diagnosis_min_confidence
            if llm_result.route in {"start_diagnosis", "continue_diagnosis"}
            else self.min_confidence
        )
        if llm_result.confidence < threshold:
            return rule_result.to_decision()

        has_pair = bool(rule_result.signals.get("has_pair"))
        has_failure = bool(rule_result.signals.get("has_failure"))
        has_question_style = bool(rule_result.signals.get("has_question_style"))
        has_specific_endpoints = bool(
            llm_result.detected_signals.get("has_specific_endpoints", has_pair)
        )

        if llm_result.route in {"start_diagnosis", "continue_diagnosis"} and not has_specific_endpoints:
            return IntentDecision(
                route="clarify",
                confidence=rule_result.confidence,
                reason="conservative_missing_endpoints",
                clarify_message=rule_result.clarify_message
                or "如果要直接开始诊断，请提供源主机、目标主机和端口。",
            )

        if rule_result.route == "clarify" and llm_result.route == "general_chat" and has_failure:
            return rule_result.to_decision()

        if rule_result.route == "general_chat" and llm_result.route == "start_diagnosis":
            if has_question_style:
                return rule_result.to_decision()
            return IntentDecision(
                route="clarify",
                confidence=rule_result.confidence,
                reason="conservative_question_or_low_context",
                clarify_message="如果要直接开始诊断，请提供源主机、目标主机和端口。",
            )

        return llm_result.to_decision()

    def _recent_messages(self, session: Optional[Any]) -> List[Dict[str, Any]]:
        if not session or not getattr(session, "messages", None):
            return []
        return [
            {
                "role": item.get("role"),
                "content": item.get("content"),
            }
            for item in session.messages[-5:]
            if item.get("role") in {"user", "assistant", "system"}
        ]
```

- [ ] **Step 4: Run the regression matrix and hybrid tests again**

Run:

```powershell
python -m pytest tests/unit/agent/test_intent_routing_samples.py tests/unit/agent/test_hybrid_intent_router.py -q
```

Expected:

```text
........                                                                 [100%]
```

- [ ] **Step 5: Commit the regression matrix**

```powershell
git add src/agent/hybrid_intent_router.py tests/unit/agent/test_intent_routing_samples.py
git commit -m "test: add intent routing regression matrix"
```

## Self-Review

### Spec coverage

- `RuleIntentRouter`, `LLMIntentClassifier`, and `HybridIntentRouter` each have a dedicated task.
- `rule`/`hybrid` mode switching is covered in Task 4.
- Conservative merge and LLM fallback are covered in Task 3 and hardened in Task 5.
- Structured decision logging is implemented in Task 3.
- Regression prompts for diagnosis, clarify, general chat, access relation, and continuation are covered in Task 5.

### Placeholder scan

- No placeholder markers remain.
- Every code-edit step includes concrete code blocks.
- Every test step includes exact `python -m pytest` commands because `pytest` is not on PATH in this workspace.

### Type consistency

- `RuleIntentRouter.classify()` returns `RuleIntentResult`.
- `RuleIntentRouter.route_message()` and `HybridIntentRouter.route_message()` both return `IntentDecision`.
- `LLMIntentClassifier.classify()` returns `LLMIntentResult`.
- `build_intent_router()` returns either `RuleIntentRouter` or `HybridIntentRouter`, both exposing `route_message()`.
