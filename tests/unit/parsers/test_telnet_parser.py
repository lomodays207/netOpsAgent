"""
Telnet解析器单元测试
"""
import pytest

from src.models.results import CommandResult
from src.utils.parsers.telnet_parser import detect_telnet_error_type


class TestDetectTelnetErrorType:
    """Telnet错误类型检测测试"""

    def test_connection_refused(self):
        """测试Connection Refused场景"""
        result = CommandResult(
            command="telnet 10.0.2.20 80",
            host="server1",
            success=False,
            stdout="",
            stderr="bash: connect: Connection refused\n/dev/tcp/10.0.2.20/80: Connection refused\nFAILED",
            exit_code=1,
            execution_time=0.1
        )

        telnet_result = detect_telnet_error_type(result)

        assert telnet_result.error_type == "refused"
        assert telnet_result.confidence >= 0.9
        assert "refused" in telnet_result.raw_output.lower()

    def test_connection_timeout(self):
        """测试Connection Timeout场景"""
        result = CommandResult(
            command="timeout 5 bash -c 'cat < /dev/tcp/10.0.2.20/80'",
            host="server1",
            success=False,
            stdout="",
            stderr="bash: connect: Connection timed out\nFAILED",
            exit_code=1,
            execution_time=5.2
        )

        telnet_result = detect_telnet_error_type(result)

        assert telnet_result.error_type == "timeout"
        assert telnet_result.confidence >= 0.9
        # 验证原始输出包含相关信息
        assert "timed out" in telnet_result.raw_output or "timeout" in telnet_result.raw_output.lower()

    def test_connection_success(self):
        """测试连接成功场景"""
        result = CommandResult(
            command="timeout 5 bash -c 'cat < /dev/tcp/10.0.2.20/80'",
            host="server1",
            success=True,
            stdout="SUCCESS",
            stderr="",
            exit_code=0,
            execution_time=0.05
        )

        telnet_result = detect_telnet_error_type(result)

        assert telnet_result.error_type == "success"
        assert telnet_result.confidence == 1.0

    def test_unknown_error(self):
        """测试未知错误场景"""
        result = CommandResult(
            command="telnet invalid_host 80",
            host="server1",
            success=False,
            stdout="",
            stderr="Temporary failure in name resolution",
            exit_code=1,
            execution_time=0.1
        )

        telnet_result = detect_telnet_error_type(result)

        assert telnet_result.error_type == "unknown"
        assert telnet_result.confidence < 0.9
