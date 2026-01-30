"""
Traceroute输出解析器

解析traceroute输出，识别网络路径和断点位置
"""
import re
from typing import List, Optional

from ...models.results import CommandResult
from .base import TracerouteHop, TracerouteResult


def parse_traceroute_output(result: CommandResult) -> TracerouteResult:
    """
    解析traceroute输出

    Args:
        result: 命令执行结果

    Returns:
        TracerouteResult: 包含所有跳点和分析结果

    示例输入:
        traceroute to 10.0.2.20 (10.0.2.20), 30 hops max, 60 byte packets
         1  10.0.1.1 (10.0.1.1)  0.512 ms  0.389 ms  0.301 ms
         2  10.10.1.1 (10.10.1.1)  1.234 ms  1.123 ms  1.089 ms
         3  * * *
         4  * * *
         5  * * *

    解析逻辑:
        1. 提取目标IP
        2. 逐行解析每一跳
        3. 识别第一个超时的hop
        4. 记录最后一个可达的hop
    """
    stdout = result.stdout

    # 提取目标IP
    # 格式: traceroute to 10.0.2.20 (10.0.2.20)
    target_pattern = r"traceroute to ([\d.]+)"
    target_match = re.search(target_pattern, stdout)
    target_ip = target_match.group(1) if target_match else ""

    # 解析每一跳
    hops: List[TracerouteHop] = []
    last_reachable_hop: Optional[TracerouteHop] = None
    first_timeout_hop: Optional[int] = None

    # 格式: 1  10.0.1.1 (10.0.1.1)  0.512 ms  0.389 ms  0.301 ms
    hop_pattern = r"^\s*(\d+)\s+([\d.]+)\s+\(([\d.]+)\)\s+([\d.]+)\s+ms"
    # 超时格式: 3  * * *
    timeout_pattern = r"^\s*(\d+)\s+\*\s+\*\s+\*"

    lines = stdout.split('\n')
    for line in lines:
        # 解析正常hop
        hop_match = re.match(hop_pattern, line)
        if hop_match:
            hop_number = int(hop_match.group(1))
            ip_address = hop_match.group(2)
            hostname = hop_match.group(3)
            rtt_ms = float(hop_match.group(4))

            hop = TracerouteHop(
                hop_number=hop_number,
                ip_address=ip_address,
                hostname=hostname,
                rtt_ms=rtt_ms,
                is_timeout=False
            )
            hops.append(hop)
            last_reachable_hop = hop
            continue

        # 解析超时hop
        timeout_match = re.match(timeout_pattern, line)
        if timeout_match:
            hop_number = int(timeout_match.group(1))
            hop = TracerouteHop(
                hop_number=hop_number,
                ip_address=None,
                hostname=None,
                rtt_ms=None,
                is_timeout=True
            )
            hops.append(hop)

            # 记录第一个超时的hop
            if first_timeout_hop is None:
                first_timeout_hop = hop_number

    # 判断是否到达目标
    is_complete = False
    if last_reachable_hop and last_reachable_hop.ip_address == target_ip:
        is_complete = True

    return TracerouteResult(
        target_ip=target_ip,
        hops=hops,
        last_reachable_hop=last_reachable_hop,
        first_timeout_hop=first_timeout_hop,
        is_complete=is_complete
    )
