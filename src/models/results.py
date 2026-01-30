"""
执行结果相关数据模型
定义命令执行结果和排查步骤结果
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class CommandResult:
    """
    命令执行结果

    记录单个命令在特定主机上的执行结果
    """
    command: str                        # 执行的命令
    host: str                           # 执行命令的主机
    success: bool                       # 是否执行成功
    stdout: str                         # 标准输出
    stderr: str                         # 标准错误输出
    exit_code: int                      # 退出码
    execution_time: float               # 执行耗时（秒）
    timestamp: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        status = "✅" if self.success else "❌"
        return (f"{status} [{self.host}] {self.command} "
               f"(exit={self.exit_code}, time={self.execution_time:.2f}s)")

    @classmethod
    def from_api_response(cls, response: Dict[str, Any]) -> "CommandResult":
        """
        从自动化平台API响应创建CommandResult

        Args:
            response: API响应字典，格式如下:
                {
                    "success": true,
                    "device": "server1",
                    "command": "ping -c 4 10.0.2.20",
                    "stdout": "PING 10.0.2.20...",
                    "stderr": "",
                    "exit_code": 0,
                    "execution_time": 0.523,
                    "timestamp": "2026-01-13T10:30:00Z"
                }
        """
        return cls(
            command=response.get("command", ""),
            host=response.get("device", ""),
            success=response.get("success", False),
            stdout=response.get("stdout", ""),
            stderr=response.get("stderr", ""),
            exit_code=response.get("exit_code", -1),
            execution_time=response.get("execution_time", 0.0),
            timestamp=datetime.fromisoformat(response.get("timestamp", datetime.now().isoformat()))
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "command": self.command,
            "host": self.host,
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class StepResult:
    """
    排查步骤结果

    记录排查流程中单个步骤的执行情况
    """
    step_number: int                    # 步骤编号
    step_name: str                      # 步骤名称
    action: str                         # 动作类型（execute_command/query_cmdb/analyze等）
    success: bool                       # 步骤是否成功
    command_result: Optional[CommandResult] = None  # 命令执行结果（如果是命令执行）
    next_step: Optional[int] = None     # 下一步编号（根据结果决定）
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据（解析结果、分析结论等）

    def __str__(self) -> str:
        status = "✅" if self.success else "❌"
        return f"{status} Step {self.step_number}: {self.step_name}"

    def get_summary(self) -> str:
        """获取步骤的摘要信息"""
        summary = f"Step {self.step_number}: {self.step_name} ({self.action})\n"
        if self.command_result:
            summary += f"  命令: {self.command_result.command}\n"
            summary += f"  主机: {self.command_result.host}\n"
            summary += f"  结果: {'成功' if self.success else '失败'}\n"
            summary += f"  耗时: {self.command_result.execution_time:.2f}s\n"
        if self.metadata:
            summary += f"  元数据: {self.metadata}\n"
        if self.next_step:
            summary += f"  下一步: Step {self.next_step}\n"
        return summary

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "step_number": self.step_number,
            "step_name": self.step_name,
            "action": self.action,
            "success": self.success,
            "command_result": self.command_result.to_dict() if self.command_result else None,
            "next_step": self.next_step,
            "metadata": self.metadata
        }


# 注意：DiagnosticReport 已在 src/models/report.py 中定义
# 这里不再重复定义，避免冲突



