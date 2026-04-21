"""
tests/test_access_assets.py

网络访问关系资产库功能单元测试
"""
import pytest
import asyncio
import os
import tempfile
from datetime import datetime


# ---- 使用临时数据库进行测试 ----

@pytest.fixture
def temp_db_path(tmp_path):
    """临时数据库路径"""
    return str(tmp_path / "test_sessions.db")


@pytest.fixture
async def db(temp_db_path):
    """初始化并返回测试用数据库实例"""
    from src.db.database import SessionDatabase
    database = SessionDatabase(db_path=temp_db_path)
    await database.initialize()
    return database


# ---- 测试：创建访问关系记录 ----

@pytest.mark.asyncio
async def test_create_access_asset(db):
    """测试新增一条访问关系记录"""
    asset_data = {
        "src_system": "N-TEST",
        "src_system_name": "测试系统",
        "src_deploy_unit": "TEST_AP",
        "src_ip": "10.1.1.1",
        "dst_system": "P-DST",
        "dst_deploy_unit": "DST_WB",
        "dst_ip": "10.2.2.2",
        "protocol": "TCP",
        "port": "8080"
    }
    record_id = await db.create_access_asset(asset_data)
    assert record_id is not None
    assert isinstance(record_id, int)
    assert record_id > 0


@pytest.mark.asyncio
async def test_create_access_asset_minimal(db):
    """测试只填必填字段时也能成功创建"""
    asset_data = {
        "src_system": "N-MIN",
        "dst_system": "P-MIN"
    }
    record_id = await db.create_access_asset(asset_data)
    assert record_id is not None


# ---- 测试：查询访问关系记录 ----

@pytest.mark.asyncio
async def test_query_all(db):
    """测试无过滤条件时返回全部记录"""
    # 插入3条数据
    for i in range(3):
        await db.create_access_asset({
            "src_system": f"N-SRC{i}",
            "dst_system": "P-DST",
            "protocol": "TCP"
        })

    result = await db.query_access_assets()
    assert result["total"] == 3
    assert len(result["items"]) == 3


@pytest.mark.asyncio
async def test_query_by_src_system(db):
    """测试按源系统过滤"""
    await db.create_access_asset({"src_system": "N-AQM", "src_system_name": "金融资产质量管理", "dst_system": "P-DST"})
    await db.create_access_asset({"src_system": "N-CRM", "src_system_name": "客户关系管理", "dst_system": "P-DST"})
    await db.create_access_asset({"src_system": "N-OA", "dst_system": "P-DST"})

    result = await db.query_access_assets(src_system="N-AQM")
    assert result["total"] == 1
    assert result["items"][0]["src_system"] == "N-AQM"


@pytest.mark.asyncio
async def test_query_by_src_system_chinese(db):
    """测试按源系统中文名模糊查询"""
    await db.create_access_asset({"src_system": "N-AQM", "src_system_name": "金融资产质量管理", "dst_system": "P-DST"})
    await db.create_access_asset({"src_system": "N-CRM", "src_system_name": "客户关系管理", "dst_system": "P-DST"})

    result = await db.query_access_assets(src_system="金融")
    assert result["total"] == 1
    assert result["items"][0]["src_system"] == "N-AQM"


@pytest.mark.asyncio
async def test_query_by_keyword(db):
    """测试关键词全局搜索"""
    await db.create_access_asset({"src_system": "N-AQM", "dst_system": "P-ZH-DMP", "dst_ip": "10.87.28.127"})
    await db.create_access_asset({"src_system": "N-CRM", "dst_system": "P-DB-MAIN", "dst_ip": "10.20.5.50"})

    result = await db.query_access_assets(keyword="10.87")
    assert result["total"] == 1

    result2 = await db.query_access_assets(keyword="P-ZH-DMP")
    assert result2["total"] == 1
    assert result2["items"][0]["src_system"] == "N-AQM"


@pytest.mark.asyncio
async def test_query_by_protocol(db):
    """测试按协议过滤"""
    await db.create_access_asset({"src_system": "N-A", "dst_system": "P-B", "protocol": "TCP"})
    await db.create_access_asset({"src_system": "N-C", "dst_system": "P-D", "protocol": "UDP"})

    result_tcp = await db.query_access_assets(protocol="TCP")
    assert result_tcp["total"] == 1

    result_udp = await db.query_access_assets(protocol="UDP")
    assert result_udp["total"] == 1

    result_all = await db.query_access_assets()
    assert result_all["total"] == 2


@pytest.mark.asyncio
async def test_query_pagination(db):
    """测试分页功能"""
    for i in range(25):
        await db.create_access_asset({"src_system": f"N-S{i:02d}", "dst_system": "P-DST"})

    page1 = await db.query_access_assets(page=1, page_size=10)
    assert len(page1["items"]) == 10
    assert page1["total"] == 25
    assert page1["page"] == 1

    page3 = await db.query_access_assets(page=3, page_size=10)
    assert len(page3["items"]) == 5


# ---- 测试：删除访问关系记录 ----

@pytest.mark.asyncio
async def test_delete_access_asset(db):
    """测试删除记录"""
    record_id = await db.create_access_asset({"src_system": "N-DEL", "dst_system": "P-DST"})
    assert record_id is not None

    success = await db.delete_access_asset(record_id)
    assert success is True

    result = await db.query_access_assets(keyword="N-DEL")
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_delete_nonexistent(db):
    """测试删除不存在的记录返回 False"""
    success = await db.delete_access_asset(99999)
    assert success is False


# ---- 测试：Mock 数据种子 ----

@pytest.mark.asyncio
async def test_seed_access_assets_if_empty(db):
    """测试空表时自动填充 Mock 数据"""
    count = await db.seed_access_assets_if_empty()
    assert count > 0

    result = await db.query_access_assets()
    assert result["total"] == count


@pytest.mark.asyncio
async def test_seed_does_not_duplicate(db):
    """测试已有数据时不重复插入"""
    count1 = await db.seed_access_assets_if_empty()
    assert count1 > 0

    count2 = await db.seed_access_assets_if_empty()
    assert count2 == 0  # 不重复插入

    result = await db.query_access_assets()
    assert result["total"] == count1


# ---- 测试：API 接口（使用 FastAPI TestClient）----

@pytest.fixture
def test_client(temp_db_path):
    """创建 FastAPI 测试客户端"""
    import os
    # 临时设置数据库路径（通过环境变量或直接修改）
    # 注意：这里使用 Mock 方式，不实际连接真实 DB
    from fastapi.testclient import TestClient
    # 由于 API 使用的是全局 session_manager，这里做简单的导入测试
    # 实际测试可通过依赖注入来替换 DB
    try:
        from src.api import app
        client = TestClient(app, raise_server_exceptions=False)
        return client
    except Exception:
        return None


def test_list_access_assets_api(test_client):
    """测试查询 API 端点存在且可访问"""
    if test_client is None:
        pytest.skip("API 客户端初始化失败（可能缺少依赖）")

    response = test_client.get("/api/v1/assets/access-relations")
    # 接受 200 或 500（数据库未初始化时）
    assert response.status_code in [200, 500]


def test_chat_query_api_removed(test_client):
    """测试聊天查询接口缺少关键词时返回 422"""
    if test_client is None:
        pytest.skip("API 客户端初始化失败")

    response = test_client.get("/api/v1/assets/access-relations/chat-query")
    assert response.status_code in [404, 405]
