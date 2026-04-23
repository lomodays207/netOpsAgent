"""LLM-backed intent routing classifier."""

from __future__ import annotations

import json
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from ..integrations.llm_client import LLMClient
from .intent_types import LLMIntentResult, RuleIntentResult


ALLOWED_ROUTES = (
    "start_diagnosis",
    "continue_diagnosis",
    "clarify",
    "general_chat",
)

AllowedRoute = Literal[
    "start_diagnosis",
    "continue_diagnosis",
    "clarify",
    "general_chat",
]


class LLMIntentClassificationError(Exception):
    """Raised when the LLM intent classifier returns invalid output."""


class _LLMIntentPayload(BaseModel):
    route: AllowedRoute
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    clarify_message: Optional[str] = None
    needs_more_detail: bool = False
    detected_signals: Dict[str, Any] = Field(default_factory=dict)


class LLMIntentClassifier:
    """Classify ambiguous routing decisions with a constrained LLM JSON response."""

    SYSTEM_PROMPT = """
你是网络运维聊天入口的路由分类器，不是聊天助手。
你的任务只是把当前用户消息路由到一个允许的处理流程，不要回答用户问题。
只能选择以下 route 之一：start_diagnosis、continue_diagnosis、clarify、general_chat。
信息不足时优先选择 clarify；方法咨询、知识问答和访问关系知识问题优先选择 general_chat。
只有诊断对象和上下文明确时才选择 start_diagnosis。
只有当前消息明显是在诊断会话中继续补充信息时才选择 continue_diagnosis。
必须只输出合法 JSON，不要输出 Markdown、解释文字或额外文本。
""".strip()

    def __init__(self, llm_client: LLMClient, temperature: float = 0.0):
        self.llm_client = llm_client
        self.temperature = temperature

    def classify(
        self,
        message: str,
        session: Optional[Any],
        recent_messages: list[Any],
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
            data = json.loads(raw)
            payload = _LLMIntentPayload.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise LLMIntentClassificationError("Invalid LLM intent classification output") from exc

        return LLMIntentResult(
            route=payload.route,
            confidence=payload.confidence,
            reason=payload.reason,
            clarify_message=payload.clarify_message,
            needs_more_detail=payload.needs_more_detail,
            detected_signals=payload.detected_signals,
        )

    def _build_prompt(
        self,
        message: str,
        session: Optional[Any],
        recent_messages: list[Any],
        rule_result: RuleIntentResult,
    ) -> str:
        prompt_payload = {
            "message": message,
            "session_status": getattr(session, "status", None),
            "is_diagnostic_session": self._is_diagnostic_session(session),
            "recent_messages": [
                self._serialize_recent_message(item) for item in (recent_messages or [])[-5:]
            ],
            "rule_result": {
                "route": rule_result.route,
                "confidence": rule_result.confidence,
                "reason": rule_result.reason,
                "certainty": rule_result.certainty,
                "clarify_message": rule_result.clarify_message,
                "signals": rule_result.signals,
            },
            "allowed_routes": list(ALLOWED_ROUTES),
            "required_output_keys": [
                "route",
                "confidence",
                "reason",
                "clarify_message",
                "needs_more_detail",
                "detected_signals",
            ],
        }
        return json.dumps(prompt_payload, ensure_ascii=False, indent=2)

    def _serialize_recent_message(self, message: Any) -> dict[str, Any]:
        if isinstance(message, dict):
            return {
                "role": message.get("role"),
                "content": message.get("content"),
            }

        return {
            "role": getattr(message, "role", None),
            "content": getattr(message, "content", str(message)),
        }

    def _is_diagnostic_session(self, session: Optional[Any]) -> bool:
        if not session or not getattr(session, "task", None):
            return False

        task = session.task
        return not (
            getattr(task, "source", None) == "general_chat"
            and getattr(task, "target", None) == "general_chat"
        )
