"""
网络路由器

根据主机IP自动路由到对应网络段的AutomationPlatformClient
支持多网络环境隔离
"""
import ipaddress
from typing import Dict, Optional, List
from dataclasses import dataclass


@dataclass
class NetworkConfig:
    """网络配置"""
    name: str
    api_url: str
    api_token: str
    networks: List[str]  # CIDR格式，如 ["10.0.0.0/8", "192.168.0.0/16"]


class NetworkRouter:
    """
    网络路由器

    根据主机IP网段自动选择对应的AutomationPlatformClient
    实现多网络环境隔离和分布式命令执行
    """

    def __init__(self):
        self.networks: Dict[str, NetworkConfig] = {}
        self.clients: Dict[str, 'AutomationPlatformClient'] = {}

    def register_network(self, config: NetworkConfig):
        """
        注册网络配置

        Args:
            config: 网络配置
        """
        self.networks[config.name] = config
        # 创建对应的客户端
        from .automation_platform_client import AutomationPlatformClient
        self.clients[config.name] = AutomationPlatformClient(
            api_url=config.api_url,
            api_token=config.api_token
        )

    def find_client_for_host(self, host: str) -> Optional['AutomationPlatformClient']:
        """
        根据主机IP找到对应的AutomationPlatformClient

        Args:
            host: 主机IP或主机名

        Returns:
            AutomationPlatformClient实例，如果找不到返回None
        """
        network_name = self._find_network_for_host(host)
        if network_name:
            return self.clients.get(network_name)
        return None

    def _find_network_for_host(self, host: str) -> Optional[str]:
        """
        根据主机IP找到对应的网络名称

        Args:
            host: 主机IP或主机名

        Returns:
            网络名称，如果找不到返回None
        """
        # 尝试解析为IP地址
        try:
            host_ip = ipaddress.ip_address(host)
        except ValueError:
            # 不是IP地址，可能是主机名，使用默认网络
            return self._get_default_network()

        # 遍历所有网络，找到匹配的
        for network_name, config in self.networks.items():
            for network_cidr in config.networks:
                network = ipaddress.ip_network(network_cidr)
                if host_ip in network:
                    return network_name

        # 找不到匹配的，使用默认网络
        return self._get_default_network()

    def _get_default_network(self) -> Optional[str]:
        """获取默认网络（第一个注册的）"""
        if self.networks:
            return list(self.networks.keys())[0]
        return None

    def get_client(self, network_name: str) -> 'AutomationPlatformClient':
        """
        获取指定网络的客户端

        Args:
            network_name: 网络名称

        Returns:
            AutomationPlatformClient实例
        """
        return self.clients.get(network_name)


# 全局路由器实例
_router = NetworkRouter()


def get_router() -> NetworkRouter:
    """获取全局路由器"""
    return _router
