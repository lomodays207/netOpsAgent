# Host Port Status Query Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make single-host port status questions skip RAG, stay in `general_chat`, and let the LLM drive `check_port_alive` tool calling and final summarization.

**Architecture:** Add one shared rule-based detector for host-port status queries and reuse it in routing and RAG-skip decisions. Remove the hardcoded direct port-check path from the general chat agent and feed the detector result into the LLM tool-calling context instead.

**Tech Stack:** FastAPI, LangChain messages/tools, pytest, existing `GeneralChatToolAgent`, existing `RuleIntentRouter`

---

### Task 1: Add Failing Tests For Shared Detection And RAG Skip

**Files:**
- Create: `tests/unit/agent/test_query_intents.py`
- Modify: `tests/test_rag_skip_for_access_relations.py`

- [ ] **Step 1: Write the failing detector tests**

```python
from src.agent.query_intents import detect_host_port_status_query


def test_detect_host_port_status_query_matches_single_host_port_status_request():
    result = detect_host_port_status_query("请帮我检查10.0.2.20 主机上的 8008 是否正常监听？")

    assert result == {"host": "10.0.2.20", "port": 8008}


def test_detect_host_port_status_query_ignores_how_to_question():
    result = detect_host_port_status_query("如何检查端口是否监听")

    assert result is None


def test_detect_host_port_status_query_ignores_connectivity_request():
    result = detect_host_port_status_query("10.0.1.10 到 10.0.2.20 的 8008 不通")

    assert result is None
```

- [ ] **Step 2: Run detector tests to verify they fail**

Run: `pytest tests/unit/agent/test_query_intents.py -q`
Expected: FAIL with `ModuleNotFoundError` for `src.agent.query_intents`

- [ ] **Step 3: Write the failing RAG skip test**

```python
@pytest.mark.asyncio
async def test_host_port_status_query_skips_rag():
    request = GeneralChatRequestWithRAG(
        message="请帮我检查10.0.2.20 主机上的 8008 是否正常监听？",
        use_rag=True,
        session_id=None,
    )

    ...

    assert "rag_skipped" in event_types
    assert "rag_start" not in event_types
    assert "rag_result" not in event_types
```

- [ ] **Step 4: Run the RAG skip test to verify it fails**

Run: `pytest tests/test_rag_skip_for_access_relations.py::test_host_port_status_query_skips_rag -q`
Expected: FAIL because RAG is still executed or because `rag_skipped` is not emitted

### Task 2: Add Shared Detector And Reuse It In Routing

**Files:**
- Create: `src/agent/query_intents.py`
- Modify: `src/agent/rule_intent_router.py`
- Modify: `tests/unit/agent/test_rule_intent_router.py`
- Modify: `tests/unit/agent/test_hybrid_intent_router.py`
- Test: `tests/unit/agent/test_query_intents.py`

- [ ] **Step 1: Implement `detect_host_port_status_query()` in a shared module**

```python
def detect_host_port_status_query(message: str) -> Optional[dict[str, int | str]]:
    ...
```

- [ ] **Step 2: Reuse the shared detector in `RuleIntentRouter`**

```python
port_status_query = detect_host_port_status_query(text)
...
"host_port_status_query": port_status_query,
"is_port_listening_check": port_status_query is not None,
```

- [ ] **Step 3: Keep matching requests as hard `general_chat`**

```python
if signals["is_port_listening_check"]:
    return RuleIntentResult(
        route="general_chat",
        confidence=0.96,
        reason="host_port_listening_check",
        certainty="hard",
        signals=signals,
    )
```

- [ ] **Step 4: Run routing tests**

Run: `pytest tests/unit/agent/test_query_intents.py tests/unit/agent/test_rule_intent_router.py tests/unit/agent/test_hybrid_intent_router.py -q`
Expected: PASS

### Task 3: Reuse Shared Detector In `general_chat_stream_v2()` RAG Skip

**Files:**
- Modify: `src/api.py`
- Modify: `tests/test_rag_skip_for_access_relations.py`

- [ ] **Step 1: Reuse the shared detector for skip-RAG decisions**

```python
host_port_query = detect_host_port_status_query(request.message) if request.use_rag else None
if request.use_rag and host_port_query:
    skip_rag = True
    yield ... "检测到主机端口状态查询,跳过知识库检索"
```

- [ ] **Step 2: Preserve existing access relation skip behavior**

```python
if request.use_rag and is_access_relation_data_query(request.message):
    ...
elif request.use_rag and host_port_query:
    ...
```

- [ ] **Step 3: Run the RAG skip tests**

Run: `pytest tests/test_rag_skip_for_access_relations.py -q`
Expected: PASS

### Task 4: Remove Hardcoded Direct Port Check And Feed Detection Context To LLM

**Files:**
- Modify: `src/agent/general_chat_agent.py`
- Modify: `tests/test_general_chat_agent.py`

- [ ] **Step 1: Remove `_extract_direct_port_check()` and `_run_direct_port_check()`**

```python
# delete the hardcoded direct port-check path
```

- [ ] **Step 2: Inject host-port detection context as a system message**

```python
host_port_query = detect_host_port_status_query(latest_user_content)
if host_port_query:
    messages.append(
        SystemMessage(
            content=(
                "当前用户请求已识别为主机端口状态查询。"
                f"目标主机: {host_port_query['host']}。"
                f"目标端口: {host_port_query['port']}。"
                "必须先调用 check_port_alive，再基于工具结果回答。"
            )
        )
    )
```

- [ ] **Step 3: Update the port-check agent test so LLM drives the tool call**

```python
def test_general_chat_agent_uses_llm_tool_call_for_explicit_port_check():
    ...
    assert llm_client.tool_round == 2
    assert agent.network_tools.calls == [{"host": "10.0.2.20", "port": 8008, "timeout": 30}]
```

- [ ] **Step 4: Remove the old bypass test and replace it with a summary-after-tool test**

Run: `pytest tests/test_general_chat_agent.py -q`
Expected: PASS

### Task 5: Run Final Verification

**Files:**
- Verify: `src/agent/query_intents.py`
- Verify: `src/agent/rule_intent_router.py`
- Verify: `src/api.py`
- Verify: `src/agent/general_chat_agent.py`
- Verify: `tests/unit/agent/test_query_intents.py`
- Verify: `tests/unit/agent/test_rule_intent_router.py`
- Verify: `tests/unit/agent/test_hybrid_intent_router.py`
- Verify: `tests/test_general_chat_agent.py`
- Verify: `tests/test_rag_skip_for_access_relations.py`

- [ ] **Step 1: Run the focused test suite**

Run: `pytest tests/unit/agent/test_query_intents.py tests/unit/agent/test_rule_intent_router.py tests/unit/agent/test_hybrid_intent_router.py tests/test_general_chat_agent.py tests/test_rag_skip_for_access_relations.py tests/unit/integrations/test_network_tools.py -q`
Expected: PASS with 0 failures

- [ ] **Step 2: Run compile verification**

Run: `python -m compileall -q src/agent/query_intents.py src/agent/rule_intent_router.py src/api.py src/agent/general_chat_agent.py`
Expected: exit code 0

- [ ] **Step 3: Run whitespace and patch sanity check**

Run: `git diff --check -- src/agent/query_intents.py src/agent/rule_intent_router.py src/api.py src/agent/general_chat_agent.py tests/unit/agent/test_query_intents.py tests/unit/agent/test_rule_intent_router.py tests/unit/agent/test_hybrid_intent_router.py tests/test_general_chat_agent.py tests/test_rag_skip_for_access_relations.py`
Expected: exit code 0
