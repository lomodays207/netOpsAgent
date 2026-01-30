# MCP Server简化设计方案

**更新日期**: 2026-01-14
**关键变化**: 使用FastMCP + 自动化平台API，不直接SSH

---

## 核心简化

### 原方案（复杂）
```
MCP Server → SSH连接 → 服务器执行命令
```
**问题**: 需要管理SSH连接、密钥、连接池

### 新方案（简单）
```
MCP Server → 自动化平台API → 服务器执行命令
```
**优势**:
- 无需SSH管理
- 复用现有基础设施
- 更安全（API层面控制）

---

## FastMCP实现

### 文件结构
```
src/integrations/
├── mcp_server.py          # FastMCP Server主文件
└── automation_client.py   # 自动化平台API客户端（已存在）
```

### 核心代码

**`src/integrations/mcp_server.py`**:
```python
from fastmcp import FastMCP
from .automation_platform_client import AutomationPlatformClient
import os

# 初始化FastMCP
mcp = FastMCP("netOpsAgent")

# 初始化自动化平台客户端
automation_client = AutomationPlatformClient(
    api_url=os.getenv("AUTOMATION_API_URL"),
    api_token=os.getenv("AUTOMATION_API_TOKEN")
)

@mcp.tool()
async def execute_command(
    host: str,
    command: str,
    timeout: int = 30
) -> dict:
    """
    在指定主机上执行命令

    Args:
        host: 目标主机IP或主机名
        command: 要执行的命令
        timeout: 超时时间（秒）

    Returns:
        {
            "success": bool,
            "stdout": str,
            "stderr": str,
            "exit_code": int
        }
    """
    # 调用自动化平台API
    result = await automation_client.execute(
        device=host,
        command=command,
        timeout=timeout
    )

    return {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code
    }

@mcp.tool()
async def query_cmdb(hosts: list[str]) -> dict:
    """查询CMDB获取主机信息"""
    # 调用CMDB API
    pass

# 启动MCP Server
if __name__ == "__main__":
    mcp.run()
```

---

## 使用方式

### 1. 启动MCP Server
```bash
python -m src.integrations.mcp_server
```

### 2. LLM调用MCP工具
```python
# LLM Agent决策
decision = {
    "action": "execute_command",
    "params": {
        "host": "10.0.1.10",
        "command": "timeout 5 bash -c 'cat < /dev/tcp/10.0.2.20/80'"
    }
}

# 调用MCP工具
result = await mcp_client.call_tool("execute_command", **decision["params"])
```

---

## 依赖更新

### 新增依赖
```txt
fastmcp>=0.1.0
```

### 移除依赖
- ~~asyncssh~~ (不需要了)

---

## 安全机制

### 1. API层面控制
- 自动化平台API已有权限控制
- 无需在MCP层面管理SSH密钥

### 2. 命令白名单（可选）
```python
ALLOWED_COMMANDS = [
    r"^timeout \d+ bash -c 'cat < /dev/tcp/.*'$",  # telnet
    r"^ping -c \d+ -W \d+ .*$",                     # ping
    r"^ss -[tunlp]+ \| grep .*$",                   # ss
    r"^iptables -L .* -n -v$",                      # iptables
    r"^traceroute .* -m \d+ -w \d+$",               # traceroute
]

def validate_command(command: str) -> bool:
    return any(re.match(pattern, command) for pattern in ALLOWED_COMMANDS)
```

---

## 实施步骤（简化版）

### Step 1: 实现FastMCP Server
1. 创建 `src/integrations/mcp_server.py`
2. 实现 `execute_command` 工具
3. 调用现有的 `AutomationPlatformClient`

### Step 2: 测试MCP工具
```bash
# 启动MCP Server
python -m src.integrations.mcp_server

# 测试工具调用
python -c "
import asyncio
from mcp import ClientSession

async def test():
    async with ClientSession('stdio', 'python', '-m', 'src.integrations.mcp_server') as session:
        result = await session.call_tool('execute_command', {
            'host': '10.0.1.10',
            'command': 'echo hello'
        })
        print(result)

asyncio.run(test())
"
```

### Step 3: LLM Agent集成
1. 修改 `src/agent/llm_agent.py`
2. 配置LLM使用MCP工具
3. 测试端到端流程

---

## 对比：简化前 vs 简化后

| 项目 | 简化前 | 简化后 |
|------|--------|--------|
| **SSH管理** | 需要 | 不需要 |
| **依赖** | asyncssh | fastmcp |
| **代码量** | ~300行 | ~100行 |
| **安全性** | 自己管理 | API层控制 |
| **维护成本** | 高 | 低 |

---

## 总结

通过使用FastMCP + 自动化平台API，设计方案大幅简化：

✅ **更简单** - 无需SSH连接管理
✅ **更安全** - 复用自动化平台的权限控制
✅ **更快** - 减少70%代码量
✅ **更易维护** - 依赖现有基础设施

**下一步**: 实现 `src/integrations/mcp_server.py`（约100行代码）
