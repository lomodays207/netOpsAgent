"""
SQLite 数据库管理模块

提供会话和消息的持久化存储功能
"""
import aiosqlite
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path


class SessionDatabase:
    """SQLite 数据库管理器"""
    
    def __init__(self, db_path: str = "runtime/sessions.db"):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._ensure_runtime_dir()
    
    def _ensure_runtime_dir(self):
        """确保 runtime 目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            print(f"[SessionDatabase] 创建目录: {db_dir}")
    
    async def initialize(self):
        """初始化数据库表结构"""
        async with aiosqlite.connect(self.db_path) as db:
            # 启用 WAL 模式（Write-Ahead Logging）提高并发性能
            await db.execute("PRAGMA journal_mode=WAL")
            
            # 创建会话表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    task_data TEXT NOT NULL,
                    context TEXT,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    pending_question TEXT,
                    llm_config TEXT
                )
            """)
            
            # 创建消息表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
            """)
            
            # 创建索引
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_status 
                ON sessions(status)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_updated_at 
                ON sessions(updated_at)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session_id 
                ON messages(session_id)
            """)
            
            await db.commit()
            print(f"[SessionDatabase] 数据库初始化完成: {self.db_path}")
    
    async def create_session(self, session_data: Dict[str, Any]) -> bool:
        """
        创建新会话
        
        Args:
            session_data: 会话数据字典，包含所有必要字段
            
        Returns:
            是否成功
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO sessions (
                        session_id, task_data, context, status,
                        created_at, updated_at, pending_question, llm_config
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_data['session_id'],
                    session_data['task_data'],
                    session_data.get('context'),
                    session_data['status'],
                    session_data['created_at'],
                    session_data['updated_at'],
                    session_data.get('pending_question'),
                    session_data.get('llm_config')
                ))
                await db.commit()
                return True
        except Exception as e:
            print(f"[SessionDatabase] 创建会话失败: {e}")
            return False
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取会话数据
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话数据字典，如果不存在则返回 None
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM sessions WHERE session_id = ?",
                    (session_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return dict(row)
                    return None
        except Exception as e:
            print(f"[SessionDatabase] 获取会话失败: {e}")
            return None
    
    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新会话数据
        
        Args:
            session_id: 会话ID
            updates: 要更新的字段字典
            
        Returns:
            是否成功
        """
        try:
            # 构建 UPDATE 语句
            set_clauses = []
            values = []
            
            for key, value in updates.items():
                set_clauses.append(f"{key} = ?")
                values.append(value)
            
            # 总是更新 updated_at
            if 'updated_at' not in updates:
                set_clauses.append("updated_at = ?")
                values.append(datetime.now().isoformat())
            
            values.append(session_id)
            
            sql = f"UPDATE sessions SET {', '.join(set_clauses)} WHERE session_id = ?"
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(sql, values)
                await db.commit()
                return True
        except Exception as e:
            print(f"[SessionDatabase] 更新会话失败: {e}")
            return False
    
    async def delete_session(self, session_id: str) -> bool:
        """
        删除会话（级联删除相关消息）
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否成功
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "DELETE FROM sessions WHERE session_id = ?",
                    (session_id,)
                )
                await db.commit()
                return True
        except Exception as e:
            print(f"[SessionDatabase] 删除会话失败: {e}")
            return False
    
    async def add_message(self, message_data: Dict[str, Any]) -> bool:
        """
        添加消息
        
        Args:
            message_data: 消息数据字典
            
        Returns:
            是否成功
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO messages (
                        session_id, role, content, timestamp, metadata
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    message_data['session_id'],
                    message_data['role'],
                    message_data['content'],
                    message_data['timestamp'],
                    message_data.get('metadata')
                ))
                await db.commit()
                return True
        except Exception as e:
            print(f"[SessionDatabase] 添加消息失败: {e}")
            return False
    
    async def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """
        获取会话的所有消息
        
        Args:
            session_id: 会话ID
            
        Returns:
            消息列表
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC",
                    (session_id,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            print(f"[SessionDatabase] 获取消息失败: {e}")
            return []
    
    async def cleanup_expired(self, ttl_seconds: int) -> int:
        """
        清理过期会话
        
        Args:
            ttl_seconds: 会话超时时间（秒）
            
        Returns:
            清理的会话数量
        """
        try:
            from datetime import timedelta
            cutoff_time = (datetime.now() - timedelta(seconds=ttl_seconds)).isoformat()
            
            async with aiosqlite.connect(self.db_path) as db:
                # 先查询要删除的会话数量
                async with db.execute(
                    "SELECT COUNT(*) FROM sessions WHERE updated_at < ?",
                    (cutoff_time,)
                ) as cursor:
                    row = await cursor.fetchone()
                    count = row[0] if row else 0
                
                # 删除过期会话
                await db.execute(
                    "DELETE FROM sessions WHERE updated_at < ?",
                    (cutoff_time,)
                )
                await db.commit()
                
                return count
        except Exception as e:
            print(f"[SessionDatabase] 清理过期会话失败: {e}")
            return 0
    
    async def get_all_sessions(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取所有会话（可选按状态过滤）
        
        Args:
            status: 可选的状态过滤
            
        Returns:
            会话列表
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                if status:
                    sql = "SELECT * FROM sessions WHERE status = ? ORDER BY updated_at DESC"
                    params = (status,)
                else:
                    sql = "SELECT * FROM sessions ORDER BY updated_at DESC"
                    params = ()
                
                async with db.execute(sql, params) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            print(f"[SessionDatabase] 获取所有会话失败: {e}")
            return []
