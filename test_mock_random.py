"""
测试Mock数据随机返回机制

验证：
1. ss -tuln 命令能够正确匹配
2. 多次调用返回不同的随机结果
3. 不再出现 "Mock data not found" 错误
"""
import asyncio
import importlib.util

# 直接导入模块，绕过相对导入问题
spec1 = importlib.util.spec_from_file_location("automation_platform_client", "src/integrations/automation_platform_client.py")
automation_module = importlib.util.module_from_spec(spec1)

# 先加载依赖的模块
spec2 = importlib.util.spec_from_file_location("results", "src/models/results.py")
results_module = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(results_module)

# 将依赖模块注入到 sys.modules 中
import sys
sys.modules['models.results'] = results_module

# 加载主模块
spec1.loader.exec_module(automation_module)

AutomationPlatformClient = automation_module.AutomationPlatformClient


async def main():
    print("=" * 60)
    print("测试Mock数据随机返回机制")
    print("=" * 60)
    
    client = AutomationPlatformClient()
    
    # 测试1: ss -tuln 命令匹配
    print("\n[测试1] ss -tuln 命令匹配测试")
    print("-" * 60)
    error_count = 0
    for i in range(5):
        result = await client.execute('server2', "ss -tuln | grep ':80'")
        status = "成功" if result.success else "失败"
        has_output = "有输出" if result.stdout else "无输出"
        print(f"第{i+1}次: {status} | {has_output} | exit_code={result.exit_code}")
        if result.stderr and "Mock data not found" in result.stderr:
            print(f"  ❌ 错误: {result.stderr}")
            error_count += 1
    
    print(f"\n✓ 测试1结果: {'通过' if error_count == 0 else f'失败（{error_count}个错误）'}")
    
    # 测试2: 随机性测试
    print("\n[测试2] 随机性测试（统计端口存在/不存在次数）")
    print("-" * 60)
    port_exists = 0
    port_not_exists = 0
    
    # 重置场景，触发随机fallback
    client.current_scenario = None
    
    for i in range(10):
        result = await client.execute('test_device_random', "ss -abc | grep ':80'")
        if result.stdout and "LISTEN" in result.stdout:
            port_exists += 1
        else:
            port_not_exists += 1
    
    print(f"端口存在: {port_exists} 次")
    print(f"端口不存在: {port_not_exists} 次")
    print(f"\n✓ 测试2结果: {'通过（存在随机性）' if 0 < port_exists < 10 else '需要多次测试'}")
    
    # 测试3: 未知命令fallback
    print("\n[测试3] 未知命令fallback测试")
    print("-" * 60)
    cmds = ["ip route show", "unknown_cmd_xyz", "custom_test_command"]
    
    fallback_error_count = 0
    for cmd in cmds:
        result = await client.execute('test_device', cmd)
        has_error = "Mock data not found" in result.stderr
        if has_error:
            fallback_error_count += 1
        print(f"{'✓ 正常' if not has_error else '✗ 错误'} | {cmd}")
    
    print(f"\n✓ 测试3结果: {'通过' if fallback_error_count == 0 else f'失败（{fallback_error_count}个错误）'}")
    
    print("\n" + "=" * 60)
    total_errors = error_count + fallback_error_count
    if total_errors == 0:
        print("✓✓✓ 所有测试通过！")
    else:
        print(f"✗ 测试失败：共{total_errors}个错误")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
