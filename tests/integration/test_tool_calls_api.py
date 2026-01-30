"""
测试 API 的工具调用历史显示功能
"""
import requests
import json

# API 地址
API_URL = "http://127.0.0.1:8000/api/v1/diagnose"

# 测试请求
test_request = {
    "description": "10.0.1.10到10.0.2.20端口80不通",
    "use_llm": True,
    "verbose": False  # 不需要详细输出，工具调用历史会自动返回
}

print("=" * 80)
print("测试 netOpsAgent API - 显示 LLM 工具调用历史")
print("=" * 80)
print(f"\n请求: {json.dumps(test_request, ensure_ascii=False, indent=2)}\n")
print("发送请求中...\n")

try:
    # 发送 POST 请求
    response = requests.post(API_URL, json=test_request, timeout=120)

    # 检查响应
    if response.status_code == 200:
        result = response.json()

        print("=" * 80)
        print("诊断结果")
        print("=" * 80)
        print(f"\n任务ID: {result['task_id']}")
        print(f"状态: {result['status']}")
        print(f"\n根因: {result['root_cause']}")
        print(f"置信度: {result['confidence']:.1f}%")
        print(f"执行时间: {result['execution_time']:.2f}秒")

        # 显示工具调用历史（新功能）
        if result.get('tool_calls'):
            print("\n" + "=" * 80)
            print("LLM 工具调用历史（分析过程）")
            print("=" * 80)

            for idx, tool_call in enumerate(result['tool_calls'], 1):
                print(f"\n[Step {tool_call['step']}] 工具调用 #{idx}")
                print(f"  工具名称: {tool_call['tool']}")
                print(f"  参数:")
                for key, value in tool_call['arguments'].items():
                    print(f"    - {key}: {value}")

                result_summary = tool_call['result_summary']
                status_icon = "✅" if result_summary['success'] else "❌"
                print(f"  执行结果: {status_icon}")
                print(f"  耗时: {result_summary['execution_time']:.2f}秒")

                if result_summary.get('stdout'):
                    print(f"  输出: {result_summary['stdout'][:100]}...")
                if result_summary.get('stderr'):
                    print(f"  错误: {result_summary['stderr'][:100]}...")
        else:
            print("\n未找到工具调用历史")

        # 显示修复建议
        print(f"\n" + "=" * 80)
        print("修复建议")
        print("=" * 80)
        for i, suggestion in enumerate(result['suggestions'], 1):
            print(f"{i}. {suggestion}")

    else:
        print(f"\n请求失败: {response.status_code}")
        print(response.text)

except requests.exceptions.Timeout:
    print("\n请求超时")
except requests.exceptions.ConnectionError:
    print("\n连接失败，请确保 API 服务已启动")
except Exception as e:
    print(f"\n发生错误: {e}")

print("\n" + "=" * 80)
