import asyncio
import json
import os
import sys
from datetime import datetime

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.session_manager import SQLiteSessionManager

async def verify_persistence():
    print("Initializing components...")
    session_manager = SQLiteSessionManager()
    await session_manager.initialize()
    
    session_id = "test_persistence_" + datetime.now().strftime("%Y%m%d%H%M%S")
    
    print(f"Starting persistence test for session: {session_id}")
    
    try:
        # 1. Save user message
        print("Step 1: Saving user message...")
        await session_manager.add_message(session_id, "user", "Test diagnosis request")
        
        # 2. Save mock tool call
        print("Step 2: Saving mock tool call...")
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
        
        # 3. Save mock report
        print("Step 3: Saving mock report...")
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
        import traceback
        traceback.print_exc()
        return
    
    print("\nChecking saved messages via DB...")
    messages = await session_manager.db.get_messages(session_id)
    
    found_tool_calls = False
    found_report = False
    
    for msg in messages:
        role = msg['role']
        content = msg['content']
        metadata_str = msg['metadata']
        metadata = json.loads(metadata_str) if metadata_str else {}
        
        print(f"Role: {role} | Content: {content[:50]}...")
        if "tool_call" in metadata:
            print(f"  -> SUCCESS: Found tool call metadata: {metadata['tool_call']['name']}")
            found_tool_calls = True
        if "report" in metadata:
            print(f"  -> SUCCESS: Found report metadata: {metadata['report']['root_cause']}")
            found_report = True
    
    if found_tool_calls and found_report:
        print("\nFINAL VERIFICATION SUCCESS: All diagnostic data persisted correctly.")
    else:
        print("\nFINAL VERIFICATION FAILURE: Some data was not found.")

if __name__ == "__main__":
    asyncio.run(verify_persistence())
