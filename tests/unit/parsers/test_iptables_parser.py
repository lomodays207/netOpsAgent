"""
Iptables解析器单元测试
"""
import pytest

from src.models.results import CommandResult
from src.utils.parsers.iptables_parser import parse_iptables_rules


class TestParseIptablesRules:
    """Iptables规则解析测试"""

    def test_explicit_drop_rule(self):
        """测试明确的DROP规则"""
        result = CommandResult(
            command="iptables -L INPUT -n -v",
            host="server2",
            success=True,
            stdout="""Chain INPUT (policy ACCEPT)
pkts bytes target  prot opt in  out  source      destination
100  6000  ACCEPT  tcp  --  *   *   0.0.0.0/0   0.0.0.0/0   tcp dpt:22
  0     0  DROP    tcp  --  *   *   0.0.0.0/0   0.0.0.0/0   tcp dpt:80""",
            stderr="",
            exit_code=0,
            execution_time=0.05
        )

        match = parse_iptables_rules(result, 80, "INPUT")

        assert match.has_blocking_rule is True
        assert match.rule_action == "DROP"
        assert match.policy == "ACCEPT"
        assert "tcp dpt:80" in match.rule_line

    def test_accept_rule(self):
        """测试ACCEPT规则"""
        result = CommandResult(
            command="iptables -L INPUT -n -v",
            host="server2",
            success=True,
            stdout="""Chain INPUT (policy DROP)
pkts bytes target  prot opt in  out  source      destination
100  6000  ACCEPT  tcp  --  *   *   0.0.0.0/0   0.0.0.0/0   tcp dpt:80
  0     0  ACCEPT  tcp  --  *   *   0.0.0.0/0   0.0.0.0/0   tcp dpt:22""",
            stderr="",
            exit_code=0,
            execution_time=0.05
        )

        match = parse_iptables_rules(result, 80, "INPUT")

        assert match.has_blocking_rule is False
        assert match.rule_action == "ACCEPT"
        assert match.policy == "DROP"

    def test_default_policy_drop(self):
        """测试默认策略为DROP且无明确规则"""
        result = CommandResult(
            command="iptables -L INPUT -n -v",
            host="server2",
            success=True,
            stdout="""Chain INPUT (policy DROP)
pkts bytes target  prot opt in  out  source      destination
100  6000  ACCEPT  tcp  --  *   *   0.0.0.0/0   0.0.0.0/0   tcp dpt:22""",
            stderr="",
            exit_code=0,
            execution_time=0.05
        )

        match = parse_iptables_rules(result, 80, "INPUT")

        assert match.has_blocking_rule is True
        assert match.rule_action == "DROP"
        assert match.policy == "DROP"
        assert match.rule_line is None  # 无明确规则

    def test_default_policy_accept(self):
        """测试默认策略为ACCEPT且无明确规则"""
        result = CommandResult(
            command="iptables -L INPUT -n -v",
            host="server2",
            success=True,
            stdout="""Chain INPUT (policy ACCEPT)
pkts bytes target  prot opt in  out  source      destination""",
            stderr="",
            exit_code=0,
            execution_time=0.05
        )

        match = parse_iptables_rules(result, 80, "INPUT")

        assert match.has_blocking_rule is False
        assert match.rule_action is None
        assert match.policy == "ACCEPT"

    def test_reject_rule(self):
        """测试REJECT规则"""
        result = CommandResult(
            command="iptables -L INPUT -n -v",
            host="server2",
            success=True,
            stdout="""Chain INPUT (policy ACCEPT)
pkts bytes target  prot opt in  out  source      destination
  0     0  REJECT  tcp  --  *   *   0.0.0.0/0   0.0.0.0/0   tcp dpt:80 reject-with icmp-port-unreachable""",
            stderr="",
            exit_code=0,
            execution_time=0.05
        )

        match = parse_iptables_rules(result, 80, "INPUT")

        assert match.has_blocking_rule is True
        assert match.rule_action == "REJECT"
