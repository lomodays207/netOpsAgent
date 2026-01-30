"""
解析器基类和通用数据结构

定义所有解析器共用的数据结构和抽象基类
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class TelnetErrorType:
    """Telnet错误类型解析结果"""
    error_type: str                    # "refused" | "timeout" | "success" | "unknown"
    confidence: float                  # 0-1
    raw_output: str


@dataclass
class PortListeningStatus:
    """端口监听状态"""
    is_listening: bool
    process_name: Optional[str] = None # 监听该端口的进程名
    pid: Optional[int] = None          # 进程ID
    bind_address: str = ""             # 绑定的地址（0.0.0.0 或特定IP）


@dataclass
class PingResult:
    """Ping命令结果"""
    packets_transmitted: int
    packets_received: int
    packet_loss_percent: float
    rtt_min: Optional[float] = None    # ms
    rtt_avg: Optional[float] = None    # ms
    rtt_max: Optional[float] = None    # ms
    is_reachable: bool = False


@dataclass
class IptablesRuleMatch:
    """Iptables规则匹配结果"""
    has_blocking_rule: bool
    rule_action: Optional[str] = None  # "DROP" | "REJECT" | "ACCEPT"
    rule_line: Optional[str] = None    # 匹配的规则原始行
    policy: str = "ACCEPT"             # 链的默认策略 (DROP/ACCEPT)


@dataclass
class TracerouteHop:
    """Traceroute单个跳点"""
    hop_number: int
    ip_address: Optional[str]          # None表示超时（* * *）
    hostname: Optional[str]
    rtt_ms: Optional[float]            # 第一次RTT
    is_timeout: bool


@dataclass
class TracerouteResult:
    """Traceroute完整结果"""
    target_ip: str
    hops: List[TracerouteHop]
    last_reachable_hop: Optional[TracerouteHop] = None
    first_timeout_hop: Optional[int] = None  # 第一个超时的hop编号
    is_complete: bool = False          # 是否到达目标


@dataclass
class FailedHopIdentification:
    """故障跳点识别结果"""
    failed_hop_number: int
    failed_device_name: Optional[str]  # 从CMDB推断的设备名
    failed_device_type: str            # "leaf_switch" | "spine_switch" | "server" | "unknown"
    last_reachable_ip: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""                # 推断理由


class ParseError(Exception):
    """解析错误异常"""
    def __init__(self, message: str, raw_output: str = ""):
        super().__init__(message)
        self.raw_output = raw_output
