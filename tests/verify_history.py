import asyncio
import json
import os
import sys

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agent.llm_agent import LLMAgent
from src.session_manager import SQLiteSessionManager
from src.models.task import DiagnosticTask, Protocol, FaultType

async def verify_history():
    print("Initializing components...")
    # Use a temporary database for testing if possible, or just check the current one
    session_manager = SQLiteSessionManager()
    await session_manager.initialize()
    
    # agent = LLMAgent() # Bypassing agent init to avoid API key requirement
    
    task = DiagnosticTask(
        task_id="test_verify_history_" + str(int(asyncio.get_event_loop().time())),
        source="10.0.1.10",
        target="10.0.2.20",
        protocol=Protocol.TCP,
        port=80,
        fault_type=Fault_Type.CONNECTIVITY if hasattr(FaultType, 'CONNECTIVITY') else FaultType.NETWORK_UNREACHABLE,
        user_input="Test diagnosis"
    )
    
    session_id = task.task_id
    # session_manager.create_session(session_id, task, None, None)
    
    print(f"Starting diagnosis for session: {session_id}")
    
    # We'll just run a few steps or mock the behavior
    # to avoid hitting real LLM too much if not needed, 
    # but since this is for verification of 'logging', 
    # we want to see actual execution flow.
    
    try:
        # 1. 保存用户消息
        print("Testing: Saving user message...")
        await session_manager.add_message(session_id, "user", "Test diagnosis request")
        
        # 2. 模拟工具调用记录
        print("Testing: Saving mock tool call...")
        tool_call_data = {
            "name": "ping",
            "arguments": {"host": "10.0.1.10"},
            "result": {"success": True, "stdout": "64 bytes from 10.0.1.10..."}
        }
        await session_manager.add_message(
            session_id=session_id,
            role="assistant",
            content="执行工具: ping",
            metadata={"tool_call": tool_call_data}
        )
        
        # 3. 模拟最终报告
        print("Testing: Saving mock report...")
        report_data = {
            "root_cause": "防火墙拒绝访问",
            "confidence": 0.95,
            "fix_suggestions": ["检查 ACL 策略", "允许端口 80 流量"]
        }
        await session_manager.add_message(
            session_id=session_id,
            role="assistant",
            content=f"诊断完成。根因：{report_data['root_cause']}",
            metadata={"report": report_data}
        )
        
    except Exception as e:
        print(f"Error during test: {e}")
    
    print("\nChecking saved messages...")
    messages = await session_manager.db.get_session_messages(session_id)
    
    found_tool_calls = False
    for msg in messages:
        print(f"Role: {msg['role']} | Content: {msg['content'][:50]}...")
        if msg['metadata']:
            metadata = json.loads(msg['metadata'])
            if "tool_call" in metadata:
                print(f"  -> Found tool call: {metadata['tool_call']['name']}")
                found_tool_calls = True
    
    if found_tool_calls:
        print("\nSUCCESS: Tool calls were found in the history!")
    else:
        print("\nFAILURE: No tool calls found in the history.")

if __name__ == "__main__":
    asyncio.run(verify_history())
