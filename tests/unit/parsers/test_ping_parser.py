"""
Ping解析器单元测试
"""
import pytest

from src.models.results import CommandResult
from src.utils.parsers.ping_parser import parse_ping_result


class TestParsePingResult:
    """Ping结果解析测试"""

    def test_ping_success(self):
        """测试Ping成功场景"""
        result = CommandResult(
            command="ping -c 4 -W 5 10.0.2.20",
            host="server1",
            success=True,
            stdout="""PING 10.0.2.20 (10.0.2.20) 56(84) bytes of data.
64 bytes from 10.0.2.20: icmp_seq=1 ttl=64 time=0.123 ms
64 bytes from 10.0.2.20: icmp_seq=2 ttl=64 time=0.089 ms
64 bytes from 10.0.2.20: icmp_seq=3 ttl=64 time=0.156 ms
64 bytes from 10.0.2.20: icmp_seq=4 ttl=64 time=0.102 ms

--- 10.0.2.20 ping statistics ---
4 packets transmitted, 4 received, 0% packet loss, time 3001ms
rtt min/avg/max/mdev = 0.089/0.125/0.234/0.052 ms""",
            stderr="",
            exit_code=0,
            execution_time=3.1
        )

        ping_result = parse_ping_result(result)

        assert ping_result.is_reachable is True
        assert ping_result.packets_transmitted == 4
        assert ping_result.packets_received == 4
        assert ping_result.packet_loss_percent == 0.0
        assert ping_result.rtt_avg == 0.125
        assert ping_result.rtt_min == 0.089
        assert ping_result.rtt_max == 0.234

    def test_ping_failed_100_loss(self):
        """测试Ping 100%丢包场景"""
        result = CommandResult(
            command="ping -c 4 -W 5 10.0.2.20",
            host="server1",
            success=False,
            stdout="""PING 10.0.2.20 (10.0.2.20) 56(84) bytes of data.

--- 10.0.2.20 ping statistics ---
4 packets transmitted, 0 received, 100% packet loss, time 3001ms""",
            stderr="",
            exit_code=1,
            execution_time=12.0
        )

        ping_result = parse_ping_result(result)

        assert ping_result.is_reachable is False
        assert ping_result.packets_transmitted == 4
        assert ping_result.packets_received == 0
        assert ping_result.packet_loss_percent == 100.0
        assert ping_result.rtt_avg is None

    def test_ping_partial_loss(self):
        """测试Ping部分丢包场景"""
        result = CommandResult(
            command="ping -c 4 -W 5 10.0.2.20",
            host="server1",
            success=True,
            stdout="""PING 10.0.2.20 (10.0.2.20) 56(84) bytes of data.
64 bytes from 10.0.2.20: icmp_seq=1 ttl=64 time=0.123 ms
64 bytes from 10.0.2.20: icmp_seq=3 ttl=64 time=0.156 ms

--- 10.0.2.20 ping statistics ---
4 packets transmitted, 2 received, 50% packet loss, time 3001ms
rtt min/avg/max/mdev = 0.123/0.139/0.156/0.016 ms""",
            stderr="",
            exit_code=0,
            execution_time=3.1
        )

        ping_result = parse_ping_result(result)

        assert ping_result.is_reachable is True
        assert ping_result.packet_loss_percent == 50.0
        assert ping_result.packets_received == 2

    def test_invalid_output(self):
        """测试无效输出场景"""
        result = CommandResult(
            command="ping invalid_host",
            host="server1",
            success=False,
            stdout="ping: invalid_host: Name or service not known",
            stderr="",
            exit_code=2,
            execution_time=0.01
        )

        ping_result = parse_ping_result(result)

        # 解析失败应返回100%丢包
        assert ping_result.is_reachable is False
        assert ping_result.packet_loss_percent == 100.0
