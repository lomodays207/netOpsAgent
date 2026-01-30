"""
测试 netOpsAgent API 的 Python 脚本
"""
import requests
import json

# API 地址
API_URL = "http://127.0.0.1:8000/api/v1/diagnose"

# 测试请求
test_request = {
    "description": "10.0.1.10到10.0.2.20端口80不通",
    "use_llm": True,
    "verbose": False
}

print("=" * 60)
print("测试 netOpsAgent API")
print("=" * 60)
print(f"\n请求: {json.dumps(test_request, ensure_ascii=False, indent=2)}\n")
print("发送请求中...")

try:
    # 发送 POST 请求
    response = requests.post(API_URL, json=test_request, timeout=120)

    # 检查响应
    if response.status_code == 200:
        result = response.json()

        print("\n" + "=" * 60)
        print("✅ 诊断成功")
        print("=" * 60)
        print(f"\n任务ID: {result['task_id']}")
        print(f"状态: {result['status']}")
        print(f"\n根因: {result['root_cause']}")
        print(f"置信度: {result['confidence']:.1f}%")
        print(f"执行时间: {result['execution_time']:.2f}秒")

        print(f"\n执行步骤 ({len(result['steps'])} 个):")
        for step in result['steps']:
            status = "✅" if step['success'] else "❌"
            print(f"  {status} Step {step['step']}: {step['name']}")
            if step['command']:
                print(f"     命令: {step['command']}")

        print(f"\n修复建议:")
        for i, suggestion in enumerate(result['suggestions'], 1):
            print(f"  {i}. {suggestion}")

    else:
        print(f"\n❌ 请求失败: {response.status_code}")
        print(response.text)

except requests.exceptions.Timeout:
    print("\n❌ 请求超时（诊断时间较长，建议增加 timeout）")
except requests.exceptions.ConnectionError:
    print("\n❌ 连接失败，请确保 API 服务已启动")
    print("   启动命令: .venv\\Scripts\\uvicorn.exe src.api:app --host 127.0.0.1 --port 8000")
except Exception as e:
    print(f"\n❌ 发生错误: {e}")

print("\n" + "=" * 60)
