"""
网络拓扑故障点识别

根据traceroute结果和CMDB拓扑信息，识别故障节点的类型和名称
"""
from typing import Any, Dict

from .base import FailedHopIdentification, TracerouteResult


def identify_failed_hop(
    traceroute_result: TracerouteResult,
    topology_path: list,
    device_details: Dict[str, Any]
) -> FailedHopIdentification:
    """
    根据traceroute结果和CMDB拓扑推断故障节点

    Args:
        traceroute_result: Traceroute解析结果
        topology_path: CMDB拓扑路径（设备名称列表）
        device_details: 设备详情字典 {设备名: {ip, type, ...}}

    Returns:
        FailedHopIdentification: 故障节点识别结果

    推断逻辑:
        1. 找到最后可达的hop IP
        2. 在CMDB拓扑中查找该IP对应的设备
        3. 推断下一个节点（超时的hop）是什么设备
        4. 根据Spine-Leaf架构规则推断设备类型

    示例:
        - 最后可达: 10.10.1.1 (spine-01)
        - 第一个超时: hop 3
        - 拓扑路径: [leaf-01, spine-01, leaf-02, server2]
        - 推断: leaf-02故障
    """
    if not traceroute_result.first_timeout_hop:
        # 没有超时，网络正常
        return FailedHopIdentification(
            failed_hop_number=0,
            failed_device_name=None,
            failed_device_type="none",
            last_reachable_ip=None,
            confidence=1.0,
            reasoning="Traceroute完成，未发现超时节点"
        )

    last_reachable_ip = None
    if traceroute_result.last_reachable_hop:
        last_reachable_ip = traceroute_result.last_reachable_hop.ip_address

    # 在拓扑中查找最后可达IP对应的设备
    last_reachable_device = None
    for i, device in enumerate(topology_path):
        device_info = device_details.get(device)
        if device_info and device_info.get('ip') == last_reachable_ip:
            last_reachable_device = device
            # 推断下一个设备
            if i + 1 < len(topology_path):
                failed_device = topology_path[i + 1]
                failed_device_info = device_details.get(failed_device)

                # 判断设备类型
                device_type = "unknown"
                if failed_device_info:
                    if 'leaf' in failed_device.lower():
                        device_type = "leaf_switch"
                    elif 'spine' in failed_device.lower():
                        device_type = "spine_switch"
                    elif 'server' in failed_device.lower():
                        device_type = "server"

                return FailedHopIdentification(
                    failed_hop_number=traceroute_result.first_timeout_hop,
                    failed_device_name=failed_device,
                    failed_device_type=device_type,
                    last_reachable_ip=last_reachable_ip,
                    confidence=0.85,
                    reasoning=f"基于CMDB拓扑，最后可达设备{last_reachable_device}，下一跳应为{failed_device}"
                )

    # 无法匹配CMDB拓扑，返回未知
    return FailedHopIdentification(
        failed_hop_number=traceroute_result.first_timeout_hop,
        failed_device_name=None,
        failed_device_type="unknown",
        last_reachable_ip=last_reachable_ip,
        confidence=0.5,
        reasoning="无法在CMDB拓扑中找到匹配的设备，建议手动排查"
    )
