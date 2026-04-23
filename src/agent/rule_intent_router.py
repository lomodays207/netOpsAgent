"""Rule-based intent routing."""

from __future__ import annotations

import re
from typing import Any, Optional

from ..utils.input_validator import extract_endpoint_pair
from .intent_types import IntentDecision, RuleIntentResult


ACCESS_RELATION_RE = re.compile(
    r"(访问关系|哪些系统访问|谁访问|被哪些系统访问|之间.*访问关系)",
    re.IGNORECASE,
)
ACCESS_RELATION_KNOWLEDGE_RE = re.compile(
    r"(怎么|如何|为什么|什么是|是什么|步骤|原理|思路|办法|开权限|配置|申请|提单|权限|审批|必填|准备|流程)",
    re.IGNORECASE,
)
QUESTION_STYLE_RE = re.compile(
    r"(怎么|如何|为什么|什么是|是什么|哪些|步骤|原理|思路|办法|请问|\?)",
    re.IGNORECASE,
)
FAILURE_RE = re.compile(
    r"(不通|失败|超时|拒绝|访问不了|访问失败|无法访问|连不上|连不通|连接失败|timeout|refused|"
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
    """Route messages into diagnosis, continuation, clarify, or general chat."""

    def classify(self, message: str, session: Optional[Any] = None) -> RuleIntentResult:
        text = (message or "").strip()
        session_status = getattr(session, "status", None)

        if session_status == "waiting_user":
            return RuleIntentResult(
                route="continue_diagnosis",
                confidence=0.99,
                reason="session_waiting_user",
                certainty="hard",
            )

        signals = self._collect_signals(text, session)

        if signals["is_diagnostic_session"]:
            if signals["has_pair"] and (
                signals["has_failure"]
                or signals["has_tool_cmd"]
                or signals["has_actionable"]
                or signals["has_ip"]
            ):
                return RuleIntentResult(
                    route="start_diagnosis",
                    confidence=0.9,
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

        if signals["is_access_relation_query"]:
            return RuleIntentResult(
                route="general_chat",
                confidence=0.95,
                reason="access_relation_query",
                certainty="hard",
                signals=signals,
            )

        if signals["has_pair"] and (
            signals["has_failure"]
            or signals["has_tool_cmd"]
            or signals["has_actionable"]
            or signals["has_ip"]
        ):
            return RuleIntentResult(
                route="start_diagnosis",
                confidence=0.92,
                reason="structured_diagnosis_request",
                certainty="hard",
                signals=signals,
            )

        if signals["has_tool_cmd"] and signals["has_ip"]:
            return RuleIntentResult(
                route="start_diagnosis",
                confidence=0.86,
                reason="specific_diagnostic_command",
                certainty="hard",
                signals=signals,
            )

        if signals["has_question_style"]:
            return RuleIntentResult(
                route="general_chat",
                confidence=0.78,
                reason="general_network_question",
                certainty="soft",
                signals=signals,
            )

        if signals["has_failure"] and (signals["has_actionable"] or signals["has_live_issue"]):
            return RuleIntentResult(
                route="clarify",
                confidence=0.82,
                reason="issue_report_without_enough_details",
                certainty="soft",
                clarify_message=self._build_clarify_message(
                    has_pair=signals["has_pair"],
                    has_port_or_service=signals["has_port_or_service"],
                ),
                signals=signals,
            )

        if signals["has_failure"] and not signals["has_pair"]:
            return RuleIntentResult(
                route="clarify",
                confidence=0.7,
                reason="failure_signal_without_endpoints",
                certainty="soft",
                clarify_message=self._build_clarify_message(
                    has_pair=signals["has_pair"],
                    has_port_or_service=signals["has_port_or_service"],
                ),
                signals=signals,
            )

        if signals["has_tool_cmd"] or signals["has_port_or_service"]:
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

    def _collect_signals(self, text: str, session: Optional[Any]) -> dict[str, Any]:
        source, target = extract_endpoint_pair(text)
        return {
            "source": source,
            "target": target,
            "has_pair": self._has_specific_pair(source, target),
            "has_ip": bool(IP_RE.search(text)),
            "has_failure": bool(FAILURE_RE.search(text)),
            "has_actionable": bool(ACTIONABLE_RE.search(text)),
            "has_live_issue": bool(LIVE_ISSUE_RE.search(text)),
            "has_question_style": bool(QUESTION_STYLE_RE.search(text)),
            "has_tool_cmd": bool(TOOL_CMD_RE.search(text)),
            "has_port_or_service": bool(PORT_OR_SERVICE_RE.search(text)),
            "is_access_relation_query": bool(
                ACCESS_RELATION_RE.search(text)
                and not ACCESS_RELATION_KNOWLEDGE_RE.search(text)
            ),
            "is_diagnostic_session": self._is_diagnostic_session(session),
        }

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
                "请提供源主机、目标主机和实际故障现象。"
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
