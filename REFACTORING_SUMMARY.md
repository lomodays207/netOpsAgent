# 架构重构总结 - 从假MCP到纯LangChain

## 重构日期
2026-01-19

## 重构目标
**移除假的MCP架构，改为纯LangChain实现**

原架构存在的问题：
1. 虽然使用了 FastMCP 装饰器，但从未真正通过 MCP 协议调用
2. `llm_agent` 直接调用 Python 函数，不是 MCP 协议通信
3. 过度设计：单体 Python 应用不需要 MCP 的分布式能力
4. 命名误导：`mcp_registry` 其实是网络路由器，与 MCP 无关

## 架构变化

### 旧架构（假MCP）
```
LLM (LangChain bind_tools)
  -> llm_client.invoke_with_tools()
    -> llm_agent 解析 tool_calls
      -> mcp_server.execute_command_impl() (普通函数调用，不是MCP协议)
        -> mcp_registry (根据IP选择client)
          -> automation_client.execute()
            -> 自动化平台API
```

### 新架构（纯LangChain）
```
LLM (LangChain bind_tools)
  -> llm_client.invoke_with_tools()
    -> llm_agent 解析 tool_calls
      -> network_tools.execute_command() (业务逻辑封装)
        -> network_router (根据IP选择client)
          -> automation_client.execute()
            -> 自动化平台API
```

## 文件变更

### 1. 删除的文件
- 无（保留 mcp_server.py 用于参考，可后续删除）

### 2. 新增的文件
- `src/integrations/network_router.py` - 网络路由器（从 mcp_registry.py 重命名）
- `src/integrations/network_tools.py` - 网络诊断工具封装
- `config/networks.yaml` - 网络配置文件（从 mcp_servers.yaml 重命名）

### 3. 重构的文件

#### `src/integrations/llm_client.py`
**变更**：
- 移除 `register_tool()`, `_tools`, `_create_langchain_tools()` 等复杂机制
- 简化 `invoke_with_tools()` 直接接收 LangChain Tool 对象列表
- 移除 fallback 机制

**核心改进**：
```python
# 旧代码：需要先注册工具
client.register_tool(name="xxx", func=xxx, ...)
tools_schema = [...]  # OpenAI schema格式
response = client.invoke_with_tools(prompt, tools_schema)

# 新代码：直接传入LangChain Tool对象
from langchain_core.tools import Tool
tools = [Tool(name="xxx", func=xxx, description="...")]
response = client.invoke_with_tools(prompt, tools)
```

#### `src/integrations/network_router.py`
**变更**：
- 从 `mcp_registry.py` 重命名
- `MCPRegistry` -> `NetworkRouter`
- `MCPServerConfig` -> `NetworkConfig`
- `find_server_for_host()` -> `find_client_for_host()`
- 移除所有MCP相关的注释和命名

**核心功能**（保留）：
- 根据IP网段路由到不同的 `AutomationPlatformClient`
- 支持多网络环境隔离

#### `src/integrations/network_tools.py`
**新文件**：从 `mcp_server.py` 提取业务逻辑

**功能**：
- 封装网络诊断工具（execute_command, query_cmdb）
- 支持网络路由（通过 NetworkRouter）
- 提供统一的工具接口给 LLM Agent

**示例**：
```python
tools = NetworkTools(use_router=True)
result = await tools.execute_command(host="10.0.1.10", command="ping ...")
```

#### `src/agent/llm_agent.py`
**重大重构**：

**移除**：
- `from ..integrations import mcp_server`
- `from ..integrations.config_loader import load_mcp_config`
- `_register_mcp_tools()` 方法
- 所有 MCP 相关代码

**新增**：
- `from ..integrations.network_tools import NetworkTools`
- `from ..integrations.config_loader import load_network_config`
- `_create_tools()` 方法：直接创建 LangChain Tool 对象

**核心改进**：
```python
# 旧代码：注册工具到llm_client
self.llm_client.register_tool(
    name="execute_command",
    func=self._execute_command_impl,
    description="...",
    parameters_schema={...}
)

# 新代码：直接创建LangChain Tool
async def execute_command_func(host: str, command: str, timeout: int = 30) -> dict:
    return await self.network_tools.execute_command(host, command, timeout)

tool = Tool(
    name="execute_command",
    description="...",
    func=execute_command_func
)
```

#### `src/integrations/config_loader.py`
**变更**：
- `load_mcp_config()` -> `load_network_config()`
- 导入从 `mcp_registry` 改为 `network_router`
- 配置文件路径从 `mcp_servers.yaml` 改为 `networks.yaml`

#### `config/networks.yaml`
**变更**：
- 从 `mcp_servers.yaml` 复制并更新
- `mcp_servers:` -> `networks:`
- 注释更新，移除MCP相关描述

## 核心优势

### 1. 架构清晰
- **旧架构**：假装在用MCP，实际是普通函数调用
- **新架构**：直接用 LangChain，没有多余的抽象层

### 2. 代码简化
- 移除 200+ 行无用代码（register_tool, _create_langchain_tools, fallback等）
- llm_client.py 从 370 行减少到 221 行

### 3. 命名准确
- **旧命名**：`mcp_registry`, `MCP_TOOLS`, `load_mcp_config` - 误导性
- **新命名**：`network_router`, `network_tools`, `load_network_config` - 准确反映功能

### 4. 职责清晰
- `llm_client`: 纯粹的 LLM 调用封装
- `network_tools`: 网络诊断业务逻辑
- `network_router`: IP网段路由逻辑
- `llm_agent`: 诊断流程编排

## 保留的功能

### 1. 多网络环境支持（原 mcp_registry 功能）
- 根据主机IP自动路由到对应的 `AutomationPlatformClient`
- 支持 CIDR 网段配置
- 从 `networks.yaml` 加载配置

### 2. LangChain Tool Calling
- 使用 `bind_tools()` 让 LLM 输出 tool calls
- 标准的 LangChain Tool 对象
- 支持异步工具函数

### 3. 网络诊断逻辑
- execute_command: 在远程主机执行命令
- query_cmdb: 查询主机信息
- 自动化平台 API 集成

## 后续工作

### 可选清理
1. 删除 `src/integrations/mcp_server.py`（已废弃）
2. 删除 `config/mcp_servers.yaml`（已废弃）
3. 删除旧的 `mcp_registry.py`（已被 network_router.py 替代）

### 测试更新
1. 更新 `test_llm_client.py` - 适配新的 invoke_with_tools API
2. 更新 `test_mcp_basic.py` - 改为测试 network_tools

### 文档更新
1. 更新架构图
2. 更新 API 文档

## 总结

**这次重构不是简单的重命名，而是从根本上纠正了架构设计的错误。**

**关键认知**：
- **MCP 协议** ≠ **LangChain Tool Calling**
- MCP 是传输层协议（类似 gRPC），LangChain 是应用层框架
- 单体 Python 应用不需要 MCP 的分布式能力
- 不要为了用新技术而过度设计

**重构成果**：
- ✅ 架构清晰，职责分明
- ✅ 代码简化，易于维护
- ✅ 命名准确，符合实际功能
- ✅ 保留所有核心功能（网络路由、Tool Calling、诊断逻辑）

**你学到的教训**：
> **以为在用 MCP，其实只是普通函数调用**
> **应该先理解技术本质，再决定是否使用，而不是盲目追新**
