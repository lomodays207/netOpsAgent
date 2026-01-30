"""
CMDB客户端

查询CMDB获取拓扑和设备信息（Phase 1使用Mock数据）
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

from ..models.topology import HostInfo, NetworkPath


class CMDBClient:
    """
    CMDB API客户端

    Phase 1实现：从Mock JSON文件读取数据
    Phase 2实现：调用真实CMDB API
    """

    def __init__(self, mock_data_path: Optional[str] = None):
        """
        初始化CMDB客户端

        Args:
            mock_data_path: Mock数据文件路径（Phase 1）
        """
        self.mock_data_path = mock_data_path or self._get_default_mock_path()
        self.mock_data = self._load_mock_data()

    def _get_default_mock_path(self) -> str:
        """获取默认Mock数据路径"""
        project_root = Path(__file__).parent.parent.parent
        return str(project_root / "tests" / "fixtures" / "mock_cmdb_data.json")

    def _load_mock_data(self) -> Dict:
        """加载Mock数据"""
        try:
            with open(self.mock_data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"警告: Mock数据文件不存在: {self.mock_data_path}")
            return {"servers": [], "switches": [], "topology": {}}

    def get_host_info(self, host: str) -> Optional[HostInfo]:
        """
        查询主机信息

        Args:
            host: 主机名或IP地址

        Returns:
            HostInfo对象，如果主机不存在则返回None
        """
        servers = self.mock_data.get("servers", [])

        for server in servers:
            if server["hostname"] == host or server["ip"] == host:
                return HostInfo(
                    ip=server["ip"],
                    hostname=server["hostname"],
                    leaf_switch=server["leaf_switch"],
                    rack=server["rack"],
                    status=server["status"],
                    tags=server.get("tags", [])
                )

        return None

    def get_network_path(self, source: str, target: str) -> Optional[NetworkPath]:
        """
        获取两台主机间的网络路径

        Args:
            source: 源主机名或IP
            target: 目标主机名或IP

        Returns:
            NetworkPath对象，如果路径不存在则返回None
        """
        # 获取源和目标主机信息
        source_info = self.get_host_info(source)
        target_info = self.get_host_info(target)

        if not source_info or not target_info:
            return None

        source_leaf = source_info.leaf_switch
        target_leaf = target_info.leaf_switch

        # 判断是否在同一个Leaf下
        same_leaf = (source_leaf == target_leaf)

        if same_leaf:
            # 同Leaf：不经过Spine
            return NetworkPath(
                source_leaf=source_leaf,
                target_leaf=target_leaf,
                same_leaf=True,
                spine_switches=[]
            )
        else:
            # 跨Leaf：需要经过Spine
            # 从Mock数据中查找拓扑路径
            topology_key = f"{source_info.hostname}_to_{target_info.hostname}"
            topology_data = self.mock_data.get("topology", {}).get(topology_key)

            if topology_data:
                path = topology_data.get("path", [])
                # 提取Spine交换机（path中leaf之间的设备）
                spine_switches = [device for device in path if 'spine' in device.lower()]
            else:
                # 默认使用spine-01
                spine_switches = ["spine-01"]

            return NetworkPath(
                source_leaf=source_leaf,
                target_leaf=target_leaf,
                same_leaf=False,
                spine_switches=spine_switches
            )

    def get_topology_details(self, source: str, target: str) -> Optional[Dict]:
        """
        获取详细的拓扑信息（包括设备详情）

        Args:
            source: 源主机名
            target: 目标主机名

        Returns:
            包含path和device_details的字典
        """
        source_info = self.get_host_info(source)
        target_info = self.get_host_info(target)

        if not source_info or not target_info:
            return None

        topology_key = f"{source_info.hostname}_to_{target_info.hostname}"
        topology_data = self.mock_data.get("topology", {}).get(topology_key)

        if topology_data:
            return {
                "path": topology_data.get("path", []),
                "device_details": topology_data.get("device_details", {})
            }

        return None

    def get_switch_info(self, switch_name: str) -> Optional[Dict]:
        """
        查询交换机信息

        Args:
            switch_name: 交换机名称

        Returns:
            交换机详情字典
        """
        switches = self.mock_data.get("switches", [])

        for switch in switches:
            if switch["name"] == switch_name:
                return switch

        return None

    def list_hosts(self) -> List[HostInfo]:
        """
        列出所有主机

        Returns:
            HostInfo对象列表
        """
        servers = self.mock_data.get("servers", [])
        return [
            HostInfo(
                ip=server["ip"],
                hostname=server["hostname"],
                leaf_switch=server["leaf_switch"],
                rack=server["rack"],
                status=server["status"],
                tags=server.get("tags", [])
            )
            for server in servers
        ]
