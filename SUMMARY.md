# netOpsAgent - LLM功能集成总结

## 🎉 完成状态

✅ **LLM功能已完全集成到netOpsAgent项目中**

## 📦 新增文件

### 核心实现
1. **`src/integrations/llm_client.py`** (147行)
   - OpenAI协议客户端
   - 支持任意兼容模型
   - 错误处理和重试机制

2. **`src/agent/nlu.py`** (176行)
   - 自然语言理解模块
   - Few-shot提示词
   - 自动回退机制

### 文档
3. **`docs/LLM_GUIDE.md`** (完整使用指南)
   - 配置说明
   - 使用示例
   - 最佳实践
   - 故障排除

4. **`LLM_FEATURES.md`** (功能总结)

## 🔧 修改的文件

### 核心模块
1. **`src/agent/analyzer.py`**
   - 添加LLM辅助分析方法 `_ai_analysis()`
   - 智能选择规则/LLM结果
   - 置信度阈值控制

2. **`src/cli.py`**
   - 添加 `--use-llm` 标志
   - LLM模式的NLU集成
   - 状态提示优化

3. **`src/agent/__init__.py`**
   - 导出NLU模块

4. **`src/integrations/__init__.py`**
   - 导出LLMClient

### 配置文件
5. **`requirements.txt`**
   - 新增 `openai>=1.0`
   - 新增 `python-dotenv>=1.0`

6. **`.env.example`**
   - LLM API配置示例（已有）

## 🚀 功能特性

### 1. 双引擎模式

| 模式 | 触发方式 | 特点 |
|------|---------|------|
| **规则引擎** | 默认 | 快速、免费、准确（已知场景）|
| **LLM增强** | `--use-llm` | 智能、灵活、适应未知场景 |

### 2. LLM增强的NLU

**输入示例：**
```
"我们的应用服务器连不上数据库了"
```

**LLM解析结果：**
```json
{
  "source": "应用服务器",
  "target": "数据库",
  "protocol": "tcp",
  "port": 3306,
  "fault_type": "port_unreachable"
}
```

### 3. LLM辅助分析

**工作流程：**
```
执行排查 → 规则分析（置信度0.9）
                  ↓ 高于阈值
              直接返回结果

执行排查 → 规则分析（置信度0.6）
                  ↓ 低于阈值
              LLM深度分析（置信度0.85）
                  ↓
              返回LLM结果
```

## 📝 使用方法

### 基本用法

```bash
# 规则引擎模式（默认）
python -m src.cli diagnose "server1到server2端口80不通" --scenario scenario1_refused

# LLM增强模式
python -m src.cli diagnose "服务器A连不上服务器B的HTTP服务" --use-llm

# 测试场景
python -m src.cli test scenario1_refused --use-llm
```

### 配置LLM

编辑 `.env` 文件：

```bash
# DeepSeek (推荐)
API_KEY=sk-xxxxx
API_BASE_URL=https://api.deepseek.com/v1
MODEL=deepseek-chat

# 或 通义千问
API_KEY=your-key
API_BASE_URL=https://api-inference.modelscope.cn/v1
MODEL=qwen/Qwen2.5-72B-Instruct

# 或 OpenAI
API_KEY=sk-xxxxx
API_BASE_URL=https://api.openai.com/v1
MODEL=gpt-4
```

## 🎯 技术亮点

### 1. OpenAI协议兼容
- 不绑定特定模型提供商
- 支持DeepSeek、Qwen、GPT、本地模型等
- 统一的接口设计

### 2. 智能回退机制
```python
try:
    # 尝试LLM解析
    task = nlu.parse_user_input(user_input)
except Exception:
    # 失败自动回退到规则引擎
    task = parse_user_input_rule_based(user_input)
```

### 3. 提示词工程
- **系统提示词**: 定义专家角色
- **Few-shot示例**: 提供样例
- **输出约束**: JSON格式
- **温度控制**: 0.3（确定性）

### 4. 成本优化
- 规则引擎优先（免费、快速）
- 置信度阈值控制LLM调用
- 仅在必要时使用AI

## 📊 测试验证

### 已验证功能
✅ 规则引擎模式正常运行
✅ CLI正常工作
✅ 所有25个单元测试通过
✅ Scenario 1测试成功

### LLM功能（需配置API）
⚠️ 需要配置.env才能测试
⚠️ 功能代码已完成，等待API配置

## 🔗 相关文档

- **完整使用指南**: `docs/LLM_GUIDE.md`
- **项目规格**: `docs/spec.md`
- **解析器设计**: `docs/parsers_design.md`
- **功能总结**: `LLM_FEATURES.md`

## 💡 最佳实践

### 何时使用LLM？

**推荐使用LLM：**
- ✅ 自然语言输入（非技术用户）
- ✅ 未知/复杂故障
- ✅ 规则引擎置信度低
- ✅ 需要详细根因分析

**推荐使用规则引擎：**
- ✅ 常见故障类型
- ✅ 批量诊断
- ✅ 快速响应要求
- ✅ 离线环境

### 成本控制

```bash
# 方案1: 按需启用
python -m src.cli diagnose "..." --use-llm  # 仅在需要时

# 方案2: 批量处理不用LLM
for i in {1..100}; do
    python -m src.cli diagnose "server$i..." 
done

# 方案3: 系统默认（混合模式）
# 规则置信度高→直接返回
# 规则置信度低→才调用LLM
```

## 🎓 技术栈

- **LLM SDK**: OpenAI Python SDK
- **环境管理**: python-dotenv
- **提示词工程**: Few-shot learning
- **错误处理**: 多层回退机制
- **成本优化**: 智能触发策略

## 📈 项目统计

- **新增代码**: ~500行
- **新增文件**: 4个
- **修改文件**: 6个
- **新增依赖**: 2个
- **文档**: 2篇完整指南

## 🚀 下一步

1. **配置API密钥**测试LLM功能
2. **调优提示词**提高解析准确率
3. **添加缓存**减少重复LLM调用
4. **监控成本**跟踪API使用情况
5. **扩展场景**支持更多故障类型

## ✅ 总结

LLM功能已**完全集成**到netOpsAgent中，实现了：

1. ✅ **灵活的模型支持** - OpenAI协议兼容
2. ✅ **智能的NLU** - 自然语言理解
3. ✅ **可靠的回退** - 失败自动降级
4. ✅ **高效的成本** - 规则优先，AI兜底
5. ✅ **完整的文档** - 详细使用指南

**系统现在支持两种工作模式，用户可以根据场景灵活选择！** 🎉
