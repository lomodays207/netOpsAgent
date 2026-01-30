"""
网络诊断工具

提供网络诊断相关的工具函数，用于LLM Agent调用
"""
from typing import Optional, List, Dict

from .automation_platform_client import AutomationPlatformClient
from .network_router import get_router
from ..models.results import CommandResult


class NetworkTools:
    """
    网络诊断工具集

    封装网络诊断相关的业务逻辑，支持多网络环境路由
    """

    def __init__(
        self,
        default_client: Optional[AutomationPlatformClient] = None,
        use_router: bool = True
    ):
        """
        初始化网络工具

        Args:
            default_client: 默认的AutomationPlatformClient（如果不使用router）
            use_router: 是否使用NetworkRouter进行网络路由
        """
        self.default_client = default_client or AutomationPlatformClient()
        self.use_router = use_router
        self.router = get_router() if use_router else None

    def _get_client_for_host(self, host: str) -> AutomationPlatformClient:
        """
        获取指定主机的客户端

        如果启用router且找到对应网络的client，则使用该client
        否则使用default_client

        Args:
            host: 主机IP或主机名

        Returns:
            AutomationPlatformClient实例
        """
        if self.use_router and self.router:
            client = self.router.find_client_for_host(host)
            if client:
                return client

        return self.default_client

    async def execute_command(
        self,
        host: str,
        command: str,
        timeout: int = 30
    ) -> Dict:
        """
        在指定主机上执行命令

        通过自动化平台API在远程主机上执行命令，用于网络诊断。
        支持多网络环境，自动路由到对应的API。

        Args:
            host: 目标主机IP或主机名（例如：10.0.1.10, web-server-01）
            command: 要执行的命令（例如：timeout 5 bash -c 'cat < /dev/tcp/10.0.2.20/80'）
            timeout: 超时时间（秒），默认30秒

        Returns:
            dict: 命令执行结果
                {
                    "success": bool,      # 命令是否执行成功
                    "stdout": str,        # 标准输出
                    "stderr": str,        # 标准错误输出
                    "exit_code": int,     # 退出码
                    "host": str,          # 执行命令的主机
                    "command": str,       # 执行的命令
                    "execution_time": float  # 执行耗时（秒）
                }

        Examples:
            >>> tools = NetworkTools()
            >>> # 测试端口连通性
            >>> result = await tools.execute_command(
            ...     host="10.0.1.10",
            ...     command="timeout 5 bash -c 'cat < /dev/tcp/10.0.2.20/80'"
            ... )
            >>> # 检查端口监听状态
            >>> result = await tools.execute_command(
            ...     host="10.0.2.20",
            ...     command="ss -tlnp | grep ':80'"
            ... )
        """
        try:
            # 获取对应的client
            client = self._get_client_for_host(host)

            # 调用自动化平台API执行命令
            result: CommandResult = await client.execute(
                device=host,
                command=command,
                timeout=timeout
            )

            # 转换为标准化的字典格式返回给LLM
            return {
                "success": result.success,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
                "host": result.host,
                "command": result.command,
                "execution_time": result.execution_time
            }

        except Exception as e:
            # 捕获异常并返回错误信息
            return {
                "success": False,
                "stdout": "",
                "stderr": f"执行命令时发生错误: {str(e)}",
                "exit_code": -1,
                "host": host,
                "command": command,
                "execution_time": 0.0
            }

    async def query_cmdb(self, hosts: List[str]) -> Dict:
        """
        查询CMDB获取主机信息

        从配置管理数据库(CMDB)查询主机的详细信息，包括IP地址、主机名、所属业务等。

        Args:
            hosts: 主机列表（IP或主机名）

        Returns:
            dict: 主机信息
                {
                    "success": bool,
                    "hosts": [
                        {
                            "hostname": str,
                            "ip": str,
                            "business": str,
                            "status": str
                        }
                    ]
                }

        Examples:
            >>> tools = NetworkTools()
            >>> result = await tools.query_cmdb(["10.0.1.10", "web-server-01"])
        """
        # TODO: Phase 2实现真实CMDB查询
        # 目前返回Mock数据
        return {
            "success": True,
            "hosts": [
                {
                    "hostname": host,
                    "ip": host if host.replace(".", "").isdigit() else "unknown",
                    "business": "unknown",
                    "status": "active"
                }
                for host in hosts
            ]
        }

    async def query_firewall_policy(
        self,
        host: str,
        port: int,
        source_ip: Optional[str] = None
    ) -> Dict:
        """
        查询防火墙/安全组策略

        检查指定主机上的防火墙或安全组是否放行了特定端口。

        Args:
            host: 目标主机名或IP
            port: 要检查的端口
            source_ip: 源IP地址（可选，用于检查特定源的放行规则）

        Returns:
            dict: 策略查询结果
                {
                    "success": bool,       # 查询是否成功
                    "policy_exists": bool, # 放行策略是否存在
                    "policy_type": str,    # 策略类型: iptables/security_group/firewalld
                    "rules": list,         # 匹配的规则列表
                    "blocking_rule": str,  # 如果被阻止，阻止规则详情
                    "suggestion": str      # 修复建议
                }
        """
        import random
        
        # Mock: 随机返回策略开放或未开放
        policy_exists = random.choice([True, False])
        
        if policy_exists:
            return {
                "success": True,
                "policy_exists": True,
                "policy_type": random.choice(["iptables", "security_group", "firewalld"]),
                "rules": [
                    {
                        "rule_id": "rule-001",
                        "action": "ACCEPT",
                        "protocol": "tcp",
                        "port": port,
                        "source": source_ip or "0.0.0.0/0"
                    }
                ],
                "blocking_rule": None,
                "suggestion": None
            }
        else:
            policy_type = random.choice(["iptables", "security_group", "firewalld"])
            return {
                "success": True,
                "policy_exists": False,
                "policy_type": policy_type,
                "rules": [],
                "blocking_rule": f"Chain INPUT (policy DROP) 或 安全组默认拒绝TCP {port}端口",
                "suggestion": f"在{policy_type}中添加放行规则: 允许TCP {port}端口入站"
            }

    async def query_gateway(self, target_ip: str) -> Dict:
        """
        查询目标IP的网关地址

        通过CMDB或网络配置查询指定IP所在网段的网关地址。

        Args:
            target_ip: 目标IP地址

        Returns:
            dict: 网关信息
                {
                    "success": bool,
                    "gateway_ip": str,      # 网关IP地址
                    "gateway_device": str,  # 网关设备名称
                    "network_segment": str, # 所属网段
                    "vlan": str            # VLAN ID
                }
        """
        import random
        
        # Mock: 根据目标IP生成网关地址
        ip_parts = target_ip.split(".")
        if len(ip_parts) == 4:
            gateway_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.1"
            network_segment = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"
        else:
            gateway_ip = "10.0.0.1"
            network_segment = "10.0.0.0/24"
        
        return {
            "success": True,
            "gateway_ip": gateway_ip,
            "gateway_device": random.choice(["leaf-01", "leaf-02", "leaf-03"]),
            "network_segment": network_segment,
            "vlan": f"VLAN{random.randint(100, 999)}"
        }

    async def ping_gateway(
        self,
        source_host: str,
        gateway_ip: str
    ) -> Dict:
        """
        从源主机ping网关地址

        Args:
            source_host: 源主机
            gateway_ip: 网关IP地址

        Returns:
            dict: ping结果
                {
                    "success": bool,       # 是否能ping通
                    "packet_loss": float,  # 丢包率
                    "rtt_avg": float,      # 平均延迟(ms)
                    "stdout": str,         # 原始ping输出
                }
        """
        import random
        
        # Mock: 随机返回ping成功或失败
        is_reachable = random.choice([True, True, False])  # 2/3概率成功
        
        if is_reachable:
            rtt = round(random.uniform(0.1, 2.0), 3)
            return {
                "success": True,
                "packet_loss": 0.0,
                "rtt_avg": rtt,
                "stdout": f"PING {gateway_ip}: 4 packets transmitted, 4 received, 0% packet loss\nrtt avg = {rtt} ms"
            }
        else:
            return {
                "success": False,
                "packet_loss": 100.0,
                "rtt_avg": 0,
                "stdout": f"PING {gateway_ip}: 4 packets transmitted, 0 received, 100% packet loss"
            }

    async def query_network_device_policy(
        self,
        device_name: str,
        target_network: str
    ) -> Dict:
        """
        查询网络设备（交换机/路由器）的路由和ACL策略

        登录指定网络设备，检查到目标网段的路由和访问控制策略。

        Args:
            device_name: 网络设备名称（如 spine-01, leaf-02）
            target_network: 目标网段或IP

        Returns:
            dict: 策略查询结果
                {
                    "success": bool,
                    "device_type": str,       # 设备类型: spine/leaf/router
                    "vendor": str,            # 设备厂商
                    "route_exists": bool,     # 是否存在到目标的路由
                    "route_info": dict,       # 路由详情
                    "acl_blocking": bool,     # 是否有ACL阻止
                    "acl_rules": list,        # ACL规则列表
                    "interface_status": str,  # 接口状态
                    "suggestion": str         # 修复建议
                }
        """
        import random
        
        # Mock: 随机生成网络设备策略查询结果
        device_type = "spine" if "spine" in device_name.lower() else "leaf"
        vendor = random.choice(["Cisco", "Arista", "Huawei", "Juniper"])
        
        # 随机决定问题类型
        problem_type = random.choice(["route_missing", "acl_blocking", "interface_down", "no_issue"])
        
        if problem_type == "route_missing":
            return {
                "success": True,
                "device_type": device_type,
                "vendor": vendor,
                "route_exists": False,
                "route_info": None,
                "acl_blocking": False,
                "acl_rules": [],
                "interface_status": "up",
                "suggestion": f"在{device_name}上添加到{target_network}的静态路由或检查BGP邻居状态"
            }
        elif problem_type == "acl_blocking":
            return {
                "success": True,
                "device_type": device_type,
                "vendor": vendor,
                "route_exists": True,
                "route_info": {
                    "destination": target_network,
                    "next_hop": "10.10.10.1",
                    "interface": "Ethernet1/1"
                },
                "acl_blocking": True,
                "acl_rules": [
                    {"name": "ACL-DENY-ALL", "action": "deny", "destination": target_network}
                ],
                "interface_status": "up",
                "suggestion": f"修改ACL规则，允许到{target_network}的流量"
            }
        elif problem_type == "interface_down":
            return {
                "success": True,
                "device_type": device_type,
                "vendor": vendor,
                "route_exists": True,
                "route_info": {
                    "destination": target_network,
                    "next_hop": "10.10.10.1",
                    "interface": "Ethernet1/1"
                },
                "acl_blocking": False,
                "acl_rules": [],
                "interface_status": "down",
                "suggestion": f"检查{device_name}的Ethernet1/1接口状态，可能是物理链路故障"
            }
        else:
            return {
                "success": True,
                "device_type": device_type,
                "vendor": vendor,
                "route_exists": True,
                "route_info": {
                    "destination": target_network,
                    "next_hop": "10.10.10.1",
                    "interface": "Ethernet1/1",
                    "metric": 10
                },
                "acl_blocking": False,
                "acl_rules": [],
                "interface_status": "up",
                "suggestion": None
            }

    async def analyze_traceroute(
        self,
        traceroute_output: str,
        cmdb_topology: Optional[Dict] = None
    ) -> Dict:
        """
        分析traceroute输出，识别断点位置

        Args:
            traceroute_output: traceroute命令的输出
            cmdb_topology: CMDB中的拓扑信息（可选）

        Returns:
            dict: 分析结果
                {
                    "success": bool,
                    "is_complete": bool,        # traceroute是否到达目标
                    "total_hops": int,          # 总跳数
                    "last_reachable_hop": dict, # 最后可达的跳
                    "first_timeout_hop": int,   # 第一个超时的跳数
                    "failed_device": str,       # 推断的故障设备名称
                    "failed_device_ip": str,    # 故障设备IP
                    "analysis": str             # 分析说明
                }
        """
        import random
        import re
        
        # 解析traceroute输出
        lines = traceroute_output.strip().split("\n")
        hops = []
        first_timeout = None
        last_reachable = None
        
        for line in lines[1:]:  # 跳过第一行header
            # 匹配 hop 行: " 1  10.0.1.1 (10.0.1.1)  0.512 ms"  
            match = re.match(r'\s*(\d+)\s+(\S+)', line)
            if match:
                hop_num = int(match.group(1))
                hop_addr = match.group(2)
                
                if hop_addr == "*":
                    if first_timeout is None:
                        first_timeout = hop_num
                else:
                    last_reachable = {
                        "hop": hop_num,
                        "ip": hop_addr.strip("()")
                    }
                    hops.append(last_reachable)
        
        # 推断故障设备
        failed_device = None
        if first_timeout and cmdb_topology:
            path = cmdb_topology.get("path", [])
            if first_timeout <= len(path):
                failed_device = path[first_timeout - 1]
        
        if not failed_device:
            failed_device = random.choice(["leaf-02", "spine-01", "router-core"])
        
        return {
            "success": True,
            "is_complete": first_timeout is None,
            "total_hops": len(hops),
            "last_reachable_hop": last_reachable,
            "first_timeout_hop": first_timeout,
            "failed_device": failed_device,
            "failed_device_ip": last_reachable["ip"] if last_reachable else None,
            "analysis": f"Traceroute在第{first_timeout}跳超时，推断故障设备为{failed_device}" if first_timeout else "Traceroute正常完成"
        }

