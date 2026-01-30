"""
任务相关数据模型
定义故障排查任务的核心数据结构
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class Protocol(str, Enum):
    """网络协议枚举"""
    ICMP = "icmp"
    TCP = "tcp"
    UDP = "udp"


class FaultType(str, Enum):
    """故障类型枚举"""
    CONNECTIVITY = "connectivity"        # 连通性故障
    PORT_UNREACHABLE = "port_unreachable"  # 端口不可达
    SLOW = "slow"                        # 响应慢
    DNS = "dns"                          # DNS故障


@dataclass
class DiagnosticTask:
    """
    故障排查任务

    核心数据结构，描述一个完整的排查任务
    """
    task_id: str                         # 唯一任务ID
    user_input: str                      # 原始用户输入
    source: str                          # 源主机（IP或主机名）
    target: str                          # 目标主机（IP或主机名）
    protocol: Protocol                   # 网络协议
    fault_type: FaultType                # 故障类型
    created_at: datetime = field(default_factory=datetime.now)
    port: Optional[int] = None           # 端口号（如果是TCP/UDP）
    context: Dict[str, Any] = field(default_factory=dict)  # 额外上下文信息

    def __str__(self) -> str:
        """任务的字符串表示"""
        if self.port:
            return (f"[{self.task_id}] {self.source} → {self.target}:{self.port} "
                   f"({self.protocol.value}) - {self.fault_type.value}")
        return (f"[{self.task_id}] {self.source} → {self.target} "
               f"({self.protocol.value}) - {self.fault_type.value}")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "task_id": self.task_id,
            "user_input": self.user_input,
            "source": self.source,
            "target": self.target,
            "protocol": self.protocol.value,
            "fault_type": self.fault_type.value,
            "port": self.port,
            "created_at": self.created_at.isoformat(),
            "context": self.context
        }
