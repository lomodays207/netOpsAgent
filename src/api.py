"""
FastAPI HTTP 服务 - 提供网络故障诊断接口

启动方式：
    uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload

API 文档：
    http://localhost:8000/docs
"""
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Optional
import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os

from .agent import IntentRouter, NLU
from .agent.general_chat_agent import (
    GENERAL_CHAT_SYSTEM_PROMPT_TEMPLATE,
    GeneralChatToolAgent,
)
from .agent.llm_agent import LLMAgent, NeedUserInputException
from .integrations import LLMClient
from .session_manager import get_session_manager, DiagnosisSession

# 加载环境变量
load_dotenv()

# 创建 FastAPI 应用
app = FastAPI(
    title="netOpsAgent API",
    description="智能网络故障排查 API",
    version="1.0.0"
)

# 挂载静态文件目录（如果存在）
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# 初始化会话管理器
session_manager = get_session_manager()
intent_router = IntentRouter()


@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    # 初始化数据库
    await session_manager.initialize()
    # 启动会话清理任务
    await session_manager.start_cleanup()
    if hasattr(session_manager, "db") and session_manager.db:
        await session_manager.db.seed_access_assets_if_empty()
    print("[API] 会话管理器已启动")


# 请求模型
class DiagnoseRequest(BaseModel):
    """诊断请求"""
    description: str = Field(..., description="故障描述，例如：'server1到server2端口80不通'", min_length=1)
    use_llm: bool = Field(default=True, description="是否使用 LLM 解析和诊断")
    verbose: bool = Field(default=False, description="是否返回详细的工具调用信息")
    session_id: Optional[str] = Field(None, description="可选的会话ID，用于在现有会话中开始新诊断")

    class Config:
        json_schema_extra = {
            "example": {
                "description": "10.0.1.10到10.0.2.20端口80不通",
                "use_llm": True,
                "verbose": False
            }
        }


class ChatAnswerRequest(BaseModel):
    """用户回答请求"""
    session_id: str = Field(..., description="会话ID")
    answer: str = Field(..., description="用户的回答", min_length=1)

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "task_20260123105030_a1b2c3d4",
                "answer": "目标服务器上有防火墙，配置为仅允许特定IP访问"
            }
        }


class GeneralChatRequest(BaseModel):
    """通用聊天请求"""
    message: str = Field(..., description="用户的消息", min_length=1)
    session_id: Optional[str] = Field(None, description="可选的会话ID，用于继续现有会话")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "你好，请问你能做什么？",
                "session_id": None
            }
        }


class ChatStreamRequest(BaseModel):
    """Unified chat request routed on the backend."""
    message: str = Field(..., min_length=1, description="User message")
    session_id: Optional[str] = Field(None, description="Optional session id")
    use_llm: bool = Field(default=True, description="Use LLM-powered diagnosis parsing")
    verbose: bool = Field(default=False, description="Include verbose tool output in diagnosis")
    use_rag: bool = Field(default=True, description="Use knowledge retrieval in general chat")


class RenameSessionRequest(BaseModel):
    """重命名会话请求"""
    new_name: str = Field(..., description="新的会话名称", min_length=1, max_length=500)

    class Config:
        json_schema_extra = {
            "example": {
                "new_name": "服务器连接问题诊断"
            }
        }



# 响应模型
class DiagnoseResponse(BaseModel):
    """诊断响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="诊断状态：success | failed")
    root_cause: Optional[str] = Field(None, description="根因分析")
    confidence: Optional[float] = Field(None, description="置信度 (0-100)")
    execution_time: Optional[float] = Field(None, description="执行时间（秒）")
    steps: list = Field(default_factory=list, description="执行的诊断步骤")
    suggestions: list = Field(default_factory=list, description="修复建议")
    tool_calls: Optional[list] = Field(None, description="LLM工具调用历史（显示分析过程）")
    error: Optional[str] = Field(None, description="错误信息（如果失败）")


def generate_task_id() -> str:
    """生成任务ID"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    short_uuid = str(uuid.uuid4())[:8]
    return f"task_{timestamp}_{short_uuid}"


def build_general_chat_system_prompt(use_rag: bool = False) -> str:
    """Build the general chat prompt with optional RAG guidance."""
    rag_instruction = (
        "如果知识库检索返回了参考资料，请优先依据参考资料回答一般网络运维问题。"
        if use_rag else
        "当前未启用知识库增强；对于一般网络运维问题，可基于你的专业知识回答。"
    )
    return GENERAL_CHAT_SYSTEM_PROMPT_TEMPLATE.format(rag_instruction=rag_instruction)


def is_access_relation_data_query(message: str) -> bool:
    """
    检测消息是否为访问关系数据查询（而非知识咨询）
    
    访问关系数据查询的特征：
    1. 包含系统标识符（系统编码、系统名称或部署单元）
    2. 询问访问关系数据
    3. 不是询问知识性问题（如何、流程、权限等）
    
    Args:
        message: 用户消息
        
    Returns:
        True 如果是访问关系数据查询，False 否则
        
    Examples:
        >>> is_access_relation_data_query("N-CRM有哪些访问关系")
        True
        >>> is_access_relation_data_query("访问关系如何开权限")
        False
        >>> is_access_relation_data_query("CRMJS_AP部署单元有哪些访问关系")
        True
    """
    import re
    
    # 系统标识符模式：系统编码、系统名称、部署单元
    # 匹配系统编码（N-XXX, P-XXX-XXX）、部署单元（XXXJS_XXX）、或包含"系统"的中文名称
    # 也匹配常见系统简称（如"办公自动化"、"客户关系管理"等，可能不带"系统"二字）
    system_identifier_pattern = r"(N-[A-Z]+|P-[A-Z-]+|[A-Z]+JS_[A-Z]+|[\u4e00-\u9fa5]{2,}系统|客户关系管理|办公自动化|部署单元)"
    
    # 访问关系查询关键词
    relation_query_pattern = r"(有哪些访问关系|哪些系统访问|被.*访问|访问.*系统|之间.*访问关系)"
    
    # 知识性问题关键词（如果匹配，则不应跳过 RAG）
    # 使用更严格的模式，避免匹配系统名称中的"管理"字
    # 要求知识关键词前后有特定上下文或位于句子开头/结尾
    knowledge_query_pattern = r"(如何|怎么|流程|权限|提单|申请|审批)(?!系统)|(?<!关系)管理(?!系统)"
    
    has_system_identifier = bool(re.search(system_identifier_pattern, message))
    asks_for_relations = bool(re.search(relation_query_pattern, message))
    asks_for_knowledge = bool(re.search(knowledge_query_pattern, message))
    
    # 只有当包含系统标识符、询问访问关系、且不是知识性问题时，才是数据查询
    return has_system_identifier and asks_for_relations and not asks_for_knowledge


def create_general_chat_task(session_id: str, user_message: str):
    """Create the lightweight task object used by session storage."""
    from .models.task import DiagnosticTask, FaultType, Protocol

    return DiagnosticTask(
        task_id=session_id,
        user_input=user_message,
        source="general_chat",
        target="general_chat",
        protocol=Protocol.ICMP,
        fault_type=FaultType.CONNECTIVITY,
        port=None,
    )


async def _ensure_general_chat_session(session_id: Optional[str], message: str):
    """Get or create a lightweight general-chat session."""
    if session_id:
        session = await session_manager.get_session(session_id)
        if session:
            return session_id, session

    resolved_session_id = session_id or generate_task_id()
    session = session_manager.create_session(
        session_id=resolved_session_id,
        task=create_general_chat_task(resolved_session_id, message),
        llm_client=None,
        agent=None,
    )
    return resolved_session_id, session


def _build_clarify_stream_response(
    *,
    session_id: Optional[str],
    user_message: str,
    clarify_message: str,
) -> StreamingResponse:
    async def event_generator():
        resolved_session_id, _ = await _ensure_general_chat_session(session_id, user_message)
        await session_manager.add_message(resolved_session_id, "user", user_message)
        await session_manager.add_message(resolved_session_id, "assistant", clarify_message)
        session_manager.update_session(resolved_session_id, status="completed")

        yield f"data: {json.dumps({'type': 'start', 'session_id': resolved_session_id}, ensure_ascii=False)}\n\n"
        chunk_size = 10
        for index in range(0, len(clarify_message), chunk_size):
            chunk = clarify_message[index:index + chunk_size]
            yield f"data: {json.dumps({'type': 'content', 'text': chunk}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.02)

        yield f"data: {json.dumps({'type': 'complete', 'session_id': resolved_session_id, 'rag_used': False}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/")
async def root():
    """根路径 - 返回前端页面或 API 信息"""
    # 如果存在前端页面，返回前端页面
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    # 否则返回 API 信息
    return {
        "name": "netOpsAgent API",
        "version": "1.0.0",
        "description": "智能网络故障排查 API",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        # 尝试检查 LLM 客户端是否可用（不实际创建）
        import os
        api_key = os.getenv("API_KEY", "")
        llm_available = bool(api_key)
        
        return {
            "status": "healthy",
            "llm_available": llm_available,
            "database": "sqlite",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "llm_available": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


@app.post("/api/v1/chat/stream")
async def chat_stream(request: ChatStreamRequest):
    """Unified streaming entrypoint with backend intent routing."""
    session = await session_manager.get_session(request.session_id) if request.session_id else None
    decision = intent_router.route_message(request.message, session=session)

    if decision.route == "start_diagnosis":
        return await diagnose_stream(
            DiagnoseRequest(
                description=request.message,
                use_llm=request.use_llm,
                verbose=request.verbose,
                session_id=request.session_id,
            )
        )

    if decision.route == "continue_diagnosis":
        if not request.session_id:
            return _build_clarify_stream_response(
                session_id=None,
                user_message=request.message,
                clarify_message=(
                    "当前没有可继续的诊断会话。"
                    "如果你要我直接开始诊断，请提供源主机、目标主机和端口。"
                ),
            )
        return await chat_answer(
            ChatAnswerRequest(
                session_id=request.session_id,
                answer=request.message,
            )
        )

    if decision.route == "clarify":
        return _build_clarify_stream_response(
            session_id=request.session_id,
            user_message=request.message,
            clarify_message=decision.clarify_message
            or (
                "你是想了解排查方法，还是要我直接开始诊断？"
                "如果要直接诊断，请提供源主机、目标主机和端口。"
            ),
        )

    return await general_chat_stream_v2(
        GeneralChatRequestWithRAG(
            message=request.message,
            session_id=request.session_id,
            use_rag=request.use_rag,
        )
    )


@app.post("/api/v1/diagnose", response_model=DiagnoseResponse)
async def diagnose(request: DiagnoseRequest):
    """
    执行网络故障诊断

    ### 请求示例：
    ```json
    {
        "description": "10.0.1.10到10.0.2.20端口80不通",
        "use_llm": true,
        "verbose": false
    }
    ```

    ### 响应示例：
    ```json
    {
        "task_id": "task_20260123105030_a1b2c3d4",
        "status": "success",
        "root_cause": "目标服务器防火墙策略阻止了80端口访问",
        "confidence": 85.0,
        "execution_time": 8.5,
        "steps": [...],
        "suggestions": ["在目标服务器开放80端口的防火墙规则"]
    }
    ```
    """
    task_id = generate_task_id()

    try:
        # 1. 初始化 LLM 客户端
        llm_client = LLMClient()

        # 2. 使用 NLU 解析用户输入
        if request.use_llm:
            nlu = NLU(llm_client)
            task = nlu.parse_user_input(request.description, task_id)
        else:
            # 使用规则解析
            from .models.task import DiagnosticTask, FaultType, Protocol
            from .utils.input_validator import extract_network_info
            
            # 提取并验证网络信息
            source, target, port, error = extract_network_info(request.description)
            
            # 如果验证失败,抛出异常
            if error:
                raise ValueError(error)

            if "端口" in request.description or "telnet" in request.description.lower():
                fault_type = FaultType.PORT_UNREACHABLE
                protocol = Protocol.TCP
            else:
                fault_type = FaultType.CONNECTIVITY
                protocol = Protocol.ICMP

            task = DiagnosticTask(
                task_id=task_id,
                user_input=request.description,
                source=source,
                target=target,
                protocol=protocol,
                fault_type=fault_type,
                port=port
            )

        # 3. 执行诊断
        agent = LLMAgent(llm_client=llm_client, verbose=request.verbose)
        report = await agent.diagnose(task, session_id=task_id, session_manager=session_manager)

        # 保存助手最终结论
        if report.root_cause:
            await session_manager.add_message(
                session_id=task_id,
                role="assistant",
                content=f"诊断完成。根因：{report.root_cause}",
                metadata={"report": {
                    "root_cause": report.root_cause,
                    "confidence": report.confidence,
                    "suggestions": report.fix_suggestions
                }}
            )

        # 4. 构造响应
        # 提取工具调用历史
        tool_calls = report.metadata.get("tool_call_history", []) if report.metadata else []

        return DiagnoseResponse(
            task_id=task_id,
            status="success",
            root_cause=report.root_cause,
            confidence=report.confidence * 100,  # 转换为百分比
            execution_time=report.total_time,
            steps=[
                {
                    "step": step.step_number,
                    "name": step.step_name,
                    "command": step.command_result.command if step.command_result else None,
                    "success": step.success,
                    "output": step.command_result.stdout if (request.verbose and step.command_result) else None
                }
                for step in report.executed_steps
            ],
            suggestions=report.fix_suggestions,
            tool_calls=tool_calls if tool_calls else None
        )

    except ValueError as e:
        # 输入验证错误，返回友好提示
        return DiagnoseResponse(
            task_id=task_id,
            status="failed",
            error=f"输入验证失败: {str(e)}。请检查输入格式后重新提交。"
        )
    except Exception as e:
        # 其他错误处理
        return DiagnoseResponse(
            task_id=task_id,
            status="failed",
            error=str(e)
        )


@app.post("/api/v1/diagnose/stream")
async def diagnose_stream(request: DiagnoseRequest):
    """
    流式返回诊断过程（SSE）

    ### 请求示例：
    ```json
    {
        "description": "10.0.1.10到10.0.2.20端口80不通",
        "use_llm": true,
        "verbose": false
    }
    ```

    ### 响应格式：
    Server-Sent Events (SSE) 流式推送，事件类型包括：
    - start: 诊断开始
    - tool_start: 工具调用开始
    - tool_result: 工具调用结果
    - complete: 诊断完成
    - error: 错误信息
    """
    async def event_generator():
        try:
            # 创建事件队列
            event_queue = asyncio.Queue()

            # 发送初始注释（保持连接）
            yield ": SSE stream started\n\n"

            # 定义回调函数
            async def callback(event):
                await event_queue.put(event)
                # 强制让出控制权，确保事件被立即发送
                await asyncio.sleep(0)

            # 启动诊断任务（后台）
            async def run_diagnosis():
                try:
                    # 1. 初始化 LLM 客户端
                    llm_client = LLMClient()

                    # 2. 使用 NLU 解析用户输入
                    # 如果提供了 session_id，使用现有会话ID，否则生成新ID
                    task_id = request.session_id if request.session_id else generate_task_id()
                    
                    if request.use_llm:
                        nlu = NLU(llm_client)
                        task = nlu.parse_user_input(request.description, task_id)
                    else:
                        # 使用规则解析
                        from .models.task import DiagnosticTask, FaultType, Protocol
                        from .utils.input_validator import extract_network_info
                        
                        # 提取并验证网络信息
                        source, target, port, error = extract_network_info(request.description)
                        
                        # 如果验证失败,抛出异常
                        if error:
                            raise ValueError(error)

                        if "端口" in request.description or "telnet" in request.description.lower():
                            fault_type = FaultType.PORT_UNREACHABLE
                            protocol = Protocol.TCP
                        else:
                            fault_type = FaultType.CONNECTIVITY
                            protocol = Protocol.ICMP

                        task = DiagnosticTask(
                            task_id=task_id,
                            user_input=request.description,
                            source=source,
                            target=target,
                            protocol=protocol,
                            fault_type=fault_type,
                            port=port
                        )

                    # 3. 执行诊断（带事件回调）
                    agent = LLMAgent(llm_client=llm_client, verbose=request.verbose)

                    # 创建或获取会话
                    if request.session_id:
                        # 尝试获取现有会话
                        session = await session_manager.get_session(request.session_id)
                        if session:
                            # 更新现有会话的任务和代理
                            session_manager.update_session(
                                request.session_id, 
                                task=task,
                                agent=agent,
                                status="active",
                                stop_event=asyncio.Event() # 重置停止信号
                            )
                            # 重新设置 session 变量指向现有会话
                            session = await session_manager.get_session(request.session_id) 
                            print(f"[API] 复用现有会话: {request.session_id}")
                        else:
                             # 会话ID无效，作为新会话处理
                             print(f"[API] 警告: 请求的会话ID {request.session_id} 不存在，将创建新会话")
                             session = session_manager.create_session(
                                session_id=task_id,
                                task=task,
                                llm_client=llm_client,
                                agent=agent
                            )
                    else:
                        # 创建新会话
                        session = session_manager.create_session(
                            session_id=task_id,
                            task=task,
                            llm_client=llm_client,
                            agent=agent
                        )

                    # 保存用户初始输入作为第一条消息
                    await session_manager.add_message(task_id, "user", request.description)

                    try:
                        report = await agent.diagnose(
                            task=task,
                            event_callback=callback,
                            stop_event=session.stop_event,
                            session_id=task_id,
                            session_manager=session_manager
                        )
                        # 诊断完成，将状态设为 completed（不删除会话，保持记忆）
                        session_manager.update_session(task_id, status="completed")
                        
                        # 保存助手最终结论
                        if report and report.root_cause:
                            await session_manager.add_message(
                                session_id=task_id,
                                role="assistant",
                                content=f"诊断完成。根因：{report.root_cause}",
                                metadata={"report": {
                                    "root_cause": report.root_cause,
                                    "confidence": report.confidence,
                                    "suggestions": report.fix_suggestions
                                }}
                            )
                        
                        # 获取最后生成的报告结论并保存
                        # 注意：SSE 模式下 agent.diagnose 已经返回了报告
                        # 但这里我们希望把结论也作为消息持久化
                        # agent.diagnose 内部已经生成了报告，我们可以从返回值获取
                        # 不过 diagnose_stream 里的 run_diagnosis 是个闭包
                        # 我们可以在 diagnose 里直接处理结论保存（已经在 api.py 的普通 diagnose 接口做了，这里也要做）
                        
                        print(f"[API] 会话 {task_id} 诊断完成，会话保持活跃")
                    except NeedUserInputException as e:
                        # 需要用户输入，保存会话状态
                        session_manager.update_session(
                            task_id,
                            status="waiting_user",
                            pending_question=e.question,
                            context=agent.current_context
                        )
                        print(f"[API] 会话 {task_id} 等待用户输入: {e.question}")
                        
                        # 保存问题到历史记录
                        await session_manager.add_message(
                            session_id=task_id,
                            role="assistant",
                            content=e.question,
                            metadata={"type": "question"}
                        )
                        # 不要发送 done，让前端知道需要用户输入

                    # 发送完成信号
                    await event_queue.put({"type": "done"})

                except NeedUserInputException:
                    # NeedUserInputException 已经在上面处理，发送完成信号
                    await event_queue.put({"type": "done"})
                except ValueError as e:
                    # 输入验证错误，发送友好提示
                    await event_queue.put({
                        "type": "error",
                        "message": f"输入验证失败: {str(e)}。请检查输入格式后重新提交。"
                    })
                    await event_queue.put({"type": "done"})
                except Exception as e:
                    # 发送错误事件
                    await event_queue.put({
                        "type": "error",
                        "message": str(e)
                    })
                    await event_queue.put({"type": "done"})

            # 启动后台任务
            diagnosis_task = asyncio.create_task(run_diagnosis())

            # 从队列中读取事件并发送
            heartbeat_counter = 0
            while True:
                try:
                    # 使用极短的超时，以便快速响应队列中的事件
                    # 同时也让循环能够频繁检查任务状态
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                    if event["type"] == "done":
                        break
                    # 立即发送事件
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    # 定期发送心跳保持连接
                    heartbeat_counter += 1
                    if heartbeat_counter % 20 == 0:  # 每约 2 秒发送一次心跳
                        yield f": heartbeat {heartbeat_counter}\n\n"
                    
                    # 检查后台任务是否已经结束（如果因为某种原因没有发送 done）
                    if diagnosis_task.done():
                        break
                    continue

            # 等待诊断任务完成
            await diagnosis_task

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/v1/chat/answer")
async def chat_answer(request: ChatAnswerRequest):
    """
    用户回答问题后继续诊断（流式）

    ### 请求示例：
    ```json
    {
        "session_id": "task_20260123105030_a1b2c3d4",
        "answer": "目标服务器上有防火墙"
    }
    ```

    ### 响应格式：
    Server-Sent Events (SSE) 流式推送
    """
    async def event_generator():
        try:
            # 获取会话（使用 await 因为现在是异步的）
            session = await session_manager.get_session(request.session_id)
            if not session:
                yield f"data: {json.dumps({'type': 'error', 'message': '会话不存在或已过期'}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                return

            # 检查会话状态
            if session.status == "waiting_user":
                # 正常情况：LLM 在等待用户回答
                pass
            elif session.status == "completed":
                # 诊断已完成，用户想要继续对话
                # 将此视为新的诊断请求
                yield f"data: {json.dumps({'type': 'info', 'message': '上一次诊断已完成，开始新的诊断...'}, ensure_ascii=False)}\n\n"
                # 重置会话状态
                session_manager.update_session(request.session_id, status="active")
            elif session.status == "active":
                # 诊断正在进行中，用户不应该通过此接口继续
                yield f"data: {json.dumps({'type': 'error', 'message': '诊断正在进行中，请等待完成或询问问题'}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                return
            else:
                # 其他状态（如 error）
                yield f"data: {json.dumps({'type': 'error', 'message': f'会话状态错误: {session.status}'}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                return

            # 创建事件队列
            event_queue = asyncio.Queue()

            # 发送初始注释
            yield ": SSE stream started\n\n"

            # 定义回调函数
            async def callback(event):
                await event_queue.put(event)
                await asyncio.sleep(0)

            # 继续诊断任务（后台）
            async def continue_diagnosis():
                try:
                    # 恢复 Agent
                    agent = session.agent
                    task = session.task

                    # 更新会话状态
                    session_manager.update_session(request.session_id, status="active")
                    await session_manager.add_message(request.session_id, "user", request.answer)

                    try:
                        report = await agent.continue_diagnose(
                            task=task,
                            context=session.context,
                            user_answer=request.answer,
                            event_callback=callback,
                            stop_event=session.stop_event,
                            session_id=request.session_id,
                            session_manager=session_manager
                        )
                        # 诊断完成，将状态设为 completed（不删除会话，保持记忆）
                        session_manager.update_session(request.session_id, status="completed")

                        # 保存助手最终结论
                        if report and report.root_cause:
                            await session_manager.add_message(
                                session_id=request.session_id,
                                role="assistant",
                                content=f"诊断完成。根因：{report.root_cause}",
                                metadata={"report": {
                                    "root_cause": report.root_cause,
                                    "confidence": report.confidence,
                                    "suggestions": report.fix_suggestions
                                }}
                            )
                        print(f"[API] 会话 {request.session_id} 继续诊断完成，会话保持活跃")
                    except NeedUserInputException as e:
                        # 再次需要用户输入
                        session_manager.update_session(
                            request.session_id,
                            status="waiting_user",
                            pending_question=e.question,
                            context=agent.current_context
                        )
                        print(f"[API] 会话 {request.session_id} 再次等待用户输入: {e.question}")
                        
                        # 保存问题到历史记录
                        await session_manager.add_message(
                            session_id=request.session_id,
                            role="assistant",
                            content=e.question,
                            metadata={"type": "question"}
                        )

                    # 发送完成信号
                    await event_queue.put({"type": "done"})

                except NeedUserInputException:
                    # NeedUserInputException 已经在上面处理
                    await event_queue.put({"type": "done"})
                except Exception as e:
                    await event_queue.put({
                        "type": "error",
                        "message": str(e)
                    })
                    await event_queue.put({"type": "done"})

            # 启动后台任务
            diagnosis_task = asyncio.create_task(continue_diagnosis())

            # 从队列中读取事件并发送
            heartbeat_counter = 0
            while True:
                try:
                    # 使用较短的超时
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                    if event["type"] == "done":
                        break
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    heartbeat_counter += 1
                    if heartbeat_counter % 20 == 0:
                        yield f": heartbeat {heartbeat_counter}\n\n"
                    
                    if diagnosis_task.done():
                        break
                    continue

            # 等待诊断任务完成
            await diagnosis_task

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/v1/chat/general-legacy")
async def general_chat(request: GeneralChatRequest):
    """
    通用聊天接口（非诊断模式）
    
    支持创建新会话或继续现有会话

    ### 请求示例（新会话）：
    ```json
    {
        "message": "你好，请问你能做什么？"
    }
    ```
    
    ### 请求示例（继续会话）：
    ```json
    {
        "message": "请介绍一下你的功能",
        "session_id": "task_20260127134500_abc123"
    }
    ```

    ### 响应示例：
    ```json
    {
        "response": "你好！我是网络故障诊断助手...",
        "session_id": "task_20260127134500_abc123"
    }
    ```
    """
    try:
        # 检查是否继续现有会话
        if request.session_id:
            # 继续现有会话
            session = await session_manager.get_session(request.session_id)
            if not session:
                raise HTTPException(
                    status_code=404,
                    detail=f"会话不存在: {request.session_id}"
                )
            
            session_id = request.session_id
            llm_client = session.llm_client
            
            # 保存用户消息
            await session_manager.add_message(session_id, "user", request.message)
            
            # 定义系统提示词
            system_prompt = """你是一个专业的网络故障诊断助手。你的主要职责是帮助用户诊断和解决网络问题。

当用户向你打招呼或询问一般性问题时，你应该：
1. 友好地回应用户
2. 简要介绍你的能力（网络故障诊断、根因分析等）
3. 引导用户描述他们遇到的网络故障（如果适用）
4. 回答用户关于网络诊断的问题

你可以回答的问题类型包括：
- 网络诊断相关的概念和方法
- 常见网络故障的原因
- 如何使用本系统进行故障诊断
- 网络工具的使用方法（ping, traceroute, telnet等）

请用简洁、专业但友好的语气回答。如果用户的问题与网络诊断无关，礼貌地说明你的专长领域。"""
            
            # 获取完整对话历史并调用 LLM
            messages = session.messages
            
            response = llm_client.chat(
                messages=messages,
                system_prompt=system_prompt
            )
            
            # 保存助手响应
            await session_manager.add_message(session_id, "assistant", response)
            
            # 更新会话时间
            session_manager.update_session(session_id, status="completed")
            
        else:
            # 创建新会话
            llm_client = LLMClient()
            session_id = generate_task_id()

            # 定义系统提示词
            system_prompt = """你是一个专业的网络故障诊断助手。你的主要职责是帮助用户诊断和解决网络问题。

当用户向你打招呼或询问一般性问题时，你应该：
1. 友好地回应用户
2. 简要介绍你的能力（网络故障诊断、根因分析等）
3. 引导用户描述他们遇到的网络故障（如果适用）
4. 回答用户关于网络诊断的问题

你可以回答的问题类型包括：
- 网络诊断相关的概念和方法
- 常见网络故障的原因
- 如何使用本系统进行故障诊断
- 网络工具的使用方法（ping, traceroute, telnet等）

请用简洁、专业但友好的语气回答。如果用户的问题与网络诊断无关，礼貌地说明你的专长领域。"""

            # 调用 LLM
            response = llm_client.invoke(
                prompt=request.message,
                system_prompt=system_prompt
            )

            # 创建一个简单的任务对象用于会话管理
            from .models.task import DiagnosticTask, FaultType, Protocol
            task = DiagnosticTask(
                task_id=session_id,
                user_input=request.message,
                source="general_chat",
                target="general_chat",
                protocol=Protocol.ICMP,
                fault_type=FaultType.CONNECTIVITY,
                port=None
            )

            # 创建会话
            agent = LLMAgent(llm_client=llm_client, verbose=False)
            session = session_manager.create_session(
                session_id=session_id,
                task=task,
                llm_client=llm_client,
                agent=agent
            )

            # 保存用户消息
            await session_manager.add_message(session_id, "user", request.message)

            # 保存助手响应
            await session_manager.add_message(session_id, "assistant", response)

            # 更新会话状态为已完成
            session_manager.update_session(session_id, status="completed")

        return {
            "response": response,
            "session_id": session_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"聊天失败: {str(e)}"
        )


@app.post("/api/v1/chat/general")
async def general_chat_v2(request: GeneralChatRequest):
    """通用聊天接口，支持访问关系 tool calling。"""
    try:
        if request.session_id:
            session = await session_manager.get_session(request.session_id)
            if not session:
                raise HTTPException(
                    status_code=404,
                    detail=f"会话不存在: {request.session_id}"
                )
            session_id = request.session_id
            llm_client = session.llm_client or LLMClient()
            if session.llm_client is None:
                session_manager.update_session(session_id, llm_client=llm_client)
        else:
            llm_client = LLMClient()
            session_id = generate_task_id()
            session = session_manager.create_session(
                session_id=session_id,
                task=create_general_chat_task(session_id, request.message),
                llm_client=llm_client,
                agent=LLMAgent(llm_client=llm_client, verbose=False)
            )

        await session_manager.add_message(session_id, "user", request.message)
        tool_agent = GeneralChatToolAgent(
            llm_client=llm_client,
            session_manager=session_manager,
            session_id=session_id,
        )
        response = await tool_agent.run(
            session_messages=session.messages,
            system_prompt=build_general_chat_system_prompt(use_rag=False),
        )

        await session_manager.add_message(session_id, "assistant", response)
        session_manager.update_session(session_id, status="completed")
        return {"response": response, "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"聊天失败: {str(e)}")





@app.get("/api/v1/sessions")
async def list_sessions(status: Optional[str] = None):
    """
    获取所有会话列表（可选按状态过滤）

    ### 查询参数：
    - status: 可选，按状态过滤 (active, waiting_user, completed, error)

    ### 响应示例：
    ```json
    [
        {
            "session_id": "task_20260127133000_a1b2c3d4",
            "status": "completed",
            "created_at": "2026-01-27T13:30:00",
            "updated_at": "2026-01-27T13:35:00",
            "task_description": "10.0.1.10到10.0.2.20端口80不通",
            "pending_question": null
        }
    ]
    ```
    """
    try:
        # 从数据库获取会话列表
        if hasattr(session_manager, 'db') and session_manager.db:
            sessions_data = await session_manager.db.get_all_sessions(status=status)
        else:
            # 如果使用内存版本，从内存获取
            sessions_data = []
            for sid, session in session_manager.sessions.items():
                if status is None or session.status == status:
                    # 提取任务描述
                    task_desc = session.task.user_input if hasattr(session.task, 'user_input') else str(session.task)
                    
                    sessions_data.append({
                        'session_id': sid,
                        'status': session.status,
                        'created_at': session.created_at.isoformat(),
                        'updated_at': session.updated_at.isoformat(),
                        'task_description': task_desc,
                        'pending_question': session.pending_question
                    })
            # 按更新时间倒序排序
            sessions_data.sort(key=lambda x: x['updated_at'], reverse=True)

        # 格式化响应
        result = []
        for session_data in sessions_data:
            # 如果是从数据库获取的，需要解析 task_data
            if 'task_data' in session_data:
                import json
                try:
                    task_data = json.loads(session_data['task_data'])
                    task_desc = task_data.get('user_input', 'Unknown task')
                except:
                    task_desc = 'Unknown task'
            else:
                task_desc = session_data.get('task_description', 'Unknown task')

            result.append({
                'session_id': session_data['session_id'],
                'status': session_data['status'],
                'created_at': session_data['created_at'],
                'updated_at': session_data['updated_at'],
                'task_description': task_desc,
                'pending_question': session_data.get('pending_question')
            })

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取会话列表失败: {str(e)}"
        )



@app.post("/api/v1/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    """
    停止会话执行
    """
    await session_manager.stop_session(session_id)
    return {"status": "success", "message": "已发送停止信号"}


@app.get("/api/v1/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """
    获取指定会话的所有消息

    ### 路径参数：
    - session_id: 会话ID

    ### 响应示例：
    ```json
    [
        {
            "role": "user",
            "content": "10.0.1.10到10.0.2.20端口80不通",
            "timestamp": "2026-01-27T13:30:00"
        },
        {
            "role": "assistant",
            "content": "我来帮你诊断这个问题...",
            "timestamp": "2026-01-27T13:30:05"
        }
    ]
    ```
    """
    try:
        # 获取会话
        session = await session_manager.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"会话不存在: {session_id}"
            )

        # 返回消息列表
        messages = []
        for msg in session.messages:
            messages.append({
                'role': msg['role'],
                'content': msg['content'],
                'timestamp': msg['timestamp'],
                'metadata': msg.get('metadata', {})
            })

        return messages

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取消息失败: {str(e)}"
        )


@app.patch("/api/v1/sessions/{session_id}/rename")
async def rename_session(session_id: str, request: RenameSessionRequest):
    """
    重命名会话（更新任务描述）

    ### 路径参数：
    - session_id: 会话ID

    ### 请求体：
    ```json
    {
        "new_name": "新的会话名称"
    }
    ```

    ### 响应示例：
    ```json
    {
        "status": "success",
        "session_id": "task_20260127133000_a1b2c3d4",
        "new_name": "新的会话名称"
    }
    ```
    """
    try:
        # 获取会话
        session = await session_manager.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"会话不存在: {session_id}"
            )

        # 更新任务描述
        if hasattr(session.task, 'user_input'):
            session.task.user_input = request.new_name
        
        # 如果使用数据库，需要更新数据库中的 task_data
        if hasattr(session_manager, 'db') and session_manager.db:
            from .db import serialize_task
            task_data = serialize_task(session.task)
            await session_manager.db.update_session(
                session_id,
                {'task_data': task_data}
            )
        
        # 更新内存中的会话时间戳
        session_manager.update_session(session_id)
        
        return {
            "status": "success",
            "session_id": session_id,
            "new_name": request.new_name
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"重命名会话失败: {str(e)}"
        )


@app.delete("/api/v1/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    删除会话

    ### 路径参数：
    - session_id: 会话ID

    ### 响应示例：
    ```json
    {
        "status": "success",
        "message": "会话已删除"
    }
    ```
    """
    try:
        # 检查会话是否存在
        session = await session_manager.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"会话不存在: {session_id}"
            )

        # 删除会话（包括数据库和内存）
        session_manager.delete_session(session_id)
        
        return {
            "status": "success",
            "message": "会话已删除"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"删除会话失败: {str(e)}"
        )


@app.get("/api/v1/task/{task_id}")
async def get_task_status(task_id: str):
    """
    查询任务状态（预留接口，当前版本暂不支持异步任务）
    """
    raise HTTPException(
        status_code=501,
        detail="异步任务查询功能暂未实现，当前版本为同步诊断"
    )


# ===== 知识库管理 API =====

from fastapi import UploadFile, File

# 知识库服务初始化标志
_rag_initialized = False
_document_processor = None
_vector_store = None
_rag_chain = None


def _init_rag_services():
    """延迟初始化RAG服务（避免启动时加载模型）"""
    global _rag_initialized, _document_processor, _vector_store, _rag_chain
    if not _rag_initialized:
        from .rag import DocumentProcessor, get_vector_store, RAGChain
        _document_processor = DocumentProcessor()
        _vector_store = get_vector_store()
        _rag_chain = RAGChain(vector_store=_vector_store)
        _rag_initialized = True
        print("[API] RAG服务初始化完成")
    return _document_processor, _vector_store, _rag_chain


@app.post("/api/v1/knowledge/upload")
async def upload_knowledge(file: UploadFile = File(...)):
    """
    上传知识库文档

    ### 请求：
    - 上传TXT格式文件（multipart/form-data）

    ### 响应示例：
    ```json
    {
        "status": "success",
        "doc_id": "doc_20260203_abc123",
        "filename": "network_guide.txt",
        "chunks": 15,
        "message": "文档上传成功，已分割为15个知识块"
    }
    ```
    """
    try:
        # 验证文件类型
        if not file.filename.endswith('.txt'):
            raise HTTPException(
                status_code=400,
                detail="仅支持TXT格式文件"
            )
        
        # 初始化RAG服务
        document_processor, vector_store, _ = _init_rag_services()
        
        # 读取文件内容
        content = await file.read()
        
        if not content:
            raise HTTPException(
                status_code=400,
                detail="文件内容为空"
            )
        
        # 处理文档
        doc_id, chunks, metadatas = document_processor.process_text_file(
            file_content=content,
            filename=file.filename
        )
        
        # 添加到向量存储
        vector_store.add_documents(
            texts=chunks,
            metadatas=metadatas,
            doc_id=doc_id
        )
        
        return {
            "status": "success",
            "doc_id": doc_id,
            "filename": file.filename,
            "chunks": len(chunks),
            "message": f"文档上传成功，已分割为{len(chunks)}个知识块"
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"上传文档失败: {str(e)}"
        )


@app.get("/api/v1/knowledge/list")
async def list_knowledge():
    """
    获取知识库文档列表

    ### 响应示例：
    ```json
    {
        "status": "success",
        "documents": [
            {
                "doc_id": "doc_20260203_abc123",
                "filename": "network_guide.txt",
                "chunk_count": 15,
                "upload_time": "2026-02-03T20:30:00"
            }
        ],
        "total": 1
    }
    ```
    """
    try:
        # 初始化RAG服务
        _, vector_store, _ = _init_rag_services()
        
        # 获取文档列表
        documents = vector_store.list_documents()
        
        return {
            "status": "success",
            "documents": documents,
            "total": len(documents)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取文档列表失败: {str(e)}"
        )


@app.delete("/api/v1/knowledge/{doc_id}")
async def delete_knowledge(doc_id: str):
    """
    删除知识库文档

    ### 路径参数：
    - doc_id: 文档ID

    ### 响应示例：
    ```json
    {
        "status": "success",
        "doc_id": "doc_20260203_abc123",
        "deleted_chunks": 15,
        "message": "文档已删除"
    }
    ```
    """
    try:
        # 初始化RAG服务
        document_processor, vector_store, _ = _init_rag_services()
        
        # 删除向量存储中的文档
        deleted_count = vector_store.delete_by_doc_id(doc_id)
        
        if deleted_count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"文档不存在: {doc_id}"
            )
        
        # 删除原始文件
        document_processor.delete_file(doc_id)
        
        return {
            "status": "success",
            "doc_id": doc_id,
            "deleted_chunks": deleted_count,
            "message": "文档已删除"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"删除文档失败: {str(e)}"
        )


@app.get("/api/v1/knowledge/stats")
async def knowledge_stats():
    """
    获取知识库统计信息

    ### 响应示例：
    ```json
    {
        "status": "success",
        "stats": {
            "total_documents": 5,
            "total_chunks": 120,
            "has_knowledge": true
        }
    }
    ```
    """
    try:
        # 初始化RAG服务
        _, vector_store, rag_chain = _init_rag_services()
        
        documents = vector_store.list_documents()
        stats = vector_store.get_stats()
        
        return {
            "status": "success",
            "stats": {
                "total_documents": len(documents),
                "total_chunks": stats.get("total_chunks", 0),
                "has_knowledge": rag_chain.has_knowledge()
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取统计信息失败: {str(e)}"
        )


@app.get("/api/v1/knowledge/search")
async def search_knowledge(query: str, top_k: int = 5):
    """
    搜索知识库内容

    ### 查询参数：
    - query: 搜索关键词（必填）
    - top_k: 返回结果数量（可选，默认5）

    ### 响应示例：
    ```json
    {
        "status": "success",
        "query": "证书更新",
        "results": [
            {
                "text": "证书更新服务联系人是张三...",
                "filename": "contacts.txt",
                "relevance_score": 0.82,
                "chunk_index": 0,
                "doc_id": "doc_20260303_abc123"
            }
        ],
        "total": 1
    }
    ```
    """
    try:
        if not query or not query.strip():
            raise HTTPException(
                status_code=400,
                detail="搜索关键词不能为空"
            )

        if top_k < 1 or top_k > 20:
            top_k = 5

        # 初始化RAG服务
        _, _, rag_chain = _init_rag_services()

        # 使用RAG检索链进行语义搜索
        results = rag_chain.retrieve(query.strip(), top_k=top_k)

        # 格式化搜索结果
        formatted_results = []
        for result in results:
            metadata = result.get("metadata", {})
            formatted_results.append({
                "text": result.get("text", ""),
                "filename": metadata.get("filename", "未知来源"),
                "relevance_score": round(result.get("relevance_score", 0), 4),
                "chunk_index": metadata.get("chunk_index", 0),
                "doc_id": metadata.get("doc_id", "")
            })

        return {
            "status": "success",
            "query": query.strip(),
            "results": formatted_results,
            "total": len(formatted_results)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"搜索知识库失败: {str(e)}"
        )


@app.get("/api/v1/knowledge/{doc_id}/content")
async def get_knowledge_content(doc_id: str):
    """
    获取知识库文档内容（用于在线预览）

    ### 路径参数：
    - doc_id: 文档ID

    ### 响应示例：
    ```json
    {
        "status": "success",
        "doc_id": "doc_20260203_abc123",
        "filename": "network_guide.txt",
        "content": "文档的文本内容...",
        "size": 1234
    }
    ```
    """
    try:
        # 初始化RAG服务
        document_processor, _, _ = _init_rag_services()
        
        # 获取文档内容
        result = document_processor.get_file_content(doc_id)
        
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"文档不存在: {doc_id}"
            )
        
        return {
            "status": "success",
            "doc_id": doc_id,
            "filename": result["filename"],
            "content": result["content"],
            "size": result["size"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取文档内容失败: {str(e)}"
        )


# 修改通用聊天请求模型，添加use_rag参数
class GeneralChatRequestWithRAG(BaseModel):
    """通用聊天请求（支持RAG）"""
    message: str = Field(..., description="用户的消息", min_length=1)
    session_id: Optional[str] = Field(None, description="可选的会话ID，用于继续现有会话")
    use_rag: bool = Field(default=True, description="是否使用知识库检索增强")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "如何排查端口不通的问题？",
                "session_id": None,
                "use_rag": True
            }
        }


@app.post("/api/v1/chat/general/stream-legacy")
async def general_chat_stream(request: GeneralChatRequestWithRAG):
    """
    通用聊天接口（流式，支持RAG）

    ### 请求示例：
    ```json
    {
        "message": "如何排查端口不通的问题？",
        "use_rag": true
    }
    ```

    ### 响应格式：
    Server-Sent Events (SSE) 流式推送
    """
    async def event_generator():
        try:
            session_id = request.session_id or generate_task_id()
            
            # 发送开始事件
            yield f"data: {json.dumps({'type': 'start', 'session_id': session_id}, ensure_ascii=False)}\n\n"
            
            # 初始化LLM客户端
            llm_client = LLMClient()
            
            # 准备系统提示词
            system_prompt = """你是一个专业的网络故障诊断助手。你的主要职责是帮助用户诊断和解决网络问题。

当用户向你打招呼或询问一般性问题时，你应该：
1. 友好地回应用户
2. 简要介绍你的能力（网络故障诊断、根因分析等）
3. 引导用户描述他们遇到的网络故障（如果适用）
4. 回答用户关于网络诊断的问题

你可以回答的问题类型包括：
- 网络诊断相关的概念和方法
- 常见网络故障的原因
- 如何使用本系统进行故障诊断
- 网络工具的使用方法（ping, traceroute, telnet等）

请用简洁、专业但友好的语气回答。如果用户的问题与网络诊断无关，礼貌地说明你的专长领域。"""
            
            retrieved_docs = []
            
            # 如果启用RAG，检索相关知识
            if request.use_rag:
                try:
                    _, _, rag_chain = _init_rag_services()
                    if rag_chain.has_knowledge():
                        # 发送检索开始事件
                        yield f"data: {json.dumps({'type': 'rag_start', 'message': '正在检索知识库...'}, ensure_ascii=False)}\n\n"
                        
                        # 构建增强Prompt
                        _, enhanced_system_prompt, retrieved_docs = rag_chain.build_enhanced_prompt(request.message)
                        system_prompt = enhanced_system_prompt
                        
                        # 发送检索结果事件
                        if retrieved_docs:
                            yield f"data: {json.dumps({'type': 'rag_result', 'count': len(retrieved_docs), 'sources': [d.get('metadata', {}).get('filename', '未知') for d in retrieved_docs]}, ensure_ascii=False)}\n\n"
                        else:
                            yield f"data: {json.dumps({'type': 'rag_result', 'count': 0, 'message': '未找到相关知识'}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    print(f"[API] RAG检索失败: {e}")
                    yield f"data: {json.dumps({'type': 'rag_error', 'message': f'知识库检索失败: {str(e)}'}, ensure_ascii=False)}\n\n"
            
            # 获取或创建会话
            session = await session_manager.get_session(session_id) if request.session_id else None
            
            if session:
                # 继续现有会话
                await session_manager.add_message(session_id, "user", request.message)
                messages = session.messages
                response = llm_client.chat(messages=messages, system_prompt=system_prompt)
            else:
                # 新会话
                response = llm_client.invoke(prompt=request.message, system_prompt=system_prompt)
                
                # 创建会话
                from .models.task import DiagnosticTask, FaultType, Protocol
                task = DiagnosticTask(
                    task_id=session_id,
                    user_input=request.message,
                    source="general_chat",
                    target="general_chat",
                    protocol=Protocol.ICMP,
                    fault_type=FaultType.CONNECTIVITY,
                    port=None
                )
                agent = LLMAgent(llm_client=llm_client, verbose=False)
                session_manager.create_session(
                    session_id=session_id,
                    task=task,
                    llm_client=llm_client,
                    agent=agent
                )
                await session_manager.add_message(session_id, "user", request.message)
            
            # 流式发送响应（模拟打字效果）
            chunk_size = 10  # 每次发送的字符数
            for i in range(0, len(response), chunk_size):
                chunk = response[i:i+chunk_size]
                yield f"data: {json.dumps({'type': 'content', 'text': chunk}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.02)  # 模拟打字延迟
            
            # 保存助手响应
            await session_manager.add_message(session_id, "assistant", response)
            session_manager.update_session(session_id, status="completed")
            
            # 发送完成事件
            yield f"data: {json.dumps({'type': 'complete', 'session_id': session_id, 'rag_used': request.use_rag and len(retrieved_docs) > 0}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/v1/chat/general/stream")
async def general_chat_stream_v2(request: GeneralChatRequestWithRAG):
    """流式通用聊天接口，支持 RAG 与访问关系 tool calling。"""

    async def event_generator():
        event_queue: asyncio.Queue = asyncio.Queue()

        try:
            if request.session_id:
                session = await session_manager.get_session(request.session_id)
                if not session:
                    raise HTTPException(
                        status_code=404,
                        detail=f"会话不存在: {request.session_id}"
                    )
                session_id = request.session_id
                llm_client = session.llm_client or LLMClient()
                if session.llm_client is None:
                    session_manager.update_session(session_id, llm_client=llm_client)
            else:
                llm_client = LLMClient()
                session_id = generate_task_id()
                session = session_manager.create_session(
                    session_id=session_id,
                    task=create_general_chat_task(session_id, request.message),
                    llm_client=llm_client,
                    agent=LLMAgent(llm_client=llm_client, verbose=False)
                )

            yield f"data: {json.dumps({'type': 'start', 'session_id': session_id}, ensure_ascii=False)}\n\n"

            system_prompt = build_general_chat_system_prompt(use_rag=request.use_rag)
            retrieved_docs = []

            # Task 3.2: Detect if we should skip RAG for access relation data queries
            skip_rag = False
            if request.use_rag and is_access_relation_data_query(request.message):
                skip_rag = True
                yield f"data: {json.dumps({'type': 'rag_skipped', 'reason': '检测到访问关系数据查询,跳过知识库检索'}, ensure_ascii=False)}\n\n"

            # Task 3.3: Only execute RAG if not skipped
            if request.use_rag and not skip_rag:
                try:
                    _, _, rag_chain = _init_rag_services()
                    if rag_chain.has_knowledge():
                        yield f"data: {json.dumps({'type': 'rag_start', 'message': '正在检索知识库...'}, ensure_ascii=False)}\n\n"
                        _, system_prompt, retrieved_docs = rag_chain.build_enhanced_prompt(
                            request.message,
                            system_prompt_template=GENERAL_CHAT_SYSTEM_PROMPT_TEMPLATE
                        )
                        if retrieved_docs:
                            yield f"data: {json.dumps({'type': 'rag_result', 'count': len(retrieved_docs), 'sources': [d.get('metadata', {}).get('filename', '未知') for d in retrieved_docs]}, ensure_ascii=False)}\n\n"
                        else:
                            yield f"data: {json.dumps({'type': 'rag_result', 'count': 0, 'message': '知识库中未找到相关内容'}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    print(f"[API] RAG检索失败: {e}")
                    yield f"data: {json.dumps({'type': 'rag_error', 'message': f'知识库检索失败: {str(e)}'}, ensure_ascii=False)}\n\n"

            await session_manager.add_message(session_id, "user", request.message)

            async def callback(event: Dict):
                await event_queue.put(event)
                await asyncio.sleep(0)

            tool_agent = GeneralChatToolAgent(
                llm_client=llm_client,
                session_manager=session_manager,
                session_id=session_id,
                event_callback=callback,
            )
            response_task = asyncio.create_task(
                tool_agent.run(
                    session_messages=session.messages,
                    system_prompt=system_prompt,
                )
            )

            while True:
                if response_task.done() and event_queue.empty():
                    break
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    continue

            response = await response_task
            await session_manager.add_message(session_id, "assistant", response)
            session_manager.update_session(session_id, status="completed")

            chunk_size = 10
            for i in range(0, len(response), chunk_size):
                chunk = response[i:i + chunk_size]
                yield f"data: {json.dumps({'type': 'content', 'text': chunk}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.02)

            yield f"data: {json.dumps({'type': 'complete', 'session_id': session_id, 'rag_used': request.use_rag and len(retrieved_docs) > 0}, ensure_ascii=False)}\n\n"
        except HTTPException as e:
            yield f"data: {json.dumps({'type': 'error', 'message': e.detail}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


class AccessAssetCreate(BaseModel):
    """新增网络访问关系资产请求"""
    src_system: str = Field(..., description="源物理子系统（代码）", min_length=1)
    src_system_name: str = Field(default="", description="源物理子系统中文名")
    src_deploy_unit: str = Field(default="", description="源部署单元属性")
    src_ip: str = Field(default="", description="源IP地址（多个用换行分隔）")
    dst_system: str = Field(..., description="目的物理子系统（代码）", min_length=1)
    dst_deploy_unit: str = Field(default="", description="目的部署单元属性")
    dst_ip: str = Field(default="", description="目的IP地址")
    protocol: str = Field(default="TCP", description="协议（TCP/UDP等）")
    port: str = Field(default="", description="目的端口（多个用换行分隔）")

    class Config:
        json_schema_extra = {
            "example": {
                "src_system": "N-AQM",
                "src_system_name": "金融资产质量管理",
                "src_deploy_unit": "AQMJS_AP",
                "src_ip": "10.37.1.116",
                "dst_system": "P-ZH-DMP-CONF",
                "dst_deploy_unit": "ADDNG_WB",
                "dst_ip": "10.87.28.127",
                "protocol": "TCP",
                "port": "8080"
            }
        }


@app.get("/api/v1/assets/access-relations")
async def list_access_assets(
    src_system: Optional[str] = None,
    dst_system: Optional[str] = None,
    keyword: Optional[str] = None,
    protocol: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
):
    """查询网络访问关系资产列表（支持多条件过滤+分页）"""
    try:
        if not hasattr(session_manager, "db") or not session_manager.db:
            raise HTTPException(status_code=500, detail="数据库不可用")
        result = await session_manager.db.query_access_assets(
            src_system=src_system,
            dst_system=dst_system,
            keyword=keyword,
            protocol=protocol,
            page=max(1, page),
            page_size=min(100, max(1, page_size))
        )
        return {"status": "success", **result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.post("/api/v1/assets/access-relations", status_code=201)
async def create_access_asset(request: AccessAssetCreate):
    """新增一条网络访问关系资产记录"""
    try:
        if not hasattr(session_manager, "db") or not session_manager.db:
            raise HTTPException(status_code=500, detail="数据库不可用")
        asset_id = await session_manager.db.create_access_asset(request.dict())
        if asset_id is None:
            raise HTTPException(status_code=500, detail="创建记录失败")
        return {"status": "success", "id": asset_id, "message": "访问关系记录已创建"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"新增失败: {str(e)}")


@app.delete("/api/v1/assets/access-relations/{asset_id}")
async def delete_access_asset_route(asset_id: int):
    """删除一条网络访问关系资产记录"""
    try:
        if not hasattr(session_manager, "db") or not session_manager.db:
            raise HTTPException(status_code=500, detail="数据库不可用")
        success = await session_manager.db.delete_access_asset(asset_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"记录不存在: {asset_id}")
        return {"status": "success", "message": "记录已删除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
