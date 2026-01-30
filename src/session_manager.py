"""
会话管理器 - 用于管理多轮对话诊断的会话状态
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import json
from dataclasses import dataclass, field


@dataclass
class DiagnosisSession:
    """诊断会话"""
    session_id: str
    task: Any  # DiagnosticTask
    context: List[Dict] = field(default_factory=list)
    messages: List[Dict] = field(default_factory=list)  # 对话历史
    status: str = "active"  # active, waiting_user, completed, error
    llm_client: Any = None
    agent: Any = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    pending_question: Optional[str] = None  # LLM 的提问
    stop_event: Optional[asyncio.Event] = None  # 停止信号


class SessionManager:
    """会话管理器（内存版本）"""

    def __init__(self, ttl_seconds: int = 3600):
        """
        初始化会话管理器

        Args:
            ttl_seconds: 会话超时时间（秒），默认 1 小时
        """
        self.sessions: Dict[str, DiagnosisSession] = {}
        self.ttl_seconds = ttl_seconds
        self._cleanup_task = None

    async def start_cleanup(self):
        """启动后台清理任务"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        """定期清理过期会话"""
        while True:
            await asyncio.sleep(300)  # 每 5 分钟清理一次
            await self.cleanup_expired()

    async def cleanup_expired(self):
        """清理过期会话"""
        now = datetime.now()
        expired_ids = [
            sid for sid, session in self.sessions.items()
            if (now - session.updated_at).total_seconds() > self.ttl_seconds
        ]
        for sid in expired_ids:
            del self.sessions[sid]
        if expired_ids:
            print(f"[SessionManager] 清理了 {len(expired_ids)} 个过期会话")

    def create_session(self, session_id: str, task: Any, llm_client: Any, agent: Any) -> DiagnosisSession:
        """创建新会话"""
        session = DiagnosisSession(
            session_id=session_id,
            task=task,
            llm_client=llm_client,
            agent=agent,
            stop_event=asyncio.Event()
        )
        self.sessions[session_id] = session
        print(f"[SessionManager] 创建会话: {session_id}")
        return session

    async def get_session(self, session_id: str) -> Optional[DiagnosisSession]:
        """获取会话"""
        session = self.sessions.get(session_id)
        if session:
            session.updated_at = datetime.now()
        return session

    def update_session(self, session_id: str, **kwargs):
        """更新会话状态"""
        session = self.sessions.get(session_id)
        if session:
            for key, value in kwargs.items():
                setattr(session, key, value)
            session.updated_at = datetime.now()

    def delete_session(self, session_id: str):
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            print(f"[SessionManager] 删除会话: {session_id}")

    async def add_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict] = None):
        """添加对话消息"""
        session = self.sessions.get(session_id)
        if session:
            message = {
                "role": role,  # user, assistant, system
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            session.messages.append(message)
            session.updated_at = datetime.now()

    async def stop_session(self, session_id: str):
        """停止会话的执行"""
        session = self.sessions.get(session_id)
        if session and session.stop_event:
            session.stop_event.set()
            print(f"[SessionManager] 停止会话信号已发送: {session_id}")


class SQLiteSessionManager(SessionManager):
    """SQLite持久化会话管理器"""

    def __init__(self, ttl_seconds: int = 3600, db_path: str = "runtime/sessions.db"):
        """
        初始化SQLite会话管理器

        Args:
            ttl_seconds: 会话超时时间（秒），默认 1 小时
            db_path: 数据库文件路径
        """
        super().__init__(ttl_seconds)
        self.db_path = db_path
        self.db = None
        self._initialized = False

    async def initialize(self):
        """初始化数据库"""
        if self._initialized:
            return

        from .db import SessionDatabase
        self.db = SessionDatabase(self.db_path)
        await self.db.initialize()
        self._initialized = True
        print(f"[SQLiteSessionManager] 数据库初始化完成")

    def create_session(self, session_id: str, task: Any, llm_client: Any, agent: Any) -> DiagnosisSession:
        """创建新会话并持久化"""
        from .db import serialize_task, serialize_context, extract_llm_config

        # 创建会话对象
        session = DiagnosisSession(
            session_id=session_id,
            task=task,
            llm_client=llm_client,
            agent=agent,
            stop_event=asyncio.Event()
        )

        # 序列化数据
        session_data = {
            'session_id': session_id,
            'task_data': serialize_task(task),
            'context': serialize_context([]),
            'status': 'active',
            'created_at': session.created_at.isoformat(),
            'updated_at': session.updated_at.isoformat(),
            'pending_question': None,
            'llm_config': extract_llm_config(llm_client)
        }

        # 异步保存到数据库
        asyncio.create_task(self.db.create_session(session_data))

        # 同时保存到内存（用于快速访问）
        self.sessions[session_id] = session
        print(f"[SQLiteSessionManager] 创建会话: {session_id}")

        return session

    async def get_session(self, session_id: str) -> Optional[DiagnosisSession]:
        """从数据库恢复会话"""
        from .db import (
            deserialize_task,
            deserialize_context,
            rebuild_llm_client,
            deserialize_messages
        )
        from .agent.llm_agent import LLMAgent

        # 先尝试从内存获取
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.updated_at = datetime.now()
            return session

        # 从数据库恢复
        session_data = await self.db.get_session(session_id)
        if not session_data:
            return None

        try:
            # 反序列化 task
            task = deserialize_task(session_data['task_data'])

            # 反序列化 context
            context = deserialize_context(session_data['context']) if session_data['context'] else []

            # 重建 LLMClient
            llm_client = rebuild_llm_client(session_data['llm_config'])

            # 重建 Agent 并恢复 context
            agent = LLMAgent(llm_client=llm_client)
            agent.current_context = context  # 恢复上下文

            # 从数据库加载消息历史
            messages_data = await self.db.get_messages(session_id)
            messages = []
            for msg_data in messages_data:
                messages.append({
                    'role': msg_data['role'],
                    'content': msg_data['content'],
                    'timestamp': msg_data['timestamp'],
                    'metadata': json.loads(msg_data['metadata']) if msg_data.get('metadata') else {}
                })

            # 构造 DiagnosisSession 对象
            session = DiagnosisSession(
                session_id=session_id,
                task=task,
                context=context,
                messages=messages,
                status=session_data['status'],
                llm_client=llm_client,
                agent=agent,
                created_at=datetime.fromisoformat(session_data['created_at']),
                updated_at=datetime.fromisoformat(session_data['updated_at']),
                pending_question=session_data.get('pending_question'),
                stop_event=asyncio.Event()
            )

            # 缓存到内存
            self.sessions[session_id] = session
            print(f"[SQLiteSessionManager] 从数据库恢复会话: {session_id}")

            return session

        except Exception as e:
            print(f"[SQLiteSessionManager] 恢复会话失败 {session_id}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def update_session(self, session_id: str, **kwargs):
        """更新会话状态并持久化"""
        from .db import serialize_context

        # 更新内存中的会话
        super().update_session(session_id, **kwargs)

        # 准备数据库更新
        updates = {}
        for key, value in kwargs.items():
            if key == 'context':
                updates['context'] = serialize_context(value)
            elif key in ['status', 'pending_question']:
                updates[key] = value

        if updates:
            updates['updated_at'] = datetime.now().isoformat()
            asyncio.create_task(self.db.update_session(session_id, updates))

    def delete_session(self, session_id: str):
        """删除会话"""
        # 从内存删除
        super().delete_session(session_id)

        # 从数据库删除
        asyncio.create_task(self.db.delete_session(session_id))

    async def add_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict] = None):
        """添加对话消息并持久化"""
        # 添加到内存
        await super().add_message(session_id, role, content, metadata)

        # 持久化到数据库
        message_data = {
            'session_id': session_id,
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'metadata': json.dumps(metadata or {}, ensure_ascii=False)
        }
        await self.db.add_message(message_data)

    async def cleanup_expired(self):
        """清理过期会话"""
        if not self.db:
            return

        # 从数据库清理
        count = await self.db.cleanup_expired(self.ttl_seconds)

        # 从内存清理
        now = datetime.now()
        expired_ids = [
            sid for sid, session in self.sessions.items()
            if (now - session.updated_at).total_seconds() > self.ttl_seconds
        ]
        for sid in expired_ids:
            del self.sessions[sid]

        if count > 0 or expired_ids:
            print(f"[SQLiteSessionManager] 清理了 {count} 个数据库会话，{len(expired_ids)} 个内存会话")


# 全局单例
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """获取全局会话管理器"""
    global _session_manager
    if _session_manager is None:
        # 使用 SQLite 版本，TTL 设置为 30 天（2592000 秒）
        # 这样聊天历史记录可以保存更长时间
        _session_manager = SQLiteSessionManager(ttl_seconds=2592000)  # 30 天
    return _session_manager
