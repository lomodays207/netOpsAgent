"""
测试Mock数据随机返回机制

验证：
1. ss -tuln 命令能够正确匹配
2. 多次调用返回不同的随机结果
3. 不再出现 "Mock data not found" 错误
"""
import asyncio

from integrations.automation_platform_client import AutomationPlatformClient


async def test_random_responses():
    """测试随机返回机制"""
    print("=" * 60)
    print("测试Mock数据随机返回机制")
    print("=" * 60)
    
    client = AutomationPlatformClient()
    
    # 测试1: ss -tuln 命令匹配
    print("\n【测试1】验证 ss -tuln 命令匹配")
    print("-" * 60)
    for i in range(5):
        result = await client.execute('server2', "ss -tuln | grep ':80'")
        status = "✓ 成功" if result.success else "✗ 失败"
        has_output = "有输出" if result.stdout else "无输出"
        print(f"第 {i+1} 次: {status} | {has_output} | exit_code={result.exit_code}")
        if result.stdout:
            print(f"  输出: {result.stdout[:60]}...")
        if result.stderr and "Mock data not found" in result.stderr:
            print(f"  ❌ 错误: {result.stderr}")
    
    # 测试2: 多次调用验证随机性
    print("\n【测试2】验证随机性（统计端口存在/不存在的次数）")
    print("-" * 60)
    port_exists_count = 0
    port_not_exists_count = 0
    
    # 重置场景，测试随机返回
    client.current_scenario = None
    
    for i in range(10):
        result = await client.execute('test_device', "ss -tuln | grep ':80'")
        if result.stdout and "LISTEN" in result.stdout:
            port_exists_count += 1
        else:
            port_not_exists_count += 1
    
    print(f"端口存在: {port_exists_count} 次")
    print(f"端口不存在: {port_not_exists_count} 次")
    print(f"随机性验证: {'✓ 通过' if 0 < port_exists_count < 10 else '⚠ 可能需要多次测试'}")
    
    # 测试3: 测试未知命令的fallback机制
    print("\n【测试3】验证未知命令的fallback机制")
    print("-" * 60)
    unknown_commands = [
        "ip route show",
        "unknown_command_xyz",
        "custom_script.sh"
    ]
    
    for cmd in unknown_commands:
        result = await client.execute('test_device', cmd)
        has_error = "Mock data not found" in result.stderr
        status = "✓ 正常fallback" if not has_error else "✗ 出现错误"
        print(f"{status} | 命令: {cmd}")
        if has_error:
            print(f"  ❌ 错误: {result.stderr}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_random_responses())
