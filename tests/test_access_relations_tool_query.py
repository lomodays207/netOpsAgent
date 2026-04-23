import asyncio

import pytest

from src.db.database import SessionDatabase


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "tool_query.db")


@pytest.fixture
def db(db_path):
    database = SessionDatabase(db_path=db_path)
    asyncio.get_event_loop().run_until_complete(database.initialize())
    asyncio.get_event_loop().run_until_complete(database.seed_access_assets_if_empty())
    return database


def test_query_access_relations_outbound_filters_by_source_system(db):
    result = asyncio.get_event_loop().run_until_complete(
        db.query_access_relations(system_code="N-CRM", direction="outbound")
    )

    assert result["total"] == 2
    assert result["items"]
    assert all(item["src_system"] == "N-CRM" for item in result["items"])
    assert all(item["dst_system"] in {"N-AQM", "P-DB-MAIN"} for item in result["items"])


def test_query_access_relations_inbound_filters_by_destination_system(db):
    result = asyncio.get_event_loop().run_until_complete(
        db.query_access_relations(system_code="N-CRM", direction="inbound")
    )

    assert result["total"] == 1
    assert result["items"][0]["src_system"] == "N-OA"
    assert result["items"][0]["dst_system"] == "N-CRM"


def test_query_access_relations_deploy_unit_outbound(db):
    result = asyncio.get_event_loop().run_until_complete(
        db.query_access_relations(
            system_code="N-OA",
            deploy_unit="OAJS_WEB",
            direction="outbound",
        )
    )

    assert result["total"] == 2
    assert all(item["src_system"] == "N-OA" for item in result["items"])
    assert all(item["src_deploy_unit"] == "OAJS_WEB" for item in result["items"])


def test_query_access_relations_both_with_peer_system(db):
    result = asyncio.get_event_loop().run_until_complete(
        db.query_access_relations(
            system_code="N-CRM",
            peer_system_code="N-OA",
            direction="both",
        )
    )

    assert result["total"] == 1
    assert result["items"][0]["src_system"] == "N-OA"
    assert result["items"][0]["dst_system"] == "N-CRM"


def test_query_access_relations_resolves_chinese_name_with_generic_system_suffix(db):
    asyncio.get_event_loop().run_until_complete(
        db.create_access_asset(
            {
                "src_system": "N-NMS",
                "src_system_name": "\u667a\u80fd\u7f51\u7ba1",
                "src_deploy_unit": "NMS_AP",
                "src_ip": "10.1.1.1",
                "dst_system": "P-DST",
                "dst_deploy_unit": "DST_AP",
                "dst_ip": "10.2.2.2",
                "protocol": "TCP",
                "port": "443",
            }
        )
    )

    result = asyncio.get_event_loop().run_until_complete(
        db.query_access_relations(
            system_name="\u667a\u80fd\u7f51\u7ba1\u7cfb\u7edf",
            direction="outbound",
        )
    )

    assert result["total"] == 1
    assert result["items"][0]["src_system"] == "N-NMS"
