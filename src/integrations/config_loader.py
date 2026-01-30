"""
网络配置加载器

从YAML配置文件加载网络配置并注册到NetworkRouter
"""
import os
import yaml
from pathlib import Path
from typing import Optional

from .network_router import NetworkRouter, NetworkConfig, get_router


def load_network_config(config_path: Optional[str] = None) -> NetworkRouter:
    """
    加载网络配置

    Args:
        config_path: 配置文件路径，如果为None则使用默认路径

    Returns:
        配置好的NetworkRouter

    Raises:
        FileNotFoundError: 配置文件不存在
        yaml.YAMLError: 配置文件格式错误
    """
    if config_path is None:
        # 默认配置文件路径
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "config" / "networks.yaml"

    # 检查配置文件是否存在
    if not Path(config_path).exists():
        raise FileNotFoundError(f"网络配置文件不存在: {config_path}")

    # 读取配置文件
    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = yaml.safe_load(f)

    # 注册所有网络
    router = get_router()
    for network_config in config_data.get('networks', []):
        # 替换环境变量
        api_token = network_config['api_token']
        if api_token.startswith('${') and api_token.endswith('}'):
            env_var = api_token[2:-1]
            api_token = os.getenv(env_var, '')

        config = NetworkConfig(
            name=network_config['name'],
            api_url=network_config['api_url'],
            api_token=api_token,
            networks=network_config['networks']
        )
        router.register_network(config)

    return router
