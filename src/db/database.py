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
            
            # 创建网络访问关系资产表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS network_access_assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    src_system TEXT NOT NULL,
                    src_system_name TEXT,
                    src_deploy_unit TEXT,
                    src_ip TEXT,
                    dst_system TEXT NOT NULL,
                    dst_deploy_unit TEXT,
                    dst_ip TEXT,
                    protocol TEXT DEFAULT 'TCP',
                    port TEXT,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
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

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_assets_src_system
                ON network_access_assets(src_system)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_assets_dst_system
                ON network_access_assets(dst_system)
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

    # ===== 网络访问关系资产 CRUD =====

    async def create_access_asset(self, asset_data: Dict[str, Any]) -> Optional[int]:
        """
        新增一条网络访问关系资产

        Args:
            asset_data: 资产数据字典

        Returns:
            新记录的 id，失败返回 None
        """
        try:
            now = datetime.now().isoformat()
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    INSERT INTO network_access_assets (
                        src_system, src_system_name, src_deploy_unit, src_ip,
                        dst_system, dst_deploy_unit, dst_ip,
                        protocol, port, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    asset_data['src_system'],
                    asset_data.get('src_system_name', ''),
                    asset_data.get('src_deploy_unit', ''),
                    asset_data.get('src_ip', ''),
                    asset_data['dst_system'],
                    asset_data.get('dst_deploy_unit', ''),
                    asset_data.get('dst_ip', ''),
                    asset_data.get('protocol', 'TCP'),
                    asset_data.get('port', ''),
                    now,
                    now
                ))
                await db.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"[SessionDatabase] 新增访问关系资产失败: {e}")
            return None

    async def query_access_assets(
        self,
        src_system: Optional[str] = None,
        dst_system: Optional[str] = None,
        src_deploy_unit: Optional[str] = None,
        keyword: Optional[str] = None,
        protocol: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        查询网络访问关系资产（支持多条件+分页）

        Args:
            src_system: 按源系统过滤（模糊匹配 src_system 或 src_system_name）
            dst_system: 按目的系统过滤（模糊匹配）
            src_deploy_unit: 按源部署单元过滤（精确匹配 src_deploy_unit）
            keyword: 全字段模糊搜索关键词
            protocol: 按协议精确过滤

        Returns:
            {"items": [...], "total": int, "page": int, "page_size": int}
        """
        try:
            conditions = []
            params = []

            if src_system:
                conditions.append("(src_system LIKE ? OR src_system_name LIKE ?)")
                params.extend([f"%{src_system}%", f"%{src_system}%"])
            if dst_system:
                conditions.append("(dst_system LIKE ?)")
                params.append(f"%{dst_system}%")
            if src_deploy_unit:
                conditions.append("(src_deploy_unit = ?)")
                params.append(src_deploy_unit)
            if keyword:
                conditions.append(
                    "(src_system LIKE ? OR src_system_name LIKE ? OR dst_system LIKE ? "
                    "OR src_deploy_unit LIKE ? OR dst_deploy_unit LIKE ? "
                    "OR src_ip LIKE ? OR dst_ip LIKE ?)"
                )
                params.extend([f"%{keyword}%"] * 7)
            if protocol:
                conditions.append("protocol = ?")
                params.append(protocol)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row

                # 查询总数
                count_sql = f"SELECT COUNT(*) FROM network_access_assets {where_clause}"
                async with db.execute(count_sql, params) as cursor:
                    row = await cursor.fetchone()
                    total = row[0] if row else 0

                # 查询分页数据
                offset = (page - 1) * page_size
                data_sql = (
                    f"SELECT * FROM network_access_assets {where_clause} "
                    f"ORDER BY id DESC LIMIT ? OFFSET ?"
                )
                async with db.execute(data_sql, params + [page_size, offset]) as cursor:
                    rows = await cursor.fetchall()
                    items = [dict(row) for row in rows]

            return {"items": items, "total": total, "page": page, "page_size": page_size}
        except Exception as e:
            print(f"[SessionDatabase] 查询访问关系资产失败: {e}")
            return {"items": [], "total": 0, "page": page, "page_size": page_size}

    @staticmethod
    def _system_name_candidates(system_name: str) -> List[str]:
        """Build conservative Chinese system-name aliases for lookup."""
        stripped = system_name.strip()
        compact = "".join(stripped.split())
        candidates: List[str] = []

        for value in (stripped, compact):
            if value and value not in candidates:
                candidates.append(value)

        for value in list(candidates):
            if value.endswith("\u7cfb\u7edf") and len(value) > len("\u7cfb\u7edf"):
                without_generic_suffix = value[:-len("\u7cfb\u7edf")].strip()
                if without_generic_suffix and without_generic_suffix not in candidates:
                    candidates.append(without_generic_suffix)

        return candidates

    async def _resolve_system_codes(
        self,
        db: aiosqlite.Connection,
        system_code: Optional[str] = None,
        system_name: Optional[str] = None
    ) -> List[str]:
        """Resolve source-side system codes from explicit code or system name."""
        if system_code:
            return [system_code.strip()]

        if not system_name:
            return []

        candidates = self._system_name_candidates(system_name)
        if not candidates:
            return []

        conditions = []
        params: List[Any] = []
        for candidate in candidates:
            conditions.append("src_system_name = ?")
            params.append(candidate)
        for candidate in candidates:
            conditions.append("src_system_name LIKE ?")
            params.append(f"%{candidate}%")

        async with db.execute(
            f"""
            SELECT DISTINCT src_system
            FROM network_access_assets
            WHERE {" OR ".join(conditions)}
            ORDER BY src_system
            """,
            params
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows if row and row[0]]

    async def _query_directional_access_relations(
        self,
        db: aiosqlite.Connection,
        direction: str,
        system_codes: List[str],
        deploy_unit: Optional[str],
        peer_system_codes: List[str],
        src_ip: Optional[str] = None,
        dst_ip: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Query one direction of access relations."""
        conditions = []
        params: List[Any] = []

        if direction == "outbound":
            system_field = "src_system"
            deploy_field = "src_deploy_unit"
            peer_field = "dst_system"
            ip_field = "src_ip"
            peer_ip_field = "dst_ip"
        else:
            system_field = "dst_system"
            deploy_field = "dst_deploy_unit"
            peer_field = "src_system"
            ip_field = "dst_ip"
            peer_ip_field = "src_ip"

        if system_codes:
            placeholders = ",".join("?" for _ in system_codes)
            conditions.append(f"{system_field} IN ({placeholders})")
            params.extend(system_codes)

        if deploy_unit:
            conditions.append(f"{deploy_field} = ?")
            params.append(deploy_unit.strip())

        if peer_system_codes:
            placeholders = ",".join("?" for _ in peer_system_codes)
            conditions.append(f"{peer_field} IN ({placeholders})")
            params.extend(peer_system_codes)

        # Add IP address filtering
        if src_ip:
            conditions.append(f"src_ip = ?")
            params.append(src_ip.strip())

        if dst_ip:
            conditions.append(f"dst_ip = ?")
            params.append(dst_ip.strip())

        if not conditions:
            return []

        where_clause = " AND ".join(conditions)
        async with db.execute(
            f"SELECT * FROM network_access_assets WHERE {where_clause} ORDER BY id DESC",
            params
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def query_access_relations(
        self,
        system_code: Optional[str] = None,
        system_name: Optional[str] = None,
        deploy_unit: Optional[str] = None,
        direction: str = "outbound",
        peer_system_code: Optional[str] = None,
        peer_system_name: Optional[str] = None,
        src_ip: Optional[str] = None,
        dst_ip: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """Query access relations for chat/tool-calling scenarios.
        
        Args:
            system_code: System code (e.g., N-CRM)
            system_name: System name (e.g., 客户关系管理系统)
            deploy_unit: Deploy unit (e.g., CRMJS_AP)
            direction: Query direction - "outbound", "inbound", or "both"
            peer_system_code: Peer system code
            peer_system_name: Peer system name
            src_ip: Source IP address (e.g., 10.0.1.10)
            dst_ip: Destination IP address (e.g., 10.0.2.20)
            page: Page number (default 1)
            page_size: Page size (default 50, max 100)
        """
        try:
            if direction not in {"outbound", "inbound", "both"}:
                raise ValueError(f"Unsupported direction: {direction}")

            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row

                system_codes = await self._resolve_system_codes(
                    db=db,
                    system_code=system_code,
                    system_name=system_name
                )
                peer_system_codes = await self._resolve_system_codes(
                    db=db,
                    system_code=peer_system_code,
                    system_name=peer_system_name
                )

                if (system_code or system_name) and not system_codes:
                    return {"items": [], "total": 0, "page": page, "page_size": page_size}
                if (peer_system_code or peer_system_name) and not peer_system_codes:
                    return {"items": [], "total": 0, "page": page, "page_size": page_size}

                if direction == "both":
                    outbound_items = await self._query_directional_access_relations(
                        db=db,
                        direction="outbound",
                        system_codes=system_codes,
                        deploy_unit=deploy_unit,
                        peer_system_codes=peer_system_codes,
                        src_ip=src_ip,
                        dst_ip=dst_ip
                    )
                    inbound_items = await self._query_directional_access_relations(
                        db=db,
                        direction="inbound",
                        system_codes=system_codes,
                        deploy_unit=deploy_unit,
                        peer_system_codes=peer_system_codes,
                        src_ip=src_ip,
                        dst_ip=dst_ip
                    )

                    merged = {}
                    for item in outbound_items + inbound_items:
                        merged[item["id"]] = item
                    items = sorted(merged.values(), key=lambda item: item["id"], reverse=True)
                else:
                    items = await self._query_directional_access_relations(
                        db=db,
                        direction=direction,
                        system_codes=system_codes,
                        deploy_unit=deploy_unit,
                        peer_system_codes=peer_system_codes,
                        src_ip=src_ip,
                        dst_ip=dst_ip
                    )

            total = len(items)
            safe_page = max(1, page)
            safe_page_size = min(100, max(1, page_size))
            offset = (safe_page - 1) * safe_page_size
            paged_items = items[offset:offset + safe_page_size]
            return {
                "items": paged_items,
                "total": total,
                "page": safe_page,
                "page_size": safe_page_size,
            }
        except Exception as e:
            print(f"[SessionDatabase] chat 查询访问关系失败: {e}")
            return {"items": [], "total": 0, "page": page, "page_size": page_size}

    async def delete_access_asset(self, asset_id: int) -> bool:
        """
        删除一条网络访问关系资产

        Args:
            asset_id: 记录 id

        Returns:
            是否成功
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                result = await db.execute(
                    "DELETE FROM network_access_assets WHERE id = ?",
                    (asset_id,)
                )
                await db.commit()
                return result.rowcount > 0
        except Exception as e:
            print(f"[SessionDatabase] 删除访问关系资产失败: {e}")
            return False

    async def seed_access_assets_if_empty(self) -> int:
        """
        如果访问关系资产表为空，插入 Mock 示例数据

        Returns:
            插入的记录数
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT COUNT(*) FROM network_access_assets") as cursor:
                    row = await cursor.fetchone()
                    if row and row[0] > 0:
                        return 0  # 已有数据，不重复插入

            mock_data = [
                {
                    'src_system': 'N-AQM', 'src_system_name': '金融资产质量管理',
                    'src_deploy_unit': 'AQMJS_AP', 'src_ip': '10.37.1.116\n10.37.1.20',
                    'dst_system': 'P-ZH-DMP-CONF', 'dst_deploy_unit': 'ADDNG_WB',
                    'dst_ip': '10.87.28.127', 'protocol': 'TCP', 'port': '8080\n8900'
                },
                {
                    'src_system': 'N-AQM', 'src_system_name': '金融资产质量管理',
                    'src_deploy_unit': 'AQMJS_AP', 'src_ip': '10.37.1.116\n10.37.1.20',
                    'dst_system': 'P-ZH-DMP-CONF', 'dst_deploy_unit': 'ADNNG_WB',
                    'dst_ip': '10.36.16.67', 'protocol': 'TCP', 'port': '8080\n8900'
                },
                {
                    'src_system': 'N-AQM', 'src_system_name': '金融资产质量管理',
                    'src_deploy_unit': 'AQMJS_AP', 'src_ip': '10.37.1.116\n10.37.1.20',
                    'dst_system': 'P-ZH-DMP-CONF', 'dst_deploy_unit': 'ADNNG_WB',
                    'dst_ip': '10.36.24.98', 'protocol': 'TCP', 'port': '8080\n8900'
                },
                {
                    'src_system': 'N-AQM', 'src_system_name': '金融资产质量管理',
                    'src_deploy_unit': 'AQMJS_AP', 'src_ip': '10.37.1.116\n10.37.1.20',
                    'dst_system': 'P-ZH-DMP-CONF', 'dst_deploy_unit': 'ADDNG_WB',
                    'dst_ip': '10.87.20.106', 'protocol': 'TCP', 'port': '8080\n8900'
                },
                {
                    'src_system': 'N-AQM', 'src_system_name': '金融资产质量管理',
                    'src_deploy_unit': 'AQMJS_AP', 'src_ip': '10.37.1.116\n10.37.1.20',
                    'dst_system': 'P-ZH-DMP-CONF', 'dst_deploy_unit': 'ACNNG_WB',
                    'dst_ip': '10.36.24.113', 'protocol': 'TCP', 'port': '8070'
                },
                {
                    'src_system': 'N-AQM', 'src_system_name': '金融资产质量管理',
                    'src_deploy_unit': 'AQMJS_AP', 'src_ip': '10.37.1.116\n10.37.1.20',
                    'dst_system': 'P-ZH-DMP-CONF', 'dst_deploy_unit': 'ACNNG_WB',
                    'dst_ip': '10.36.16.30', 'protocol': 'TCP', 'port': '8070'
                },
                {
                    'src_system': 'N-AQM', 'src_system_name': '金融资产质量管理',
                    'src_deploy_unit': 'AQMJS_AP', 'src_ip': '10.37.1.116\n10.37.1.20',
                    'dst_system': 'P-ZH-DMP-CONF', 'dst_deploy_unit': 'ACDNG_WB',
                    'dst_ip': '10.87.20.108', 'protocol': 'TCP', 'port': '8070'
                },
                {
                    'src_system': 'N-CRM', 'src_system_name': '客户关系管理系统',
                    'src_deploy_unit': 'CRMJS_AP', 'src_ip': '10.38.1.100\n10.38.1.101',
                    'dst_system': 'N-AQM', 'dst_deploy_unit': 'AQMJS_AP',
                    'dst_ip': '10.37.1.116', 'protocol': 'TCP', 'port': '8080'
                },
                {
                    'src_system': 'N-CRM', 'src_system_name': '客户关系管理系统',
                    'src_deploy_unit': 'CRMJS_AP', 'src_ip': '10.38.1.100\n10.38.1.101',
                    'dst_system': 'P-DB-MAIN', 'dst_deploy_unit': 'DBMAIN_DB',
                    'dst_ip': '10.20.5.50', 'protocol': 'TCP', 'port': '1521'
                },
                {
                    'src_system': 'N-OA', 'src_system_name': '办公自动化系统',
                    'src_deploy_unit': 'OAJS_AP', 'src_ip': '10.40.1.10',
                    'dst_system': 'N-CRM', 'dst_deploy_unit': 'CRMJS_AP',
                    'dst_ip': '10.38.1.100', 'protocol': 'TCP', 'port': '8443'
                },
                {
                    'src_system': 'N-OA', 'src_system_name': '办公自动化系统',
                    'src_deploy_unit': 'OAJS_WEB', 'src_ip': '10.40.2.10\n10.40.2.11',
                    'dst_system': 'N-OA', 'dst_deploy_unit': 'OAJS_AP',
                    'dst_ip': '10.40.1.10', 'protocol': 'TCP', 'port': '8080'
                },
                {
                    'src_system': 'N-OA', 'src_system_name': '办公自动化系统',
                    'src_deploy_unit': 'OAJS_WEB', 'src_ip': '10.40.2.10\n10.40.2.11',
                    'dst_system': 'P-ZH-DMP-CONF', 'dst_deploy_unit': 'ADDNG_WB',
                    'dst_ip': '10.87.28.127', 'protocol': 'TCP', 'port': '443'
                },
                {
                    'src_system': 'N-OA', 'src_system_name': '办公自动化系统',
                    'src_deploy_unit': 'OAJS_DB', 'src_ip': '10.40.3.10',
                    'dst_system': 'P-DB-MAIN', 'dst_deploy_unit': 'DBMAIN_DB',
                    'dst_ip': '10.20.5.50', 'protocol': 'TCP', 'port': '1521'
                },
            ]

            count = 0
            for item in mock_data:
                result = await self.create_access_asset(item)
                if result:
                    count += 1
            print(f"[SessionDatabase] 已插入 {count} 条访问关系 Mock 数据")
            return count
        except Exception as e:
            print(f"[SessionDatabase] 插入 Mock 数据失败: {e}")
            return 0
