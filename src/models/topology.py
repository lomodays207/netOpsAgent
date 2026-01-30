"""
网络拓扑相关数据模型
定义主机信息和网络路径
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class HostInfo:
    """
    主机信息

    从CMDB查询得到的主机详细信息
    """
    ip: str                             # IP地址
    hostname: str                       # 主机名
    leaf_switch: str                    # 所属Leaf交换机
    rack: str                           # 机架位置
    status: str                         # 状态（online/offline/maintenance）
    tags: List[str] = field(default_factory=list)  # 标签（如k8s_node, database等）

    def __str__(self) -> str:
        return f"{self.hostname} ({self.ip}) @ {self.leaf_switch}"

    def is_online(self) -> bool:
        """检查主机是否在线"""
        return self.status == "online"


@dataclass
class NetworkPath:
    """
    网络路径

    描述源主机到目标主机的网络拓扑路径
    在Spine-Leaf架构中特别重要
    """
    source_leaf: str                    # 源主机所属Leaf交换机
    target_leaf: str                    # 目标主机所属Leaf交换机
    same_leaf: bool                     # 是否在同一个Leaf下
    spine_switches: List[str] = field(default_factory=list)  # 经过的Spine交换机（如果跨Leaf）
    estimated_hops: int = 0             # 预估跳数

    def __post_init__(self):
        """初始化后计算跳数"""
        if self.same_leaf:
            # 同Leaf: 源主机 → Leaf → 目标主机
            self.estimated_hops = 2
        else:
            # 跨Leaf: 源主机 → Leaf-01 → Spine-01 → Leaf-02 → 目标主机
            self.estimated_hops = 4 + len(self.spine_switches) - 1

    def __str__(self) -> str:
        if self.same_leaf:
            return f"{self.source_leaf} (same leaf)"
        else:
            spine_str = " → ".join(self.spine_switches)
            return f"{self.source_leaf} → {spine_str} → {self.target_leaf}"

    def get_path_description(self) -> str:
        """获取路径的详细描述"""
        if self.same_leaf:
            return f"源主机和目标主机在同一个Leaf交换机({self.source_leaf})下，预估{self.estimated_hops}跳"
        else:
            return (f"跨Leaf通信：{self.source_leaf} → "
                   f"{' → '.join(self.spine_switches)} → {self.target_leaf}，"
                   f"预估{self.estimated_hops}跳")
