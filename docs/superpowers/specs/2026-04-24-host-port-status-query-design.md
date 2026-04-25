# Host Port Status Query Design

## Summary

Add a shared host-port status query detector for general chat. It identifies requests that ask for the status of a specific port on a single host, skips knowledge-base retrieval for those requests, and lets the general chat LLM drive `check_port_alive` tool calling and final summarization.

The design keeps the responsibilities split:

- Rules handle early classification and RAG skipping.
- The general chat LLM handles tool selection and final response generation.

## Problem

The current system already skips RAG for access relation data queries, but host port status checks are not handled the same way end to end. The desired behavior is:

1. Requests like "请帮我检查10.0.2.20 主机上的 8008 是否正常监听？" should not query the knowledge base.
2. They should remain in the `general_chat` path instead of entering diagnosis or clarify flows.
3. The `check_port_alive` tool should still be selected by the LLM, not invoked by hardcoded bypass logic.
4. The LLM should produce the final answer from the tool result.

## Scope

This change only covers questions about the status of a port on a single host.

Included:

- Single host IP
- Single valid port number
- Status-oriented wording such as listening, normal, alive, service port

Excluded:

- Method questions such as "如何检查端口是否监听"
- Multi-host connectivity or diagnosis requests
- General port troubleshooting questions

## Detection Rule

Introduce a shared rule-based detector:

`detect_host_port_status_query(message: str) -> Optional[dict]`

Suggested return value:

```python
{
    "host": "10.0.2.20",
    "port": 8008,
}
```

Return `None` when the message is not a direct host-port status query.

The detector should require all of the following:

1. Exactly one host IP address in the message
2. At least one valid port number in the message, with the intended target port extracted
3. Status-query keywords such as:
   - `监听`
   - `正常`
   - `存活`
   - `服务端口`
   - `port`
   - `listen`
   - `listening`
   - `alive`
4. No evidence that the user is asking for a method, process, or troubleshooting guide rather than checking a concrete host-port state

## Integration Points

### 1. Rule Intent Router

Reuse the shared detector in `rule_intent_router`.

Behavior:

- If the detector matches, classify as a hard `general_chat` result
- Use a stable reason such as `host_port_listening_check`

This keeps the request out of diagnosis and clarify flows.

### 2. General Chat RAG Skip

Reuse the same detector in `general_chat_stream_v2`.

Behavior:

- When `use_rag=True` and the detector matches, set `skip_rag=True`
- Emit a `rag_skipped` event with a reason that explicitly says the request is a host port status query
- Do not emit `rag_start` or `rag_result`

This mirrors the existing access relation data-query behavior.

### 3. General Chat Tool Calling

Keep tool invocation LLM-driven inside `GeneralChatToolAgent`.

Behavior:

- Remove any hardcoded direct tool bypass for host-port checks
- Add the detector result as structured context for the LLM when the request matches
- Keep the existing tool definitions, including `check_port_alive`
- Keep the system prompt explicit that such requests must call `check_port_alive`

The detector is used to shape routing and context, but not to replace tool calling with imperative code.

### 4. Final Response Generation

The final answer remains LLM-generated.

Behavior:

- The LLM sees the tool result in the message history
- The LLM produces the final answer based on that result
- No fixed response template should short-circuit the LLM

## Module Placement

Create a shared detector module under the agent layer, for example:

- `src/agent/query_intents.py`

Reasoning:

- This is intent-level logic shared by routing and general chat
- It is not a generic low-level utility

## Error Handling

If tool execution fails:

- The tool result should still be recorded in tool history
- The LLM should summarize the failure based on the tool result
- The system should not silently fall back to knowledge-base answers for the same request

If the detector does not match:

- Existing RAG and general chat behavior remains unchanged

## Test Plan

### Detection Tests

- Match: "请帮我检查10.0.2.20 主机上的 8008 是否正常监听？"
- Match: "检查 10.0.2.20 的 8008 端口是否存活"
- No match: "如何检查端口是否监听"
- No match: "10.0.1.10 到 10.0.2.20 的 8008 不通"

### Routing Tests

- Matching request is classified as hard `general_chat`
- Hybrid routing does not escalate it into diagnosis or clarify

### RAG Skip Tests

- Matching request with `use_rag=True` emits `rag_skipped`
- Matching request does not emit `rag_start`
- Matching request does not emit `rag_result`

### Tool Calling Tests

- Matching request still reaches `GeneralChatToolAgent`
- LLM tool-calling path invokes `check_port_alive`
- Final response is generated after tool execution rather than by a hardcoded direct return

### Preservation Tests

- Access relation data queries still skip RAG
- Method questions about how to check ports can still use RAG
- General network knowledge queries remain unchanged

## Non-Goals

- Reworking the diagnosis flow
- Adding new network tools
- Supporting hostnames or asset names in this change
- Solving all port-related intents in one pass

## Risks

The main risk is overmatching broad port-related questions and suppressing RAG when the user is really asking for guidance rather than a concrete check. The detector must therefore stay narrow and require both a concrete host IP and concrete status-query wording.

## Recommended Implementation Order

1. Add detector tests
2. Implement the shared detector
3. Wire it into `rule_intent_router`
4. Wire it into `general_chat_stream_v2` RAG skipping
5. Remove hardcoded direct tool bypass in `GeneralChatToolAgent`
6. Pass detector context into the LLM tool-calling flow
7. Run routing, RAG-skip, agent, and tool tests
