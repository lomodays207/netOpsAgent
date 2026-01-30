# API 工具调用历史功能说明

## 功能概述

API 现在会在响应中包含 `tool_calls` 字段，显示 LLM 在诊断过程中使用的所有工具及其执行结果。

---

## 响应示例

```json
{
  "task_id": "task_20260123150551_09459c15",
  "status": "success",
  "root_cause": "目标主机防火墙阻断80端口",
  "confidence": 80.0,
  "execution_time": 8.35,

  "tool_calls": [
    {
      "step": 1,
      "tool": "execute_command",
      "arguments": {
        "command": "ping -c 4 10.0.2.20",
        "host": "10.0.1.10"
      },
      "result_summary": {
        "success": true,
        "execution_time": 3.125,
        "stdout": "PING 10.0.2.20 (10.0.2.20) 56(84) bytes of data...",
        "stderr": ""
      }
    },
    {
      "step": 1,
      "tool": "execute_command",
      "arguments": {
        "command": "telnet 10.0.2.20 80",
        "host": "10.0.1.10",
        "timeout": 5
      },
      "result_summary": {
        "success": true,
        "execution_time": 5.012,
        "stdout": "",
        "stderr": "bash: connect: Connection timed out\nFAILED"
      }
    },
    {
      "step": 2,
      "tool": "execute_command",
      "arguments": {
        "command": "ss -tlnp | grep :80",
        "host": "10.0.2.20"
      },
      "result_summary": {
        "success": true,
        "execution_time": 0.091,
        "stdout": "tcp   LISTEN  0   128   *:80   *:*   users:((\"nginx\",pid=1234,fd=6))",
        "stderr": ""
      }
    },
    {
      "step": 2,
      "tool": "execute_command",
      "arguments": {
        "command": "iptables -L -n | grep -E \"DROP|REJECT\"",
        "host": "10.0.2.20"
      },
      "result_summary": {
        "success": true,
        "execution_time": 0.123,
        "stdout": "Chain INPUT (policy DROP)...\nDROP tcp -- * * 0.0.0.0/0 0.0.0.0/0 tcp dpt:80",
        "stderr": ""
      }
    }
  ],

  "steps": [...],
  "suggestions": [...]
}
```

---

## 字段说明

### `tool_calls` 数组

每个工具调用包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `step` | int | 诊断步骤编号 |
| `tool` | string | 使用的工具名称（如 `execute_command`, `query_cmdb`） |
| `arguments` | object | 传递给工具的参数 |
| `result_summary` | object | 工具执行结果摘要 |

### `result_summary` 对象

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | boolean | 工具是否执行成功 |
| `execution_time` | float | 执行耗时（秒） |
| `stdout` | string | 标准输出（截取前200字符） |
| `stderr` | string | 错误输出（截取前200字符） |

---

## 使用场景

### 1. 调试诊断逻辑
```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/diagnose",
    json={"description": "10.0.1.10到10.0.2.20端口80不通", "use_llm": True}
)

result = response.json()

# 查看 LLM 使用了哪些工具
for tool_call in result['tool_calls']:
    print(f"Step {tool_call['step']}: {tool_call['tool']}")
    print(f"  命令: {tool_call['arguments'].get('command')}")
    print(f"  耗时: {tool_call['result_summary']['execution_time']}秒")
```

### 2. 可视化诊断流程
前端可以基于 `tool_calls` 渲染诊断流程图，展示：
- LLM 的决策路径
- 每一步执行的命令
- 命令的输出结果
- 执行耗时

### 3. 审计和日志记录
保存完整的工具调用历史用于：
- 故障复盘
- 性能分析
- 合规审计

---

## 实现细节

### 修改的文件

1. **`src/agent/llm_agent.py`**
   - 在 `_generate_report()` 方法中保存工具调用历史到 `metadata`

2. **`src/api.py`**
   - 响应模型添加 `tool_calls` 字段
   - 从 `report.metadata` 中提取并返回工具调用历史

### 数据流

```
LLM Agent 诊断
    ↓
保存工具调用到 context[]
    ↓
生成报告时存入 metadata['tool_call_history']
    ↓
API 提取 metadata 并返回 tool_calls
    ↓
前端/客户端展示诊断过程
```

---

## 测试方式

### 使用 curl
```bash
curl -X POST http://localhost:8000/api/v1/diagnose \
  -H "Content-Type: application/json" \
  -d @test_request.json | python -m json.tool
```

### 使用 Python
```bash
python test_tool_calls.py
```

### 使用 Postman
1. 访问 http://localhost:8000/docs
2. 展开 `/api/v1/diagnose` 接口
3. 点击 "Try it out"
4. 输入测试数据并执行
5. 查看响应中的 `tool_calls` 字段

---

## 注意事项

1. **输出截断**：`stdout` 和 `stderr` 字段会截取前200字符，避免响应过大
2. **仅在使用 LLM 时返回**：如果 `use_llm=false`，`tool_calls` 可能为空
3. **性能影响**：工具调用历史会增加响应大小，但开销很小（通常 < 2KB）

---

## 后续优化建议

1. **添加过滤选项**：允许客户端选择是否返回 `tool_calls`
2. **详细程度控制**：支持 `tool_call_detail` 参数控制返回的详细程度
3. **实时流式输出**：使用 Server-Sent Events (SSE) 实时推送工具调用进度

---

**版本**: 1.0.0
**更新日期**: 2026-01-23
