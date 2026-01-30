import sys
from pathlib import Path

# 添加项目根目录到sys.path以便导入
project_root = Path(__file__).parent
sys.path.append(str(project_root))

import asyncio
from src.integrations.automation_platform_client import AutomationPlatformClient

async def test_fix():
    print("开始测试 AutomationPlatformClient 修复...")
    client = AutomationPlatformClient()
    
    # 手动设置一个已知场景
    client.set_scenario("scenario1_refused")
    
    # 执行一个匹配的命令
    # 在 scenario1_refused 中，telnet_test 应该是存在的
    print("测试匹配命令 (telnet 10.0.1.10 80)...")
    try:
        result = await client.execute("10.0.1.10", "telnet 10.0.2.20 80")
        print(f"结果: success={result.success}, stdout='{result.stdout[:50]}...'")
        print("测试通过！没有发生 NameError.")
    except NameError as e:
        print(f"测试失败: 仍然发生 NameError: {e}")
    except Exception as e:
        print(f"测试发生意外错误: {e}")

if __name__ == "__main__":
    asyncio.run(test_fix())
