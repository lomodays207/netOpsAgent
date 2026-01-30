# LLM功能已添加 ✅

## 新增组件

### 1. LLM客户端 (`src/integrations/llm_client.py`)
- 使用OpenAI协议
- 支持任意兼容模型（DeepSeek、Qwen、GPT等）
- 自动错误处理和重试

### 2. NLU模块 (`src/agent/nlu.py`)
- 自然语言理解
- Few-shot提示词工程
- 失败时自动回退到规则引擎

### 3. AI辅助分析器 (增强 `src/agent/analyzer.py`)
- 规则引擎优先
- 置信度 < 0.8 时调用LLM
- 智能选择最佳结果

## 配置

在`.env`文件中配置（已在`.env.example`中提供示例）：

```bash
# OpenAI协议兼容的LLM配置
API_KEY=your-api-key-here
API_BASE_URL=https://api-inference.modelscope.cn/v1
MODEL=deepseek-ai/DeepSeek-V3.2
```

## 使用

### 规则引擎模式（默认）
```bash
python -m src.cli diagnose "server1到server2端口80不通"
```

### LLM增强模式
```bash
python -m src.cli diagnose "服务器A连不上服务器B的HTTP服务" --use-llm
```

### 测试场景
```bash
# 无LLM
python -m src.cli test scenario1_refused

# 启用LLM
python -m src.cli test scenario1_refused --use-llm
```

## 工作原理

### LLM增强的NLU
```
用户: "我们的应用服务器连不上数据库了"
  ↓
LLM解析 → {
  "source": "应用服务器",
  "target": "数据库",
  "protocol": "tcp",
  "port": 3306,
  "fault_type": "port_unreachable"
}
```

### LLM辅助分析
```
规则引擎分析
  ↓
置信度 >= 0.8? ──是──> 返回结果
  ↓ 否
LLM深度分析
  ↓
选择置信度更高的结果
```

## 依赖

新增依赖已添加到`requirements.txt`：
- `openai>=1.0` - OpenAI SDK
- `python-dotenv>=1.0` - 环境变量管理

## 文档

完整文档：[docs/LLM_GUIDE.md](docs/LLM_GUIDE.md)

## 优势

✅ **灵活** - 支持任何OpenAI协议兼容的模型
✅ **智能** - 自然语言理解 + AI推理
✅ **稳定** - 失败自动回退到规则引擎
✅ **高效** - 规则优先，LLM兜底
✅ **透明** - 清晰标识使用了哪种分析方法

## 示例输出

```
netOpsAgent - 智能网络故障排查
============================================================

已启用LLM增强模式
使用LLM解析用户输入...
OK LLM解析完成

OK 任务已创建: task_20260113_001
  故障类型: port_unreachable
  源主机: web-server
  目标主机: db-server
  端口: 3306

OK LLM客户端初始化成功
...
使用LLM辅助分析诊断结果...
状态: [OK] 已定位根因
置信度: 92.0% (高)
```
