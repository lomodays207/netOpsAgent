"""
Telnet错误类型解析器

判断telnet失败是Connection Refused还是Connection Timeout
"""
import re

from ...models.results import CommandResult
from .base import TelnetErrorType


def detect_telnet_error_type(result: CommandResult) -> TelnetErrorType:
    """
    解析telnet命令的失败类型

    Args:
        result: 命令执行结果

    Returns:
        TelnetErrorType: 包含错误类型、置信度和原始输出

    示例输入:
        - stderr: "Connection refused"
        - stderr: "Connection timed out"
        - stderr: "Temporary failure in name resolution"

    返回类型:
        - refused: 网络通，端口未监听
        - timeout: 网络不通或防火墙阻断
        - success: 连接成功
        - unknown: 无法判断（如DNS解析失败）
    """
    combined_output = result.stdout + result.stderr

    # 规则1: Connection refused 或 Connection reset by peer
    refused_patterns = [
        r"connection refused",
        r"connection reset by peer",
        r"no route to host",  # 某些情况下也表示refused
    ]
    for pattern in refused_patterns:
        if re.search(pattern, combined_output, re.IGNORECASE):
            return TelnetErrorType(
                error_type="refused",
                confidence=0.95,
                raw_output=combined_output
            )

    # 规则2: Timeout 相关
    timeout_patterns = [
        r"connection timed out",
        r"timeout",
        r"no response",
    ]
    for pattern in timeout_patterns:
        if re.search(pattern, combined_output, re.IGNORECASE):
            return TelnetErrorType(
                error_type="timeout",
                confidence=0.95,
                raw_output=combined_output
            )

    # 规则3: 使用bash的/dev/tcp测试的成功情况
    if result.exit_code == 0 and "SUCCESS" in combined_output:
        return TelnetErrorType(
            error_type="success",
            confidence=1.0,
            raw_output=combined_output
        )

    # 规则4: 未知错误（如DNS解析失败）
    return TelnetErrorType(
        error_type="unknown",
        confidence=0.5,
        raw_output=combined_output
    )
