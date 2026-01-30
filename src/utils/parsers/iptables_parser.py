"""
Iptables规则解析器

解析iptables规则，识别是否有阻断特定端口的规则
"""
import re

from ...models.results import CommandResult
from .base import IptablesRuleMatch


def parse_iptables_rules(
    result: CommandResult,
    port: int,
    chain: str = "INPUT"
) -> IptablesRuleMatch:
    """
    解析iptables输出，检查是否有阻断特定端口的规则

    Args:
        result: 命令执行结果
        port: 目标端口号
        chain: 链名称（INPUT | OUTPUT）

    Returns:
        IptablesRuleMatch: 规则匹配结果

    示例输入:
        Chain INPUT (policy DROP)
        pkts bytes target  prot opt in  out  source      destination
        100  6000  ACCEPT  tcp  --  *   *   0.0.0.0/0   0.0.0.0/0   tcp dpt:22
          0     0  DROP    tcp  --  *   *   0.0.0.0/0   0.0.0.0/0   tcp dpt:80

    解析逻辑:
        1. 提取链的默认策略（policy）
        2. 查找匹配目标端口的规则
        3. 判断是DROP/REJECT还是ACCEPT
    """
    stdout = result.stdout

    # 提取默认策略
    # 格式: Chain INPUT (policy DROP)
    policy_pattern = rf"Chain {chain} \(policy (DROP|ACCEPT|REJECT)\)"
    policy_match = re.search(policy_pattern, stdout, re.IGNORECASE)
    policy = policy_match.group(1).upper() if policy_match else "ACCEPT"

    # 查找匹配端口的规则
    # 格式: 0  0  DROP  tcp  --  *  *  0.0.0.0/0  0.0.0.0/0  tcp dpt:80
    rule_pattern = rf"(DROP|REJECT|ACCEPT)\s+tcp\s+--.*?tcp dpt:{port}"
    rule_match = re.search(rule_pattern, stdout, re.IGNORECASE | re.MULTILINE)

    if rule_match:
        action = rule_match.group(1).upper()
        rule_line = rule_match.group(0)

        # 有明确的DROP或REJECT规则
        if action in ["DROP", "REJECT"]:
            return IptablesRuleMatch(
                has_blocking_rule=True,
                rule_action=action,
                rule_line=rule_line,
                policy=policy
            )
        # 有ACCEPT规则，说明端口被放行
        elif action == "ACCEPT":
            return IptablesRuleMatch(
                has_blocking_rule=False,
                rule_action=action,
                rule_line=rule_line,
                policy=policy
            )

    # 没有明确规则，判断默认策略
    if policy == "DROP":
        return IptablesRuleMatch(
            has_blocking_rule=True,
            rule_action=policy,
            rule_line=None,
            policy=policy
        )
    else:
        return IptablesRuleMatch(
            has_blocking_rule=False,
            rule_action=None,
            rule_line=None,
            policy=policy
        )
