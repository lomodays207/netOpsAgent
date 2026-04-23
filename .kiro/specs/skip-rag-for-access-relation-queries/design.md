# Skip RAG for Access Relation Queries Bugfix Design

## Overview

This bugfix addresses the incorrect execution path when users query access relation data (e.g., "N-CRM有哪些访问关系"). Currently, the system incorrectly performs RAG knowledge base retrieval first, which may return example data or outdated information from documents, instead of letting the LLM directly call the `query_access_relations` tool to fetch real-time data from the database.

The fix introduces a detection mechanism to identify access relation **data queries** and skip RAG retrieval for them, while preserving RAG retrieval for access relation **knowledge queries** (e.g., "访问关系如何开权限") and other general network operations questions.

**Key Strategy**: Add a pre-processing step in `general_chat_stream_v2` that detects access relation data queries before RAG retrieval, and skip RAG when detected.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug - when a user message is an access relation data query and `use_rag=True`, causing unnecessary RAG retrieval
- **Property (P)**: The desired behavior - access relation data queries should skip RAG and directly invoke the `query_access_relations` tool
- **Preservation**: Existing RAG behavior for knowledge queries and other general questions must remain unchanged
- **general_chat_stream_v2**: The async function in `src/api.py` (line ~1789) that handles general chat requests with RAG support
- **is_access_relation_data_query**: A new detection function that identifies whether a message is asking for access relation data (not knowledge)
- **System Identifier**: System code (e.g., N-CRM, P-DB-MAIN), system name (e.g., 客户关系管理系统), deploy unit (e.g., CRMJS_AP), or IP address (e.g., 10.0.1.10)
- **Access Relation Data Query**: A query asking for specific access relation records from the database
- **Access Relation Knowledge Query**: A query asking about processes, permissions, or how-to information related to access relations

## Bug Details

### Bug Condition

The bug manifests when a user asks for access relation data (containing system identifiers such as system codes, system names, deploy units, or IP addresses, and asking about access relations) with `use_rag=True`. The `general_chat_stream_v2` function incorrectly executes RAG retrieval first, potentially returning knowledge base examples instead of letting the LLM call the tool to fetch real-time database records.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type GeneralChatRequestWithRAG
  OUTPUT: boolean
  
  RETURN input.use_rag = true
         AND is_access_relation_data_query(input.message)
END FUNCTION

FUNCTION is_access_relation_data_query(message)
  INPUT: message of type string
  OUTPUT: boolean
  
  // Check for system identifier (system code, system name, deploy unit, or IP address)
  has_system_identifier := MATCHES(message, SYSTEM_IDENTIFIER_PATTERN)
  
  // Check if asking about access relations
  asks_for_relations := MATCHES(message, RELATION_QUERY_PATTERN)
  
  // Check if asking knowledge questions (if yes, should NOT skip RAG)
  asks_for_knowledge := MATCHES(message, KNOWLEDGE_QUERY_PATTERN)
  
  RETURN has_system_identifier AND asks_for_relations AND NOT asks_for_knowledge
END FUNCTION

WHERE:
  SYSTEM_IDENTIFIER_PATTERN = "(N-[A-Z]+|P-[A-Z-]+|[A-Z]+JS_[A-Z]+|客户关系管理系统|办公自动化系统|部署单元|\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})"
  RELATION_QUERY_PATTERN = "(有哪些访问关系|哪些系统访问|被.*访问|访问.*系统|之间.*访问关系)"
  KNOWLEDGE_QUERY_PATTERN = "(如何|怎么|流程|权限|提单|申请|审批|管理)"
```

### Examples

- **Example 1 (Bug Condition Holds)**: User asks "N-CRM有哪些访问关系" with `use_rag=True`
  - **Current Behavior**: System executes RAG retrieval, may return knowledge base examples
  - **Expected Behavior**: System skips RAG, LLM calls `query_access_relations(system_code="N-CRM", direction="outbound")`

- **Example 2 (Bug Condition Holds)**: User asks "CRMJS_AP部署单元有哪些访问关系" with `use_rag=True`
  - **Current Behavior**: System executes RAG retrieval
  - **Expected Behavior**: System skips RAG, LLM calls `query_access_relations(deploy_unit="CRMJS_AP", direction="outbound")`

- **Example 3 (Bug Condition Holds)**: User asks "IP 为 10.0.1.10 的主机有哪些访问关系" with `use_rag=True`
  - **Current Behavior**: System executes RAG retrieval, may return knowledge base examples
  - **Expected Behavior**: System skips RAG, LLM calls `query_access_relations` tool with IP address as query condition

- **Example 4 (Bug Condition Holds)**: User asks "10.0.1.10 有哪些访问关系" with `use_rag=True`
  - **Current Behavior**: System executes RAG retrieval
  - **Expected Behavior**: System skips RAG, LLM calls `query_access_relations` tool with IP address

- **Example 5 (Bug Condition Holds)**: User asks "查询 10.0.1.10 的访问关系" with `use_rag=True`
  - **Current Behavior**: System executes RAG retrieval
  - **Expected Behavior**: System skips RAG, LLM calls `query_access_relations` tool with IP address

- **Example 6 (Bug Condition Does NOT Hold)**: User asks "访问关系如何开权限" with `use_rag=True`
  - **Current Behavior**: System executes RAG retrieval, returns knowledge documents (CORRECT)
  - **Expected Behavior**: Same as current - this is a knowledge query, should use RAG

- **Example 7 (Edge Case - Bug Condition Does NOT Hold)**: User asks "N-CRM有哪些访问关系？另外访问关系如何开权限？" with `use_rag=True`
  - **Expected Behavior**: System skips RAG (prioritize data query handling; LLM can answer knowledge part from existing knowledge)

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Access relation knowledge queries (e.g., "访问关系如何开权限", "如何提单") must continue to use RAG retrieval
- General network operations questions (e.g., "如何排查网络故障") must continue to use RAG retrieval when `use_rag=True`
- When `use_rag=False`, RAG retrieval must remain skipped regardless of message content
- RAG error handling (emitting `rag_error` event and continuing with tool calling) must remain unchanged
- Tool calling behavior in `GeneralChatToolAgent` must remain unchanged

**Scope:**
All inputs that do NOT involve access relation data queries should be completely unaffected by this fix. This includes:
- Knowledge queries about access relations (how-to, process, permissions)
- General network operations questions
- Requests with `use_rag=False`
- RAG error scenarios

## Hypothesized Root Cause

Based on the bug description and code analysis, the root cause is:

1. **Missing Pre-Processing Logic**: The `general_chat_stream_v2` function does not have any logic to detect access relation data queries before executing RAG retrieval. It unconditionally executes RAG when `use_rag=True`, regardless of message content.

2. **Incorrect Execution Order**: The current flow is:
   ```
   use_rag=True → Execute RAG retrieval → Pass enhanced prompt to LLM → LLM decides tool calling
   ```
   For access relation data queries, the correct flow should be:
   ```
   use_rag=True → Detect access relation data query → Skip RAG → Pass original prompt to LLM → LLM calls tool
   ```

3. **No Distinction Between Data and Knowledge Queries**: The system treats all access relation queries the same way, without distinguishing between:
   - Data queries (need tool calling): "N-CRM有哪些访问关系"
   - Knowledge queries (need RAG): "访问关系如何开权限"

## Correctness Properties

Property 1: Bug Condition - Access Relation Data Queries Skip RAG

_For any_ input where the bug condition holds (user message is an access relation data query and `use_rag=True`), the fixed function SHALL skip RAG retrieval, emit a `rag_skipped` event explaining the reason, and pass the original system prompt to GeneralChatToolAgent, allowing the LLM to directly call the `query_access_relations` tool.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**

Property 2: Preservation - Non-Data Query RAG Behavior

_For any_ input where the bug condition does NOT hold (knowledge queries, general questions, or `use_rag=False`), the fixed function SHALL produce exactly the same behavior as the original function, preserving RAG retrieval for knowledge queries and general questions, and skipping RAG when `use_rag=False`.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `src/api.py`

**Function**: `general_chat_stream_v2` (line ~1789)

**Specific Changes**:

1. **Add Detection Function**: Create a new helper function `is_access_relation_data_query(message: str) -> bool` before `general_chat_stream_v2`
   - Implement regex patterns to detect system identifiers (system codes, system names, deploy units, IP addresses)
   - Implement regex patterns to detect relation query keywords
   - Implement regex patterns to detect knowledge query keywords
   - Return `True` only when: has system identifier AND asks for relations AND NOT asks for knowledge

2. **Add Pre-Processing Logic**: In `general_chat_stream_v2`, before the RAG retrieval block (line ~1820)
   - Check if `request.use_rag` is `True` AND `is_access_relation_data_query(request.message)` is `True`
   - If both conditions are met, set a flag `skip_rag = True` and emit a `rag_skipped` event
   - Otherwise, set `skip_rag = False`

3. **Modify RAG Retrieval Block**: Wrap the existing RAG retrieval logic (lines ~1820-1835) in a conditional check
   - Only execute RAG retrieval if `request.use_rag` is `True` AND `skip_rag` is `False`
   - Preserve all existing RAG logic (retrieval, event emission, error handling)

4. **Event Emission**: Add a new event type `rag_skipped` with a descriptive message
   - Example: `{"type": "rag_skipped", "reason": "检测到访问关系数据查询,跳过知识库检索"}`

5. **Testing Hooks**: Ensure the detection function is testable independently from the main flow

### Pseudocode

```python
def is_access_relation_data_query(message: str) -> bool:
    """Detect if message is asking for access relation data (not knowledge)."""
    import re
    
    # Pattern for system identifiers (including IP addresses)
    system_identifier_pattern = r"(N-[A-Z]+|P-[A-Z-]+|[A-Z]+JS_[A-Z]+|客户关系管理系统|办公自动化系统|部署单元|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    
    # Pattern for relation query keywords
    relation_query_pattern = r"(有哪些访问关系|哪些系统访问|被.*访问|访问.*系统|之间.*访问关系)"
    
    # Pattern for knowledge query keywords
    knowledge_query_pattern = r"(如何|怎么|流程|权限|提单|申请|审批|管理)"
    
    has_system_identifier = bool(re.search(system_identifier_pattern, message))
    asks_for_relations = bool(re.search(relation_query_pattern, message))
    asks_for_knowledge = bool(re.search(knowledge_query_pattern, message))
    
    return has_system_identifier and asks_for_relations and not asks_for_knowledge


async def general_chat_stream_v2(request: GeneralChatRequestWithRAG):
    """流式通用聊天接口，支持 RAG 与访问关系 tool calling。"""
    
    async def event_generator():
        # ... existing session setup code ...
        
        system_prompt = build_general_chat_system_prompt(use_rag=request.use_rag)
        retrieved_docs = []
        
        # NEW: Detect if we should skip RAG for access relation data queries
        skip_rag = False
        if request.use_rag and is_access_relation_data_query(request.message):
            skip_rag = True
            yield f"data: {json.dumps({'type': 'rag_skipped', 'reason': '检测到访问关系数据查询,跳过知识库检索'}, ensure_ascii=False)}\n\n"
        
        # MODIFIED: Only execute RAG if not skipped
        if request.use_rag and not skip_rag:
            try:
                _, _, rag_chain = _init_rag_services()
                if rag_chain.has_knowledge():
                    yield f"data: {json.dumps({'type': 'rag_start', 'message': '正在检索知识库...'}, ensure_ascii=False)}\n\n"
                    _, system_prompt, retrieved_docs = rag_chain.build_enhanced_prompt(
                        request.message,
                        system_prompt_template=GENERAL_CHAT_SYSTEM_PROMPT_TEMPLATE
                    )
                    # ... existing RAG result event emission ...
            except Exception as e:
                # ... existing error handling ...
        
        # ... rest of the function remains unchanged ...
```

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that simulate access relation data queries with `use_rag=True` and observe whether RAG retrieval is executed on the UNFIXED code. Run these tests to confirm the bug exists and understand the execution path.

**Test Cases**:
1. **System Code Query Test**: Send "N-CRM有哪些访问关系" with `use_rag=True` (will execute RAG on unfixed code)
2. **Deploy Unit Query Test**: Send "CRMJS_AP部署单元有哪些访问关系" with `use_rag=True` (will execute RAG on unfixed code)
3. **Inbound Query Test**: Send "哪些系统访问N-OA" with `use_rag=True` (will execute RAG on unfixed code)
4. **IP Address Query Test**: Send "IP 为 10.0.1.10 的主机有哪些访问关系" with `use_rag=True` (will execute RAG on unfixed code)
5. **Short IP Query Test**: Send "10.0.1.10 有哪些访问关系" with `use_rag=True` (will execute RAG on unfixed code)
6. **Knowledge Query Test**: Send "访问关系如何开权限" with `use_rag=True` (should execute RAG on unfixed code - this is correct behavior)

**Expected Counterexamples**:
- RAG retrieval is executed for access relation data queries (test cases 1-3)
- `rag_start` and `rag_result` events are emitted instead of `rag_skipped`
- Possible causes: missing detection logic, incorrect execution order

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := general_chat_stream_v2_fixed(input)
  ASSERT NOT executed_rag_retrieval(result)
  ASSERT emitted_event(result, "rag_skipped")
  ASSERT tool_called_eventually(result, "query_access_relations")
END FOR
```

**Test Cases**:
1. **System Code Query**: "N-CRM有哪些访问关系" with `use_rag=True` → Should skip RAG, emit `rag_skipped`, call tool
2. **Deploy Unit Query**: "CRMJS_AP部署单元有哪些访问关系" with `use_rag=True` → Should skip RAG, emit `rag_skipped`, call tool
3. **Inbound Query**: "哪些系统访问N-OA" with `use_rag=True` → Should skip RAG, emit `rag_skipped`, call tool
4. **Both Direction Query**: "N-CRM和N-OA之间有哪些访问关系" with `use_rag=True` → Should skip RAG, emit `rag_skipped`, call tool
5. **System Name Query**: "客户关系管理系统有哪些访问关系" with `use_rag=True` → Should skip RAG, emit `rag_skipped`, call tool
6. **IP Address Query**: "IP 为 10.0.1.10 的主机有哪些访问关系" with `use_rag=True` → Should skip RAG, emit `rag_skipped`, call tool
7. **Short IP Query**: "10.0.1.10 有哪些访问关系" with `use_rag=True` → Should skip RAG, emit `rag_skipped`, call tool
8. **IP Query Variant**: "查询 10.0.1.10 的访问关系" with `use_rag=True` → Should skip RAG, emit `rag_skipped`, call tool

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT general_chat_stream_v2_original(input) = general_chat_stream_v2_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for knowledge queries and general questions, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Knowledge Query Preservation**: Observe that "访问关系如何开权限" with `use_rag=True` executes RAG on unfixed code, then verify this continues after fix
2. **General Question Preservation**: Observe that "如何排查网络故障" with `use_rag=True` executes RAG on unfixed code, then verify this continues after fix
3. **RAG Disabled Preservation**: Observe that any message with `use_rag=False` skips RAG on unfixed code, then verify this continues after fix
4. **RAG Error Preservation**: Observe that RAG errors emit `rag_error` event and continue on unfixed code, then verify this continues after fix
5. **Mixed Query Preservation**: Observe that "N-CRM有哪些访问关系？另外访问关系如何开权限？" with `use_rag=True` skips RAG on fixed code (prioritize data query)

### Unit Tests

- Test `is_access_relation_data_query` function with various message patterns:
  - System code patterns (N-CRM, P-DB-MAIN)
  - System name patterns (客户关系管理系统)
  - Deploy unit patterns (CRMJS_AP)
  - IP address patterns (10.0.1.10, 192.168.1.1)
  - Relation query keywords (有哪些访问关系, 哪些系统访问)
  - Knowledge query keywords (如何, 流程, 权限)
  - Edge cases (mixed queries, no system identifier, no relation keywords)
- Test RAG skipping logic in `general_chat_stream_v2`:
  - Verify `rag_skipped` event is emitted for data queries
  - Verify RAG is executed for knowledge queries
  - Verify RAG is skipped when `use_rag=False`
- Test event emission order and content

### Property-Based Tests

- Generate random access relation data queries with various system identifiers (including IP addresses) and verify RAG is skipped
- Generate random knowledge queries and verify RAG is executed
- Generate random general questions and verify RAG behavior is preserved
- Test across many message variations to ensure detection logic is robust
- Generate random IP addresses and verify they are correctly detected as system identifiers

### Integration Tests

- Test full flow from request to response for access relation data queries
- Test full flow for knowledge queries to ensure RAG is still used
- Test tool calling behavior after RAG skipping
- Test event stream completeness and order
