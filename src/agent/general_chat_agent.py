import json
import time
from typing import Any, Callable, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from ..integrations.llm_client import LLMClient
from ..integrations.network_tools import NetworkTools
from .query_intents import detect_host_port_status_query


GENERAL_CHAT_SYSTEM_PROMPT_TEMPLATE = """你是一个网络运维助手，负责以下任务：

1. 回答一般网络运维与故障诊断问题
2. 查询应用系统之间的网络访问关系

{rag_instruction}

当用户询问某个主机 IP 上的 TCP 端口是否正在监听、是否存活、是否正常时，必须先调用 check_port_alive 工具再回答。
示例：用户问“请帮我检查 2.7.8.6主机上的 8008 是否正常监听。”时，应调用 check_port_alive(host="2.7.8.6", port=8008)。

当用户询问访问关系时，你必须优先调用 query_access_relations 工具，禁止凭记忆、猜测、示例数据或常识直接编造访问关系。

访问关系查询的参数提取规则如下：

一、识别实体
1. 系统编码，例如 N-CRM、N-OA、N-AQM、P-DB-MAIN。
2. 中文系统名，例如 客户关系管理系统、办公自动化系统。
3. 部署单元，例如 CRMJS_AP、OAJS_AP、OAJS_WEB。
4. 对端系统，例如“X 和 Y 之间有哪些访问关系”里的 Y。

二、默认语义
1. 用户说“X有哪些访问关系”：
   默认理解为 X 主动访问其他系统，direction="outbound"。
2. 用户说“哪些系统访问X”或“X被哪些系统访问”：
   理解为其他系统访问 X，direction="inbound"。
3. 用户说“X和Y之间有哪些访问关系”：
   理解为查询 X 与 Y 的双向关系，direction="both"。
4. 用户说“X 的某部署单元有哪些访问关系”：
   在 X 基础上追加 deploy_unit 参数，并保持默认 direction="outbound"。
5. 不要把 inbound 和 outbound 混淆。

三、工具调用规则
1. 只要问题属于访问关系查询，就先调用 query_access_relations。
2. 如果能明确识别系统编码，优先传 system_code。
3. 如果没有系统编码但能明确识别中文系统名，传 system_name。
4. 如果同时识别到部署单元，传 deploy_unit。
5. 如果识别到两个系统，传 system_code 或 system_name 与 peer_system_code 或 peer_system_name。
6. 如果实体不明确，且无法安全推断，不要猜测，先用一句简短的话追问用户。

四、示例
- 用户：N-CRM有哪些访问关系
  你应调用 query_access_relations(system_code="N-CRM", direction="outbound")
- 用户：N-CRM的CRMJS_AP部署单元有哪些访问关系
  你应调用 query_access_relations(system_code="N-CRM", deploy_unit="CRMJS_AP", direction="outbound")
- 用户：哪些系统访问N-CRM
  你应调用 query_access_relations(system_code="N-CRM", direction="inbound")
- 用户：N-CRM和N-OA之间有哪些访问关系
  你应调用 query_access_relations(system_code="N-CRM", peer_system_code="N-OA", direction="both")
- 用户：客户关系管理系统有哪些访问关系
  你应调用 query_access_relations(system_name="客户关系管理系统", direction="outbound")

五、回答规则
1. 必须基于工具返回结果回答。
2. 如果有结果，先用一句话总结（带上匹配到的系统编码和中文名），再给 Markdown 表格。
3. Markdown 表格必须严格按以下列顺序输出，一列都不能少：
   | 源系统 | 源部署单元 | 源IP | 目的系统 | 目的部署单元 | 目的IP | 协议 | 端口 |
   - 源系统 列的值格式为 "{{src_system}} {{src_system_name}}"，若 src_system_name 为空则只写 src_system。
   - 目的系统 列的值为 dst_system（工具结果中没有目的系统中文名）。
   - IP 或端口字段含有多个值时（换行分隔），在单元格内用 <br> 连接，避免破坏表格结构。
4. 如果无结果，明确说明“未找到相关访问关系记录”。
5. 不要补充工具结果中不存在的系统、部署单元、IP、协议或端口。
6. 如果用户问的是一般运维问题而不是访问关系查询，则正常回答，不调用该工具。
"""


class QueryAccessRelationsInput(BaseModel):
    system_code: Optional[str] = Field(
        default=None,
        description="主查询系统编码，例如 N-CRM、N-OA"
    )
    system_name: Optional[str] = Field(
        default=None,
        description="主查询系统中文名称，例如 客户关系管理系统"
    )
    deploy_unit: Optional[str] = Field(
        default=None,
        description="部署单元名称，例如 CRMJS_AP、OAJS_AP、OAJS_WEB"
    )
    direction: str = Field(
        default="outbound",
        description='查询方向，只能是 outbound、inbound、both'
    )
    peer_system_code: Optional[str] = Field(
        default=None,
        description="对端系统编码，例如 N-OA"
    )
    peer_system_name: Optional[str] = Field(
        default=None,
        description="对端系统中文名称"
    )
    src_ip: Optional[str] = Field(
        default=None,
        description="源 IP 地址，例如 10.0.1.10、192.168.1.1"
    )
    dst_ip: Optional[str] = Field(
        default=None,
        description="目标 IP 地址，例如 10.0.2.20、192.168.1.100"
    )


class CheckPortAliveInput(BaseModel):
    host: str = Field(description="Target host IP address, for example 2.7.8.6")
    port: int = Field(description="TCP port to check, from 1 to 65535")
    timeout: int = Field(default=30, description="Command timeout in seconds")


class GeneralChatToolAgent:
    """Lightweight tool-calling agent for general chat."""

    def __init__(
        self,
        llm_client: LLMClient,
        session_manager: Any,
        session_id: str,
        event_callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
        max_tool_rounds: int = 3
    ):
        self.llm_client = llm_client
        self.session_manager = session_manager
        self.session_id = session_id
        self.event_callback = event_callback
        self.max_tool_rounds = max_tool_rounds
        self.network_tools = NetworkTools(use_router=True)
        self.tools = self._create_tools()
        self._tools_by_name = {tool.name: tool for tool in self.tools}

    def _create_tools(self) -> List[StructuredTool]:
        async def query_access_relations_func(
            system_code: Optional[str] = None,
            system_name: Optional[str] = None,
            deploy_unit: Optional[str] = None,
            direction: str = "outbound",
            peer_system_code: Optional[str] = None,
            peer_system_name: Optional[str] = None,
            src_ip: Optional[str] = None,
            dst_ip: Optional[str] = None
        ) -> Dict[str, Any]:
            if not hasattr(self.session_manager, "db") or not self.session_manager.db:
                return {
                    "success": False,
                    "error": "访问关系数据库不可用",
                    "data": "访问关系数据库不可用"
                }

            result = await self.session_manager.db.query_access_relations(
                system_code=system_code,
                system_name=system_name,
                deploy_unit=deploy_unit,
                direction=direction,
                peer_system_code=peer_system_code,
                peer_system_name=peer_system_name,
                src_ip=src_ip,
                dst_ip=dst_ip,
                page=1,
                page_size=50,
            )
            total = result.get("total", 0)
            query = {
                "system_code": system_code,
                "system_name": system_name,
                "deploy_unit": deploy_unit,
                "direction": direction,
                "peer_system_code": peer_system_code,
                "peer_system_name": peer_system_name,
                "src_ip": src_ip,
                "dst_ip": dst_ip,
            }
            return {
                "success": True,
                "data": self._build_tool_summary(query=query, total=total),
                "query": query,
                "total": total,
                "items": result.get("items", []),
            }

        query_tool = StructuredTool.from_function(
            coroutine=query_access_relations_func,
            name="query_access_relations",
            description=(
                "查询应用系统网络访问关系。"
                "当用户询问某系统、中文系统名、部署单元、IP 地址、或两个系统之间有哪些访问关系时使用。"
                "支持通过 src_ip 或 dst_ip 参数直接查询 IP 地址的访问关系。"
                "direction=outbound 表示该系统访问别人，"
                "direction=inbound 表示别人访问该系统，"
                "direction=both 表示双向关系。"
            ),
            args_schema=QueryAccessRelationsInput,
        )

        async def check_port_alive_func(
            host: str,
            port: int,
            timeout: int = 30
        ) -> Dict[str, Any]:
            result = await self.network_tools.check_port_alive(host, port, timeout)
            if "data" not in result:
                if result.get("success"):
                    state = "listening" if result.get("port_alive") else "not listening"
                    result["data"] = f"{host}:{port} is {state}"
                else:
                    result["data"] = result.get("stderr") or f"Failed to check {host}:{port}"
            return result

        port_check_tool = StructuredTool.from_function(
            coroutine=check_port_alive_func,
            name="check_port_alive",
            description=(
                "Check whether a TCP port is listening on a specified host IP. "
                "Use this when the user asks whether a host port is listening, alive, or normal."
            ),
            args_schema=CheckPortAliveInput,
        )

        return [query_tool, port_check_tool]

    def _build_tool_summary(self, query: Dict[str, Any], total: int) -> str:
        subject = query.get("system_code") or query.get("system_name") or "未指定系统"
        deploy_unit = query.get("deploy_unit")
        peer = query.get("peer_system_code") or query.get("peer_system_name")
        direction = query.get("direction") or "outbound"
        direction_label = {
            "outbound": "出向",
            "inbound": "入向",
            "both": "双向",
        }.get(direction, direction)

        parts = [f"主对象: {subject}", f"方向: {direction_label}", f"命中记录: {total} 条"]
        if deploy_unit:
            parts.append(f"部署单元: {deploy_unit}")
        if peer:
            parts.append(f"对端系统: {peer}")
        return "；".join(parts)

    def _build_langchain_messages(
        self,
        session_messages: List[Dict[str, Any]],
        system_prompt: str
    ) -> List[Any]:
        messages: List[Any] = [SystemMessage(content=system_prompt)]
        latest_user_content = None
        for msg in reversed(session_messages):
            if msg.get("role") == "user":
                latest_user_content = self._stringify_content(msg.get("content", ""))
                break

        host_port_status_query = detect_host_port_status_query(latest_user_content or "")
        if host_port_status_query:
            messages.append(
                SystemMessage(
                    content=(
                        "当前用户请求已识别为主机端口状态查询。"
                        f"目标主机: {host_port_status_query['host']}。"
                        f"目标端口: {host_port_status_query['port']}。"
                        "你必须先调用 check_port_alive 工具，再基于工具结果回答。"
                    )
                )
            )

        for msg in session_messages:
            metadata = msg.get("metadata") or {}
            tool_call = metadata.get("tool_call")
            if tool_call:
                tool_name = tool_call.get("name", "unknown_tool")
                arguments = tool_call.get("arguments") or {}
                result = tool_call.get("result") or {}
                history_summary = {
                    "tool": tool_name,
                    "arguments": arguments,
                    "summary": result.get("data"),
                    "total": result.get("total"),
                }
                messages.append(
                    SystemMessage(
                        content=(
                            "以下是本会话内已经执行过的历史工具调用结果，可作为后续追问的上下文参考："
                            f"{json.dumps(history_summary, ensure_ascii=False)}"
                        )
                    )
                )
                continue

            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
            elif role == "system":
                messages.append(SystemMessage(content=content))

        return messages

    async def _emit_event(self, event: Dict[str, Any]) -> None:
        if self.event_callback:
            await self.event_callback(event)

    async def _save_tool_call_history(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Dict[str, Any],
        execution_time: float
    ) -> None:
        await self.session_manager.add_message(
            session_id=self.session_id,
            role="assistant",
            content=f"执行工具: {tool_name}",
            metadata={
                "tool_call": {
                    "name": tool_name,
                    "arguments": arguments,
                    "result": result,
                    "execution_time": round(execution_time, 2),
                }
            }
        )

    def _stringify_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        parts.append(text)
                elif item:
                    parts.append(str(item))
            return "".join(parts)
        return str(content or "")

    async def run(
        self,
        session_messages: List[Dict[str, Any]],
        system_prompt: str
    ) -> str:
        messages = self._build_langchain_messages(
            session_messages=session_messages,
            system_prompt=system_prompt
        )
        tool_step = 1

        for _ in range(self.max_tool_rounds):
            response = self.llm_client.invoke_langchain_messages_with_tools(
                messages=messages,
                tools=self.tools,
                temperature=0.2,
            )
            messages.append(response)

            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                return self._stringify_content(response.content)

            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                arguments = tool_call.get("args") or tool_call.get("arguments") or {}
                tool = self._tools_by_name.get(tool_name)
                if tool is None:
                    result = {
                        "success": False,
                        "error": f"未知工具: {tool_name}",
                        "data": f"未知工具: {tool_name}",
                    }
                else:
                    await self._emit_event({
                        "type": "tool_start",
                        "step": tool_step,
                        "tool": tool_name,
                        "arguments": arguments,
                    })

                    start_time = time.perf_counter()
                    try:
                        result = await tool.ainvoke(arguments)
                    except Exception as exc:
                        result = {
                            "success": False,
                            "error": str(exc),
                            "data": f"工具执行失败: {exc}",
                        }
                    execution_time = round(time.perf_counter() - start_time, 2)
                    result["execution_time"] = execution_time

                    await self._emit_event({
                        "type": "tool_result",
                        "step": tool_step,
                        "tool": tool_name,
                        "result": result,
                        "execution_time": execution_time,
                    })
                    await self._save_tool_call_history(
                        tool_name=tool_name,
                        arguments=arguments,
                        result=result,
                        execution_time=execution_time,
                    )

                messages.append(
                    ToolMessage(
                        content=json.dumps(result, ensure_ascii=False),
                        tool_call_id=tool_call.get("id") or f"tool_call_{tool_step}",
                    )
                )
                tool_step += 1

        messages.append(HumanMessage(content="请基于已经获得的工具结果给出最终答复，不要继续调用工具。"))
        final_response = self.llm_client.invoke_langchain_messages(
            messages=messages,
            temperature=0.2,
        )
        return self._stringify_content(final_response.content)
