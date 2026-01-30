"""
Ping结果解析器

解析ping命令输出，提取丢包率、延迟等信息
"""
import re

from ...models.results import CommandResult
from .base import PingResult


def parse_ping_result(result: CommandResult) -> PingResult:
    """
    解析ping命令输出

    Args:
        result: 命令执行结果

    Returns:
        PingResult: 包含丢包率、RTT等统计信息

    示例输入:
        PING 10.0.2.20 (10.0.2.20) 56(84) bytes of data.
        64 bytes from 10.0.2.20: icmp_seq=1 ttl=64 time=0.123 ms
        64 bytes from 10.0.2.20: icmp_seq=2 ttl=64 time=0.089 ms

        --- 10.0.2.20 ping statistics ---
        4 packets transmitted, 4 received, 0% packet loss, time 3001ms
        rtt min/avg/max/mdev = 0.089/0.125/0.234/0.052 ms
    """
    stdout = result.stdout

    # 解析丢包率行
    # 格式: 4 packets transmitted, 4 received, 0% packet loss
    loss_pattern = r"(\d+) packets transmitted, (\d+) received, ([\d.]+)% packet loss"
    loss_match = re.search(loss_pattern, stdout)

    if not loss_match:
        # 解析失败，返回默认值（假设100%丢包）
        return PingResult(
            packets_transmitted=0,
            packets_received=0,
            packet_loss_percent=100.0,
            rtt_min=None,
            rtt_avg=None,
            rtt_max=None,
            is_reachable=False
        )

    transmitted = int(loss_match.group(1))
    received = int(loss_match.group(2))
    loss_percent = float(loss_match.group(3))

    # 解析RTT行（如果有）
    # 格式: rtt min/avg/max/mdev = 0.089/0.125/0.234/0.052 ms
    rtt_pattern = r"rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)"
    rtt_match = re.search(rtt_pattern, stdout)

    if rtt_match:
        rtt_min = float(rtt_match.group(1))
        rtt_avg = float(rtt_match.group(2))
        rtt_max = float(rtt_match.group(3))
    else:
        rtt_min = rtt_avg = rtt_max = None

    return PingResult(
        packets_transmitted=transmitted,
        packets_received=received,
        packet_loss_percent=loss_percent,
        rtt_min=rtt_min,
        rtt_avg=rtt_avg,
        rtt_max=rtt_max,
        is_reachable=(loss_percent < 100.0)
    )
