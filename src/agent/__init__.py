"""
Agent鏍稿績妯″潡

鎻愪緵浠诲姟瑙勫垝銆佹墽琛屻€佸垎鏋愬拰鎶ュ憡鐢熸垚鍔熻兘
"""
from __future__ import annotations

import importlib

from .analyzer import DiagnosticAnalyzer
from .executor import Executor
from .intent_router import IntentRouter, RuleIntentRouter, build_intent_router
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
    "build_intent_router",
    "HybridIntentRouter",
    "NLU",
]


def __getattr__(name: str):
    if name == "HybridIntentRouter":
        module = importlib.import_module(".hybrid_intent_router", __name__)
        value = module.HybridIntentRouter
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
