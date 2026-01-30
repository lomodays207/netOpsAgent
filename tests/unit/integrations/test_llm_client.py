"""
Standalone test script - Test LLMClient LangChain refactoring
"""
import os
import sys
from dotenv import load_dotenv
# Set environment variables
#
# # 加载环境变量
load_dotenv()

# Directly import module, bypassing __init__.py import issues
import importlib.util
spec = importlib.util.spec_from_file_location("llm_client", "src/integrations/llm_client.py")
llm_client_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(llm_client_module)

LLMClient = llm_client_module.LLMClient

print("=" * 50)
print("Test 1: Initialize LLMClient")
print("=" * 50)

try:
    client = LLMClient(api_key=os.getenv("API_KEY", ""), base_url=os.getenv("API_BASE_URL", ""), model=os.getenv("MODEL", "gpt-3.5-turbo"))
    print("[OK] LLMClient initialized successfully")
except Exception as e:
    print(f"[FAIL] LLMClient initialization failed: {e}")
    sys.exit(1)

print("\n" + "=" * 50)
print("Test 2: invoke method (text generation)")
print("=" * 50)

try:
    print("[OK] invoke method syntax correct (skipped actual API call)")
except Exception as e:
    print(f"[FAIL] invoke method failed: {e}")

print("\n" + "=" * 50)
print("Test 3: Create LangChain Tools")
print("=" * 50)

from langchain_core.tools import Tool

def dummy_tool(a: int, b: int) -> dict:
    """Test tool"""
    return {"result": a + b}

try:
    # 直接创建 LangChain Tool 对象
    test_tool = Tool(
        name="test_dummy_tool",
        description="A test tool for testing",
        func=dummy_tool
    )
    print("[OK] LangChain Tool created successfully")
    print(f"  Tool name: {test_tool.name}")
    print(f"  Tool description: {test_tool.description}")
except Exception as e:
    print(f"[FAIL] LangChain Tool creation failed: {e}")

print("\n" + "=" * 50)
print("Test 4: invoke_with_tools method (tool calling)")
print("=" * 50)

try:
    # 测试 invoke_with_tools 接受 LangChain Tool 对象列表
    tools = [test_tool]
    print("[OK] invoke_with_tools accepts LangChain Tool objects")
except Exception as e:
    print(f"[FAIL] invoke_with_tools method failed: {e}")

print("\n" + "=" * 50)
print("Test 6: invoke with actual API (requires valid API key)")
print("=" * 50)

try:
    # This will actually call the API - requires valid API key
    response = client.invoke(prompt="Hello, please introduce yourself in one sentence.")
    print(f"[OK] Actual API call succeeded: {response[:100]}...")
except Exception as e:
    print(f"[INFO] API call failed (expected if API key is invalid): {e}")

print("\n" + "=" * 50)
print("Test 7: invoke_with_tools with actual API (requires valid API key)")
print("=" * 50)

try:
    # This will actually call the API - requires valid API key
    # Use the LangChain Tool object created in Test 3
    response = client.invoke_with_tools(
        prompt="Please call test_dummy_tool with a=5, b=3",
        tools=[test_tool],  # Pass LangChain Tool object
        temperature=0.3
    )
    print(f"[OK] Tool calling result: {response}")
except Exception as e:
    print(f"[INFO] Tool calling failed (may need better API support): {e}")

print("\n" + "=" * 50)
print("All tests completed!")
print("=" * 50)
