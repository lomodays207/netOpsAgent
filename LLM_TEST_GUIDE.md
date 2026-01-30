# LLM测试运行指南

## 快速开始

### 1. 运行完整测试套件
```bash
python test_llm_e2e.py
```

包含3个测试：
- 测试1: 8个真实LLM调用测试（不同场景）
- 测试2: 端到端工作流测试
- 测试3: LLM指标收集测试

---

## 分步运行（可选）

如果你只想测试某个功能，可以修改 `test_llm_e2e.py` 的 `main()` 函数：

### 只测试LLM解析准确性
```python
# 在 main() 中只保留这一行
results['llm_real_call'] = test_llm_real_call()
```

### 只测试端到端流程
```python
results['e2e_workflow'] = test_e2e_workflow()
```

### 只测试性能指标
```python
results['llm_metrics'] = test_llm_metrics()
```

---

## 使用CLI测试真实场景

### 1. 测试预定义场景（使用LLM）
```bash
python -m src.cli test scenario1_refused --use-llm
```

### 2. 测试自定义输入（使用LLM）
```bash
python -m src.cli diagnose "我们的应用服务器连不上数据库了" --use-llm
```

### 3. 对比规则引擎 vs LLM
```bash
# 规则引擎模式
python -m src.cli diagnose "server1到server2端口80不通" --scenario scenario1_refused

# LLM增强模式
python -m src.cli diagnose "server1到server2端口80不通" --scenario scenario1_refused --use-llm
```

---

## 验证新模型是否生效

### 快速验证
```bash
# 运行最简单的测试
python -c "
from dotenv import load_dotenv
load_dotenv()
import os
from src.integrations.llm_client import LLMClient

print('API配置:')
print(f'  BASE_URL: {os.getenv(\"API_BASE_URL\")}')
print(f'  MODEL: {os.getenv(\"MODEL\")}')

client = LLMClient()
response = client.invoke('说你好', temperature=0.1)
print(f'\nLLM响应: {response[:100]}...')
print('\n[OK] 新模型工作正常')
"
```

---

## 测试输出说明

### 成功的输出示例
```
============================================================
测试结果统计
============================================================
总测试数: 8
成功: 8
失败: 0
成功率: 100.0%

LLM调用统计
============================================================
总调用次数: 3
成功: 3
失败: 0
成功率: 100.0%
平均延迟: 500ms  ← 新模型应该更快
```

### 失败的输出示例
```
[red]FAIL[/red]
  - port不匹配: 期望6379, 实际None
```

---

## 常见问题

### Q1: 报错 "API密钥未设置"
**原因**: .env文件配置错误或未加载

**解决**:
```bash
# 检查.env文件
cat .env | grep API_KEY

# 确保格式正确（无空格）
API_KEY=sk-xxxxx
API_BASE_URL=https://api.deepseek.com/v1
MODEL=deepseek-chat
```

### Q2: 报错 429 (Rate Limit)
**原因**: API配额用完或频率限制

**解决**:
1. 检查API提供商的配额
2. 换成付费API
3. 减少测试频率

### Q3: 延迟很高 (>2秒)
**原因**: API服务器慢或网络问题

**解决**:
1. 换更快的模型 (deepseek-chat 通常<500ms)
2. 检查网络连接
3. 使用国内API服务商

### Q4: 测试通过但解析结果不对
**原因**: 模型理解能力不足或提示词需要调优

**解决**:
1. 换能力更强的模型 (如GPT-4)
2. 调整提示词温度参数
3. 增加更多Few-shot例子

---

## 性能基准

### 不同模型的预期表现

| 模型 | 延迟 | 准确率 | 成本/1K次 |
|------|------|--------|-----------|
| deepseek-chat (官方) | 300-500ms | 90-95% | $0.14-0.28 |
| qwen-plus | 500-800ms | 85-90% | $0.50 |
| gpt-3.5-turbo | 500-1000ms | 85-90% | $0.50-1.00 |
| gpt-4 | 1000-2000ms | 95-98% | $30-60 |

---

## 下次测试建议

1. **换模型后第一次测试**: 运行完整测试套件，验证所有功能
2. **日常开发**: 只运行相关的单个测试
3. **提交代码前**: 运行完整测试套件确保没有破坏
4. **生产部署前**: 运行压力测试 (100+次调用)

---

## 压力测试（可选）

如果你想测试新模型的稳定性：

```bash
# 运行100次测试
for i in {1..100}; do
    echo "Test $i/100"
    python -m src.cli diagnose "server1到server2端口80不通" --use-llm
    sleep 1  # 避免过快触发限流
done
```

---

**现在就运行**: `python test_llm_e2e.py`
