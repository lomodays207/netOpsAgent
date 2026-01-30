"""
拓扑故障点识别单元测试
"""
import pytest

from src.utils.parsers.base import TracerouteHop, TracerouteResult
from src.utils.parsers.topology_parser import identify_failed_hop


class TestIdentifyFailedHop:
    """拓扑故障点识别测试"""

    def test_no_timeout_normal_path(self):
        """测试正常路径，无超时"""
        tr_result = TracerouteResult(
            target_ip="10.0.2.20",
            hops=[
                TracerouteHop(1, "10.0.1.1", "10.0.1.1", 0.5, False),
                TracerouteHop(2, "10.10.1.1", "10.10.1.1", 1.2, False),
                TracerouteHop(3, "10.0.2.1", "10.0.2.1", 1.5, False),
                TracerouteHop(4, "10.0.2.20", "10.0.2.20", 1.8, False),
            ],
            last_reachable_hop=TracerouteHop(4, "10.0.2.20", "10.0.2.20", 1.8, False),
            first_timeout_hop=None,
            is_complete=True
        )

        topology_path = ["server1", "leaf-01", "spine-01", "leaf-02", "server2"]
        device_details = {
            "leaf-01": {"ip": "10.0.1.1", "type": "leaf_switch"},
            "spine-01": {"ip": "10.10.1.1", "type": "spine_switch"},
            "leaf-02": {"ip": "10.0.2.1", "type": "leaf_switch"},
        }

        result = identify_failed_hop(tr_result, topology_path, device_details)

        assert result.failed_hop_number == 0
        assert result.failed_device_name is None
        assert result.failed_device_type == "none"
        assert result.confidence == 1.0

    def test_failed_at_leaf_switch(self):
        """测试Leaf交换机故障"""
        tr_result = TracerouteResult(
            target_ip="10.0.2.20",
            hops=[
                TracerouteHop(1, "10.0.1.1", "10.0.1.1", 0.5, False),
                TracerouteHop(2, "10.10.1.1", "10.10.1.1", 1.2, False),
                TracerouteHop(3, None, None, None, True),
                TracerouteHop(4, None, None, None, True),
            ],
            last_reachable_hop=TracerouteHop(2, "10.10.1.1", "10.10.1.1", 1.2, False),
            first_timeout_hop=3,
            is_complete=False
        )

        topology_path = ["server1", "leaf-01", "spine-01", "leaf-02", "server2"]
        device_details = {
            "leaf-01": {"ip": "10.0.1.1", "type": "leaf_switch"},
            "spine-01": {"ip": "10.10.1.1", "type": "spine_switch"},
            "leaf-02": {"ip": "10.0.2.1", "type": "leaf_switch"},
        }

        result = identify_failed_hop(tr_result, topology_path, device_details)

        assert result.failed_hop_number == 3
        assert result.failed_device_name == "leaf-02"
        assert result.failed_device_type == "leaf_switch"
        assert result.last_reachable_ip == "10.10.1.1"
        assert result.confidence >= 0.8
        assert "leaf-02" in result.reasoning

    def test_failed_at_spine_switch(self):
        """测试Spine交换机故障"""
        tr_result = TracerouteResult(
            target_ip="10.0.2.20",
            hops=[
                TracerouteHop(1, "10.0.1.1", "10.0.1.1", 0.5, False),
                TracerouteHop(2, None, None, None, True),
                TracerouteHop(3, None, None, None, True),
            ],
            last_reachable_hop=TracerouteHop(1, "10.0.1.1", "10.0.1.1", 0.5, False),
            first_timeout_hop=2,
            is_complete=False
        )

        topology_path = ["server1", "leaf-01", "spine-01", "leaf-02", "server2"]
        device_details = {
            "leaf-01": {"ip": "10.0.1.1", "type": "leaf_switch"},
            "spine-01": {"ip": "10.10.1.1", "type": "spine_switch"},
            "leaf-02": {"ip": "10.0.2.1", "type": "leaf_switch"},
        }

        result = identify_failed_hop(tr_result, topology_path, device_details)

        assert result.failed_hop_number == 2
        assert result.failed_device_name == "spine-01"
        assert result.failed_device_type == "spine_switch"
        assert result.last_reachable_ip == "10.0.1.1"

    def test_unknown_device_no_cmdb_match(self):
        """测试无法匹配CMDB的场景"""
        tr_result = TracerouteResult(
            target_ip="10.0.2.20",
            hops=[
                TracerouteHop(1, "192.168.1.1", "192.168.1.1", 0.5, False),
                TracerouteHop(2, None, None, None, True),
            ],
            last_reachable_hop=TracerouteHop(1, "192.168.1.1", "192.168.1.1", 0.5, False),
            first_timeout_hop=2,
            is_complete=False
        )

        topology_path = ["server1", "leaf-01", "spine-01", "leaf-02", "server2"]
        device_details = {
            "leaf-01": {"ip": "10.0.1.1", "type": "leaf_switch"},
            "spine-01": {"ip": "10.10.1.1", "type": "spine_switch"},
            "leaf-02": {"ip": "10.0.2.1", "type": "leaf_switch"},
        }

        result = identify_failed_hop(tr_result, topology_path, device_details)

        assert result.failed_hop_number == 2
        assert result.failed_device_name is None
        assert result.failed_device_type == "unknown"
        assert result.confidence == 0.5
        assert "无法在CMDB拓扑中找到" in result.reasoning
