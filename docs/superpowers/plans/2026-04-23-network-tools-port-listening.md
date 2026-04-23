# NetworkTools Port Listening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a NetworkTools tool that checks whether a given host IP has a specified TCP port listening locally.

**Architecture:** The new `NetworkTools.check_port_alive()` method will reuse the existing `AutomationPlatformClient` routing path and execute `ss -tlnp | grep ':<port>'` on the target host. `LLMAgent` will expose this method as a structured LangChain tool named `check_port_alive`.

**Tech Stack:** Python 3.10, pytest, pytest-asyncio, LangChain `StructuredTool`, existing `AutomationPlatformClient` mock command executor.

---

### Task 1: NetworkTools Method

**Files:**
- Create: `tests/unit/integrations/test_network_tools.py`
- Modify: `src/integrations/network_tools.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from src.integrations.network_tools import NetworkTools
from src.models.results import CommandResult


class RecordingClient:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def execute(self, device, command, timeout=30):
        self.calls.append({"device": device, "command": command, "timeout": timeout})
        return self.result


@pytest.mark.asyncio
async def test_check_port_alive_runs_ss_on_target_host():
    client = RecordingClient(
        CommandResult(
            command="",
            host="10.0.2.20",
            success=True,
            stdout='tcp LISTEN 0 128 0.0.0.0:80 0.0.0.0:* users:(("nginx",pid=1234,fd=6))',
            stderr="",
            exit_code=0,
            execution_time=0.12,
        )
    )
    tools = NetworkTools(default_client=client, use_router=False)

    result = await tools.check_port_alive("10.0.2.20", 80, timeout=5)

    assert result["success"] is True
    assert result["port_alive"] is True
    assert result["host"] == "10.0.2.20"
    assert result["port"] == 80
    assert client.calls == [
        {"device": "10.0.2.20", "command": "ss -tlnp | grep ':80'", "timeout": 5}
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/integrations/test_network_tools.py::test_check_port_alive_runs_ss_on_target_host -q`
Expected: FAIL with `AttributeError: 'NetworkTools' object has no attribute 'check_port_alive'`.

- [ ] **Step 3: Write minimal implementation**

Add `check_port_alive()` to `NetworkTools`. The method validates the port range, executes the `ss` command via `_get_client_for_host()`, and returns `success`, `port_alive`, `host`, `port`, `command`, `stdout`, `stderr`, `exit_code`, and `execution_time`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/integrations/test_network_tools.py::test_check_port_alive_runs_ss_on_target_host -q`
Expected: PASS.

### Task 2: LLM Tool Registration

**Files:**
- Modify: `src/agent/llm_agent.py`
- Test: `tests/unit/integrations/test_network_tools.py`

- [ ] **Step 1: Write the failing test**

```python
def test_llm_agent_registers_check_port_alive_tool():
    from src.agent.llm_agent import LLMAgent

    agent = LLMAgent(llm_client=object(), max_steps=1)

    assert "check_port_alive" in {tool.name for tool in agent.tools}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/integrations/test_network_tools.py::test_llm_agent_registers_check_port_alive_tool -q`
Expected: FAIL because the tool is not registered.

- [ ] **Step 3: Register the tool**

Add a Pydantic input schema with `host`, `port`, and `timeout`, add a `StructuredTool.from_function()` entry in `_create_tools()`, and route `"check_port_alive"` inside `_execute_tool()`.

- [ ] **Step 4: Run verification**

Run: `pytest tests/unit/integrations/test_network_tools.py -q`
Expected: PASS.
