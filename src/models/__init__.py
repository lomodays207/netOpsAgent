"""
数据模型包
提供所有核心数据结构的导入
"""
from .report import DiagnosticReport
from .results import CommandResult, StepResult
from .task import DiagnosticTask, FaultType, Protocol
from .topology import HostInfo, NetworkPath

__all__ = [
    # 枚举类型
    "Protocol",
    "FaultType",
    # 任务相关
    "DiagnosticTask",
    # 拓扑相关
    "HostInfo",
    "NetworkPath",
    # 结果相关
    "CommandResult",
    "StepResult",
    # 报告相关
    "DiagnosticReport",
]
