"""
LLM Agent - LLM驱动的动态诊断Agent

使用LangChain框架，动态决策并调用网络工具执行网络诊断
"""
import os
import json
import asyncio
from typing import Dict, List, Optional, Any, Callable
from pydantic import BaseModel, Field
from langchain_core.tools import Tool, StructuredTool

from ..integrations.llm_client import LLMClient
from ..integrations.network_tools import NetworkTools
from ..models.task import DiagnosticTask
from ..models.report import DiagnosticReport
from ..models.results import StepResult, CommandResult
from ..utils.output_formatter import ToolOutputFormatter


# 自定义异常：需要用户输入
class NeedUserInputException(Exception):
    """当 LLM 需要询问用户时抛出"""
    def __init__(self, question: str, context: List[Dict]):
        self.question = question
        self.context = context
        super().__init__(question)


# 定义工具参数的Pydantic模型
class ExecuteCommandInput(BaseModel):
    """execute_command工具的输入参数"""
    host: str = Field(description="目标主机IP或主机名，例如：10.0.1.10 或 web-server-01")
    command: str = Field(description="要执行的命令，例如：ping -c 4 10.0.2.20")
    timeout: int = Field(default=30, description="超时时间（秒），默认30秒")


class QueryCMDBInput(BaseModel):
    """query_cmdb工具的输入参数"""
    hosts: List[str] = Field(description="主机列表（IP或主机名），例如：['10.0.1.10', 'web-01']")


class AskUserInput(BaseModel):
    """ask_user工具的输入参数"""
    question: str = Field(description="向用户提出的问题，例如：'请问目标服务器上是否有防火墙？'")



class LLMAgent:
    """
    LLM驱动的诊断Agent

    使用LangChain动态决策并调用网络工具执行网络诊断
    """

    SYSTEM_PROMPT_TEMPLATE = """你是一个网络故障诊断专家Agent。

你的任务是诊断网络连接问题。你可以使用以下策略：

1. **从源主机测试连通性** - 使用telnet/ping等工具从源主机测试到目标
2. **分析错误类型** - 区分timeout（网络不通）和refused（端口未监听）
3. **检查目标主机** - 如果是refused，检查目标主机的端口监听状态
4. **检查防火墙** - 检查源主机或目标主机的防火墙规则
5. **检查路由** - 使用traceroute检查路由路径
6. **询问用户** - 当需要用户提供额外信息时（如防火墙配置、业务信息等），使用ask_user工具

诊断原则：
- 逐步缩小问题范围
- 根据上一步结果决定下一步
- 如果信息不足，可以向用户提问获取更多上下文
- 找到根因后立即结束
- 最多执行{max_steps}步

输出格式：
- 如果需要执行命令，调用相应的工具
- 如果需要用户提供信息，调用ask_user工具
- 如果已找到根因，在reasoning中说明结论"""

    @property
    def SYSTEM_PROMPT(self) -> str:
        """动态生成系统提示词"""
        return self.SYSTEM_PROMPT_TEMPLATE.format(max_steps=self.max_steps)

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        verbose: bool = False,
        max_steps: Optional[int] = None
    ):
        """
        初始化LLM Agent

        Args:
            llm_client: LLM客户端，如果为None则创建新实例
            verbose: 是否启用详细输出模式
            max_steps: 最大执行步数，如果为None则从环境变量读取（默认10）
        """
        self.llm_client = llm_client or LLMClient()

        # 从环境变量或参数获取 max_steps（优先使用参数）
        if max_steps is not None:
            self.max_steps = max_steps
        else:
            self.max_steps = int(os.getenv("LLM_AGENT_MAX_STEPS", "10"))

        self.verbose = verbose
        self.output_formatter = ToolOutputFormatter(verbose=verbose)
        self.current_context = []  # 用于存储当前诊断上下文，供 ask_user 使用

        # 创建网络工具实例
        self.network_tools = NetworkTools(use_router=True)

        # 尝试加载网络配置（支持多网络环境）
        from ..integrations.config_loader import load_network_config
        try:
            self.network_router = load_network_config()
            print(f"[网络路由] 已加载 {len(self.network_router.networks)} 个网络配置")
        except FileNotFoundError:
            # 配置文件不存在，使用默认单一网络模式
            self.network_router = None
        except Exception as e:
            print(f"[警告] 无法加载网络配置: {e}")
            self.network_router = None

        # 创建LangChain Tools
        self.tools = self._create_tools()

    def _create_tools(self) -> List[StructuredTool]:
        """创建LangChain工具列表"""
        # 创建 execute_command 工具
        async def execute_command_func(host: str, command: str, timeout: int = 30) -> dict:
            return await self.network_tools.execute_command(host, command, timeout)

        execute_command_tool = StructuredTool.from_function(
            coroutine=execute_command_func,
            name="execute_command",
            description="在指定主机上执行命令，用于网络诊断。可以执行ping、telnet、ss、iptables等命令。",
            args_schema=ExecuteCommandInput
        )

        # 创建 query_cmdb 工具
        async def query_cmdb_func(hosts: List[str]) -> dict:
            return await self.network_tools.query_cmdb(hosts)

        query_cmdb_tool = StructuredTool.from_function(
            coroutine=query_cmdb_func,
            name="query_cmdb",
            description="查询CMDB获取主机信息，包括IP地址、主机名、所属业务等。",
            args_schema=QueryCMDBInput
        )

        # 创建 ask_user 工具
        async def ask_user_func(question: str) -> dict:
            # 抛出异常，暂停诊断流程，等待用户回答
            raise NeedUserInputException(question=question, context=self.current_context)

        ask_user_tool = StructuredTool.from_function(
            coroutine=ask_user_func,
            name="ask_user",
            description="向用户提问以获取更多信息。当需要了解防火墙配置、业务信息、历史变更等无法通过命令获取的信息时使用此工具。",
            args_schema=AskUserInput
        )

        return [execute_command_tool, query_cmdb_tool, ask_user_tool]

    async def diagnose(
        self,
        task: DiagnosticTask,
        event_callback: Optional[Callable] = None,
        stop_event: Optional[asyncio.Event] = None,
        session_id: Optional[str] = None,
        session_manager: Optional[Any] = None
    ) -> DiagnosticReport:
        """
        使用LLM动态决策并执行诊断

        Args:
            task: 诊断任务
            event_callback: 可选的事件回调函数，用于实时推送诊断进度
            stop_event: 停止信号
            session_id: 会话ID (用于历史记录)
            session_manager: 会话管理器 (用于历史记录)

        Returns:
            DiagnosticReport: 诊断报告

        Raises:
            NeedUserInputException: 当需要用户输入时抛出
        """
        # 初始化上下文
        context = self._build_initial_context(task)
        self.current_context = context  # 更新当前上下文，供 ask_user 使用
        step_count = 0

        print(f"\n[LLM Agent] 开始诊断任务: {task.task_id}")
        print(f"  源主机: {task.source}")
        print(f"  目标主机: {task.target}")
        print(f"  协议: {task.protocol.value}")
        print(f"  端口: {task.port}")
        print(f"  故障类型: {task.fault_type.value}\n")

        # 发送诊断开始事件
        if event_callback:
            await event_callback({
                "type": "start",
                "data": {
                    "task_id": task.task_id,
                    "source": task.source,
                    "target": task.target,
                    "protocol": task.protocol.value,
                    "port": task.port,
                    "fault_type": task.fault_type.value,
                    "user_input": task.user_input
                }
            })

        # 诊断循环
        while step_count < self.max_steps:
            # 检查停止信号
            if stop_event and stop_event.is_set():
                print(f"[LLM Agent] 收到停止信号，终止诊断\n")
                if event_callback:
                    await event_callback({
                        "type": "error",
                        "message": "诊断已被用户中止"
                    })
                # 生成部分报告
                return self._generate_report(task, context, None)

            step_count += 1
            print(f"[LLM Agent] Step {step_count}/{self.max_steps}")

            # LLM决策下一步
            decision = await self._llm_decide_next_step(context, task)

            # 检查是否结束
            if decision.get("conclude", False):
                print(f"[LLM Agent] 诊断完成，找到根因\n")
                # 发送完成事件
                if event_callback:
                    report = self._generate_report(task, context, decision)
                    await event_callback({
                        "type": "complete",
                        "report": {
                            "root_cause": report.root_cause,
                            "confidence": report.confidence * 100,
                            "suggestions": report.fix_suggestions,
                            "total_time": report.total_time
                        }
                    })
                    return report
                return self._generate_report(task, context, decision)

            # 执行工具调用
            if decision.get("tool_calls"):
                for tool_call in decision["tool_calls"]:
                    # 每个子步骤前检查一次停止信号
                    if stop_event and stop_event.is_set():
                        # 中断后返回部分结果
                        return self._generate_report(task, context, None)

                    # 发送工具调用开始事件
                    if event_callback:
                        await event_callback({
                            "type": "tool_start",
                            "step": step_count,
                            "tool": tool_call["name"],
                            "arguments": tool_call["arguments"]
                        })

                    try:
                        result = await self._execute_tool(tool_call, task)

                        # 执行后再次检查停止信号
                        if stop_event and stop_event.is_set():
                            return self._generate_report(task, context, None)

                        # 发送工具调用结果事件
                        if event_callback:
                            await event_callback({
                                "type": "tool_result",
                                "step": step_count,
                                "tool": tool_call["name"],
                                "result": result
                            })

                        context.append({
                            "step": step_count,
                            "tool": tool_call["name"],
                            "arguments": tool_call["arguments"],
                            "result": result
                        })
                        self.current_context = context  # 更新当前上下文

                        # 添加到会话历史记录
                        print(f"[LLM Agent DEBUG] Tool={tool_call['name']}, session_id={session_id}, has_session_manager={session_manager is not None}")
                        if session_id and session_manager:
                            print(f"[LLM Agent DEBUG] Saving tool call to session history...")
                            await session_manager.add_message(
                                session_id=session_id,
                                role="assistant",
                                content=f"执行工具: {tool_call['name']}",
                                metadata={
                                    "tool_call": {
                                        "name": tool_call["name"],
                                        "arguments": tool_call["arguments"],
                                        "result": result
                                    }
                                }
                            )
                            print(f"[LLM Agent DEBUG] Tool call saved successfully")
                        else:
                            print(f"[LLM Agent WARNING] Skipping session history save - session_id or session_manager is None!")

                        # 使用formatter输出工具调用结果
                        self.output_formatter.format_tool_call(
                            tool_name=tool_call['name'],
                            arguments=tool_call['arguments'],
                            result=result
                        )

                    except NeedUserInputException as e:
                        # 需要用户输入，发送询问事件
                        if event_callback:
                            await event_callback({
                                "type": "ask_user",
                                "step": step_count,
                                "question": e.question,
                                "context": e.context
                            })
                        # 重新抛出异常，暂停诊断
                        raise

        # 达到最大步数，生成报告
        print(f"[LLM Agent] 达到最大步数，生成报告\n")
        report = self._generate_report(task, context, None)

        # 发送完成事件
        if event_callback:
            await event_callback({
                "type": "complete",
                "report": {
                    "root_cause": report.root_cause,
                    "confidence": report.confidence * 100,
                    "suggestions": report.fix_suggestions,
                    "total_time": report.total_time
                }
            })

        return report

    async def continue_diagnose(
        self,
        task: DiagnosticTask,
        context: List[Dict],
        user_answer: str,
        event_callback: Optional[Callable] = None,
        stop_event: Optional[asyncio.Event] = None,
        session_id: Optional[str] = None,
        session_manager: Optional[Any] = None
    ) -> DiagnosticReport:
        """
        继续诊断（在用户回答问题后）

        Args:
            task: 诊断任务
            context: 之前的诊断上下文
            user_answer: 用户的回答
            event_callback: 可选的事件回调函数
            stop_event: 停止信号
            session_id: 会话ID
            session_manager: 会话管理器

        Returns:
            DiagnosticReport: 诊断报告

        Raises:
            NeedUserInputException: 如果再次需要用户输入
        """
        # 恢复上下文
        self.current_context = context
        step_count = len([c for c in context if c.get('tool')]) + 1

        # 将用户的回答添加到上下文
        context.append({
            "step": step_count,
            "type": "user_answer",
            "content": user_answer
        })
        self.current_context = context

        print(f"\n[LLM Agent] 继续诊断任务（Step {step_count}）")
        print(f"  用户回答: {user_answer}\n")

        # 发送用户回答事件
        if event_callback:
            await event_callback({
                "type": "user_answer",
                "step": step_count,
                "answer": user_answer
            })

        # 继续诊断循环
        while step_count < self.max_steps:
            # 检查停止信号
            if stop_event and stop_event.is_set():
                print(f"[LLM Agent] 收到停止信号，终止诊断\n")
                if event_callback:
                    await event_callback({
                        "type": "error",
                        "message": "诊断已被用户中止"
                    })
                # 生成部分报告
                return self._generate_report(task, context, None)

            step_count += 1
            print(f"[LLM Agent] Step {step_count}/{self.max_steps}")

            # LLM决策下一步
            decision = await self._llm_decide_next_step(context, task)

            # 检查是否结束
            if decision.get("conclude", False):
                print(f"[LLM Agent] 诊断完成，找到根因\n")
                # 发送完成事件
                if event_callback:
                    report = self._generate_report(task, context, decision)
                    await event_callback({
                        "type": "complete",
                        "report": {
                            "root_cause": report.root_cause,
                            "confidence": report.confidence * 100,
                            "suggestions": report.fix_suggestions,
                            "total_time": report.total_time
                        }
                    })
                    return report
                return self._generate_report(task, context, decision)

            # 执行工具调用
            if decision.get("tool_calls"):
                for tool_call in decision["tool_calls"]:
                    # 每个子步骤前检查一次停止信号
                    if stop_event and stop_event.is_set():
                        return self._generate_report(task, context, None)

                    # 发送工具调用开始事件
                    if event_callback:
                        await event_callback({
                            "type": "tool_start",
                            "step": step_count,
                            "tool": tool_call["name"],
                            "arguments": tool_call["arguments"]
                        })

                    try:
                        result = await self._execute_tool(tool_call, task)

                        # 执行后再次检查停止信号
                        if stop_event and stop_event.is_set():
                            return self._generate_report(task, context, None)

                        # 发送工具调用结果事件
                        if event_callback:
                            await event_callback({
                                "type": "tool_result",
                                "step": step_count,
                                "tool": tool_call["name"],
                                "result": result
                            })

                        context.append({
                            "step": step_count,
                            "tool": tool_call["name"],
                            "arguments": tool_call["arguments"],
                            "result": result
                        })
                        self.current_context = context  # 更新当前上下文

                        # 添加到会话历史记录
                        print(f"[LLM Agent DEBUG - continue] Tool={tool_call['name']}, session_id={session_id}, has_session_manager={session_manager is not None}")
                        if session_id and session_manager:
                            print(f"[LLM Agent DEBUG - continue] Saving tool call to session history...")
                            await session_manager.add_message(
                                session_id=session_id,
                                role="assistant",
                                content=f"执行工具: {tool_call['name']}",
                                metadata={
                                    "tool_call": {
                                        "name": tool_call["name"],
                                        "arguments": tool_call["arguments"],
                                        "result": result
                                    }
                                }
                            )
                            print(f"[LLM Agent DEBUG - continue] Tool call saved successfully")
                        else:
                            print(f"[LLM Agent WARNING - continue] Skipping session history save - session_id or session_manager is None!")

                        # 使用formatter输出工具调用结果
                        self.output_formatter.format_tool_call(
                            tool_name=tool_call['name'],
                            arguments=tool_call['arguments'],
                            result=result
                        )

                    except NeedUserInputException as e:
                        # 需要用户输入，发送询问事件
                        if event_callback:
                            await event_callback({
                                "type": "ask_user",
                                "step": step_count,
                                "question": e.question,
                                "context": e.context
                            })
                        # 重新抛出异常，暂停诊断
                        raise

        # 达到最大步数，生成报告
        print(f"[LLM Agent] 达到最大步数，生成报告\n")
        report = self._generate_report(task, context, None)

        # 发送完成事件
        if event_callback:
            await event_callback({
                "type": "complete",
                "report": {
                    "root_cause": report.root_cause,
                    "confidence": report.confidence * 100,
                    "suggestions": report.fix_suggestions,
                    "total_time": report.total_time
                }
            })

        return report

    def _build_initial_context(self, task: DiagnosticTask) -> List[Dict]:
        """构建初始上下文"""
        return [{
            "step": 0,
            "type": "task_info",
            "data": {
                "source": task.source,
                "target": task.target,
                "protocol": task.protocol.value,
                "port": task.port,
                "fault_type": task.fault_type.value,
                "user_input": task.user_input
            }
        }]

    async def _llm_decide_next_step(self, context: List[Dict], task: DiagnosticTask) -> Dict:
        """
        使用LLM决策下一步操作

        Args:
            context: 当前上下文
            task: 诊断任务

        Returns:
            Dict: 决策结果，包含tool_calls或conclude标志
        """
        # 构建提示词
        prompt = self._build_decision_prompt(context, task)

        # 调用LLM with tools
        response = self.llm_client.invoke_with_tools(
            prompt=prompt,
            tools=self.tools,
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.3
        )

        # 解析响应
        result = {
            "reasoning": response.get("content", ""),
            "tool_calls": [],
            "conclude": False
        }

        # 检查是否有工具调用
        if response.get("tool_calls"):
            for tool_call in response["tool_calls"]:
                arguments = tool_call["arguments"]
                result["tool_calls"].append({
                    "id": tool_call["id"],
                    "name": tool_call["name"],
                    "arguments": arguments
                })
        else:
            # 没有工具调用，说明LLM认为已经可以得出结论
            result["conclude"] = True

        return result

    def _build_decision_prompt(self, context: List[Dict], task: DiagnosticTask) -> str:
        """构建决策提示词"""
        # 任务信息
        prompt = f"""当前诊断任务：
源主机: {task.source}
目标主机: {task.target}
协议: {task.protocol.value}
端口: {task.port}
故障类型: {task.fault_type.value}
用户描述: {task.user_input}

"""
        # 历史执行步骤
        if len(context) > 1:
            prompt += "已执行的诊断步骤和对话历史:\n"
            for ctx in context[1:]:  # 跳过第一个task_info
                if ctx.get("type") == "user_answer":
                    # 用户的回答
                    prompt += f"\nStep {ctx['step']}: [用户回答]\n"
                    prompt += f"  内容: {ctx['content']}\n"
                elif ctx.get("tool"):
                    # 工具调用
                    prompt += f"\nStep {ctx['step']}: {ctx['tool']}\n"
                    prompt += f"  参数: {json.dumps(ctx['arguments'], ensure_ascii=False)}\n"
                    result = ctx.get("result", {})
                    prompt += f"  成功: {result.get('success')}\n"

                    # 智能截断策略：增加截断限制
                    if result.get('stdout'):
                        stdout = result['stdout']
                        if len(stdout) <= 1000:
                            # 短输出：完整显示
                            prompt += f"  输出:\n{stdout}\n"
                        else:
                            # 长输出：显示前800字符 + 提示
                            prompt += f"  输出（前800字符）:\n{stdout[:800]}\n"
                            prompt += f"  ... (输出共{len(stdout)}字符，已截断)\n"

                    if result.get('stderr'):
                        stderr = result['stderr']
                        if len(stderr) <= 500:
                            prompt += f"  错误:\n{stderr}\n"
                        else:
                            prompt += f"  错误（前500字符）:\n{stderr[:500]}\n"
                            prompt += f"  ... (错误输出共{len(stderr)}字符，已截断)\n"

                    # 添加执行时间和退出码
                    prompt += f"  退出码: {result.get('exit_code', 'N/A')}\n"
                    prompt += f"  执行时间: {result.get('execution_time', 0):.2f}秒\n"

        prompt += "\n请分析当前情况，决定下一步操作。如果已经找到根因，请不要调用工具，直接说明结论。"
        return prompt

    async def _execute_tool(self, tool_call: Dict, task: DiagnosticTask) -> Dict:
        """
        执行工具调用

        Args:
            tool_call: 工具调用信息
            task: 诊断任务

        Returns:
            Dict: 工具执行结果
        """
        tool_name = tool_call["name"]
        arguments = tool_call["arguments"]

        try:
            if tool_name == "execute_command":
                host = arguments["host"]
                command = arguments["command"]
                timeout = arguments.get("timeout", 30)

                result = await self.network_tools.execute_command(host, command, timeout)
                return result

            elif tool_name == "query_cmdb":
                hosts = arguments["hosts"]

                result = await self.network_tools.query_cmdb(hosts)
                return result

            elif tool_name == "ask_user":
                # 询问用户，抛出异常以暂停诊断流程
                question = arguments["question"]
                raise NeedUserInputException(question=question, context=self.current_context)

            else:
                return {
                    "success": False,
                    "error": f"未知的工具: {tool_name}"
                }

        except NeedUserInputException:
            # 重新抛出 NeedUserInputException，让上层处理
            raise
        except Exception as e:
            return {
                "success": False,
                "error": f"工具执行失败: {str(e)}"
            }

    def _generate_report(
        self,
        task: DiagnosticTask,
        context: List[Dict],
        decision: Optional[Dict]
    ) -> DiagnosticReport:
        """
        生成诊断报告

        Args:
            task: 诊断任务
            context: 诊断上下文
            decision: 最终决策（如果有）

        Returns:
            DiagnosticReport: 诊断报告
        """
        # 提取根因分析
        if decision and decision.get("reasoning"):
            root_cause_desc = decision["reasoning"]
            confidence = 0.8
        else:
            root_cause_desc = "未能在最大步数内找到明确根因"
            confidence = 0.5

        # 提取证据
        evidence = self._extract_evidence(context)

        # 生成建议措施
        suggestions = self._generate_suggestions(task, context, root_cause_desc)

        # 判断是否需要人工介入（置信度低于0.7）
        need_human = confidence < 0.7

        # 构建执行步骤列表（StepResult对象）
        executed_steps = self._build_step_results(context)

        # 计算总耗时
        total_time = sum(
            ctx.get('result', {}).get('execution_time', 0.0)
            for ctx in context[1:]
            if ctx.get('result')
        )

        # 保存工具调用历史到metadata
        tool_call_history = [
            {
                "step": ctx.get("step"),
                "tool": ctx.get("tool"),
                "arguments": ctx.get("arguments"),
                "result_summary": {
                    "success": ctx.get("result", {}).get("success", False),
                    "execution_time": ctx.get("result", {}).get("execution_time", 0.0),
                    "stdout": ctx.get("result", {}).get("stdout", "")[:200],  # 限制长度
                    "stderr": ctx.get("result", {}).get("stderr", "")[:200]
                }
            }
            for ctx in context[1:]  # 跳过初始任务信息
            if ctx.get("tool")
        ]

        # 创建诊断报告
        return DiagnosticReport(
            task_id=task.task_id,
            root_cause=root_cause_desc,
            confidence=confidence,
            evidence=evidence,
            fix_suggestions=suggestions,
            need_human=need_human,
            executed_steps=executed_steps,
            total_time=total_time,
            metadata={"tool_call_history": tool_call_history}
        )

    def _extract_evidence(self, context: List[Dict]) -> List[str]:
        """从上下文中提取证据"""
        evidence = []
        for ctx in context[1:]:
            if ctx.get("tool") and ctx.get("result"):
                result = ctx["result"]
                tool_name = ctx['tool']

                # 构建更详细的证据
                if result.get("success"):
                    # 成功的命令：显示关键输出（增加到200字符）
                    stdout = result.get('stdout', '')
                    if len(stdout) <= 200:
                        evidence.append(f"{tool_name}: {stdout}")
                    else:
                        # 显示前200字符
                        evidence.append(f"{tool_name}: {stdout[:200]}...")
                else:
                    # 失败的命令：显示错误信息（增加到200字符）
                    stderr = result.get('stderr', '')
                    if len(stderr) <= 200:
                        evidence.append(f"{tool_name}: 失败 - {stderr}")
                    else:
                        evidence.append(f"{tool_name}: 失败 - {stderr[:200]}...")

        return evidence

    def _build_step_results(self, context: List[Dict]) -> List[StepResult]:
        """
        将上下文转换为StepResult对象列表

        Args:
            context: 诊断上下文

        Returns:
            StepResult对象列表
        """
        step_results = []
        for ctx in context[1:]:  # 跳过第一个task_info
            if ctx.get('tool'):
                # 构建CommandResult（如果有）
                command_result = None
                result = ctx.get('result', {})
                if result.get('command'):
                    command_result = CommandResult(
                        command=result.get('command', ''),
                        host=result.get('host', ''),
                        success=result.get('success', False),
                        stdout=result.get('stdout', ''),
                        stderr=result.get('stderr', ''),
                        exit_code=result.get('exit_code', -1),
                        execution_time=result.get('execution_time', 0.0)
                    )

                # 构建StepResult
                step_result = StepResult(
                    step_number=ctx['step'],
                    step_name=ctx['tool'],
                    action=ctx['tool'],
                    success=result.get('success', False),
                    command_result=command_result,
                    metadata=ctx.get('arguments', {})
                )
                step_results.append(step_result)

        return step_results

    def _generate_suggestions(
        self,
        task: DiagnosticTask,
        context: List[Dict],
        root_cause_desc: str
    ) -> List[str]:
        """生成建议措施"""
        suggestions = []

        # 根据根因描述生成建议
        desc_lower = root_cause_desc.lower()

        if "refused" in desc_lower or "未监听" in desc_lower:
            suggestions.append(f"检查目标主机{task.target}上的服务是否启动")
            suggestions.append(f"确认服务配置的监听端口是否为{task.port}")

        if "timeout" in desc_lower or "不可达" in desc_lower:
            suggestions.append(f"检查{task.source}到{task.target}的网络连通性")
            suggestions.append("检查防火墙规则是否阻止了连接")

        if "防火墙" in desc_lower or "iptables" in desc_lower:
            suggestions.append("检查并修改防火墙规则，允许相应端口的流量")

        # 默认建议
        if not suggestions:
            suggestions.append("请根据诊断结果进一步排查问题")

        return suggestions
