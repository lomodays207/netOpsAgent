"""
Pytest配置和全局fixtures
"""
import sys
from pathlib import Path

# 添加src目录到Python路径，以便导入模块
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
