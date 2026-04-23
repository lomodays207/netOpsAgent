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


@pytest.mark.asyncio
async def test_check_port_alive_reports_not_alive_when_grep_finds_no_listener():
    client = RecordingClient(
        CommandResult(
            command="ss -tlnp | grep ':8080'",
            host="10.0.2.20",
            success=False,
            stdout="",
            stderr="",
            exit_code=1,
            execution_time=0.09,
        )
    )
    tools = NetworkTools(default_client=client, use_router=False)

    result = await tools.check_port_alive("10.0.2.20", 8080, timeout=5)

    assert result["success"] is True
    assert result["port_alive"] is False
    assert result["exit_code"] == 1


def test_llm_agent_registers_check_port_alive_tool():
    from src.agent.llm_agent import LLMAgent

    agent = LLMAgent(llm_client=object(), max_steps=1)

    assert "check_port_alive" in {tool.name for tool in agent.tools}


@pytest.mark.asyncio
async def test_llm_agent_executes_check_port_alive_tool_call():
    from src.agent.llm_agent import LLMAgent

    class FakeNetworkTools:
        def __init__(self):
            self.calls = []

        async def check_port_alive(self, host, port, timeout=30):
            self.calls.append({"host": host, "port": port, "timeout": timeout})
            return {"success": True, "port_alive": True}

    agent = LLMAgent(llm_client=object(), max_steps=1)
    agent.network_tools = FakeNetworkTools()

    result = await agent._execute_tool(
        {
            "name": "check_port_alive",
            "arguments": {"host": "10.0.2.20", "port": 80, "timeout": 7},
        },
        task=None,
    )

    assert result == {"success": True, "port_alive": True}
    assert agent.network_tools.calls == [{"host": "10.0.2.20", "port": 80, "timeout": 7}]
