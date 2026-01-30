# 设计变更记录 (Design Change Log)

本文件用于记录项目中的重大功能变更、架构调整及设计决策。

---

## [2026-01-29] 优化中断响应速度及流式输出逻辑

### 变更背景
用户反馈在 LLM 流式输出过程中，点击“停止”按钮后响应延迟，页面往往会继续输出一段内容才真正停止。

### 变更内容

#### 1. 后端 (Python/FastAPI)
- **SSE 循环优化 (`src/api.py`)**: 
  - 减小了 `asyncio.wait_for` 的超时时间（从 0.05s 调整为 0.1s，并移除了心跳过于频繁导致的潜在阻塞风险）。
  - 移除了冗余的 `: event sent` 注释，减少数据包大小。
  - 增加了对后台任务 `done()` 状态的显式检查，确保在任务异常退出时能立即关闭连接。
- **Agent 执行检查点 (`src/agent/llm_agent.py`)**:
  - 在 `diagnose` 和 `continue_diagnose` 的工具执行前后增加了 `stop_event.is_set()` 检查。
  - 确保即使在执行长耗时工具（如网络扫描）时，也能在子步骤间迅速响应中断信号。
- **Agent 初始化重构**:
  - 移除了硬编码的 `max_steps`，支持从环境变量 `LLM_AGENT_MAX_STEPS` 读取。

#### 2. 前端 (Javascript)
- **UI 零延迟响应**: 
  - 点击“停止”按钮后立即将 `isWaitingForResponse` 设为 `false`。
  - 立即调用 `hideTypingIndicator()` 和 `setInputEnabled(true)`，无需等待服务器端确认。
- **打字机效果感知中断**: 
  - 修改了 `addAssistantMessageWithTyping` 函数，使其在每一字符渲染前检查 `isWaitingForResponse` 状态，实现“点击即停”。
- **流生命周期管理**: 
  - `processStream` 现在能感知外部中断信号并主动调用 `reader.cancel()` 释放流资源。

### 修复内容 (Hotfix)
- 修复了因为 `generalChat` 未正确维护 `isWaitingForResponse` 状态导致中断按钮在通用聊天模式下“点击不动”的问题。
- 修复了打字机逻辑在正常结束时可能出现的闪退问题。
