"""
Traceroute解析器单元测试
"""
import pytest

from src.models.results import CommandResult
from src.utils.parsers.traceroute_parser import parse_traceroute_output


class TestParseTracerouteOutput:
    """Traceroute输出解析测试"""

    def test_traceroute_complete(self):
        """测试Traceroute完整到达目标的场景"""
        result = CommandResult(
            command="traceroute 10.0.2.20 -m 30 -w 3",
            host="server1",
            success=True,
            stdout="""traceroute to 10.0.2.20 (10.0.2.20), 30 hops max, 60 byte packets
 1  10.0.1.1 (10.0.1.1)  0.512 ms  0.389 ms  0.301 ms
 2  10.10.1.1 (10.10.1.1)  1.234 ms  1.123 ms  1.089 ms
 3  10.0.2.1 (10.0.2.1)  1.567 ms  1.456 ms  1.389 ms
 4  10.0.2.20 (10.0.2.20)  1.789 ms  1.678 ms  1.567 ms""",
            stderr="",
            exit_code=0,
            execution_time=5.0
        )

        tr_result = parse_traceroute_output(result)

        assert tr_result.target_ip == "10.0.2.20"
        assert tr_result.is_complete is True
        assert len(tr_result.hops) == 4
        assert tr_result.first_timeout_hop is None
        assert tr_result.last_reachable_hop.ip_address == "10.0.2.20"
        assert tr_result.last_reachable_hop.hop_number == 4

    def test_traceroute_broken_path(self):
        """测试Traceroute中途断开的场景"""
        result = CommandResult(
            command="traceroute 10.0.2.20 -m 30 -w 3",
            host="server1",
            success=False,
            stdout="""traceroute to 10.0.2.20 (10.0.2.20), 30 hops max, 60 byte packets
 1  10.0.1.1 (10.0.1.1)  0.512 ms  0.389 ms  0.301 ms
 2  10.10.1.1 (10.10.1.1)  1.234 ms  1.123 ms  1.089 ms
 3  * * *
 4  * * *
 5  * * *""",
            stderr="",
            exit_code=0,
            execution_time=30.0
        )

        tr_result = parse_traceroute_output(result)

        assert tr_result.target_ip == "10.0.2.20"
        assert tr_result.is_complete is False
        assert len(tr_result.hops) == 5
        assert tr_result.first_timeout_hop == 3
        assert tr_result.last_reachable_hop.ip_address == "10.10.1.1"
        assert tr_result.last_reachable_hop.hop_number == 2

        # 检查超时hop
        timeout_hop = tr_result.hops[2]  # hop 3
        assert timeout_hop.is_timeout is True
        assert timeout_hop.ip_address is None
        assert timeout_hop.rtt_ms is None

    def test_traceroute_immediate_timeout(self):
        """测试第一跳就超时的场景"""
        result = CommandResult(
            command="traceroute 10.0.2.20 -m 30 -w 3",
            host="server1",
            success=False,
            stdout="""traceroute to 10.0.2.20 (10.0.2.20), 30 hops max, 60 byte packets
 1  * * *
 2  * * *
 3  * * *""",
            stderr="",
            exit_code=0,
            execution_time=9.0
        )

        tr_result = parse_traceroute_output(result)

        assert tr_result.target_ip == "10.0.2.20"
        assert tr_result.is_complete is False
        assert tr_result.first_timeout_hop == 1
        assert tr_result.last_reachable_hop is None

    def test_traceroute_partial_recovery(self):
        """测试中间有超时但后续恢复的场景"""
        result = CommandResult(
            command="traceroute 10.0.2.20 -m 30 -w 3",
            host="server1",
            success=True,
            stdout="""traceroute to 10.0.2.20 (10.0.2.20), 30 hops max, 60 byte packets
 1  10.0.1.1 (10.0.1.1)  0.512 ms  0.389 ms  0.301 ms
 2  * * *
 3  10.0.2.1 (10.0.2.1)  1.567 ms  1.456 ms  1.389 ms
 4  10.0.2.20 (10.0.2.20)  1.789 ms  1.678 ms  1.567 ms""",
            stderr="",
            exit_code=0,
            execution_time=8.0
        )

        tr_result = parse_traceroute_output(result)

        assert tr_result.target_ip == "10.0.2.20"
        assert tr_result.is_complete is True  # 最终到达了目标
        assert tr_result.first_timeout_hop == 2  # 第一个超时是hop 2
        assert tr_result.last_reachable_hop.ip_address == "10.0.2.20"
