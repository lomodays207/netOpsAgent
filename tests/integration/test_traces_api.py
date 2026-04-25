from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

import src.api as api


class FakeTraceDB:
    def __init__(self) -> None:
        self.list_calls: list[dict] = []
        self.detail_calls: list[str] = []
        self.session_calls: list[str] = []
        self.stats_calls = 0
        self.export_calls: list[dict] = []

    async def list_traces(self, **kwargs):
        self.list_calls.append(kwargs)
        return {
            "items": [
                {
                    "trace_id": "trace_20260424T120000Z_ab12cd34",
                    "session_id": "session-1",
                    "request_type": "diagnosis",
                    "status": "completed",
                    "created_at": "2026-04-24T20:00:00+08:00",
                }
            ],
            "total": 1,
            "page": kwargs["page"],
            "page_size": kwargs["page_size"],
        }

    async def get_trace_detail(self, trace_id: str):
        self.detail_calls.append(trace_id)
        if trace_id == "trace_20260424T120000Z_ab12cd35":
            return None
        return {
            "trace": {
                "trace_id": trace_id,
                "session_id": "session-1",
                "status": "completed",
            },
            "reasoning_steps": [{"step_number": 1, "reasoning_content": "check port"}],
            "tool_calls": [{"step_number": 1, "tool_name": "check_port_alive"}],
        }

    async def list_session_traces(self, session_id: str):
        self.session_calls.append(session_id)
        return [
            {
                "trace_id": "trace_20260424T120000Z_ab12cd34",
                "session_id": session_id,
                "status": "completed",
                "created_at": "2026-04-24T20:00:00+08:00",
            }
        ]

    async def get_trace_stats(self):
        self.stats_calls += 1
        return {
            "total": 2,
            "by_request_type": {"diagnosis": 1, "general_chat": 1},
            "by_status": {"completed": 1, "failed": 1},
            "average_total_time": 1.25,
            "last_24_hours": 2,
            "last_7_days": 2,
        }

    async def export_traces(self, **kwargs):
        self.export_calls.append(kwargs)
        return [
            {
                "trace_id": "trace_20260424T120000Z_ab12cd34",
                "session_id": "session-1",
                "request_type": "diagnosis",
                "status": "completed",
                "user_input": "firewall blocked",
                "created_at": "2026-04-24T20:00:00+08:00",
                "completed_at": "2026-04-24T20:00:01+08:00",
                "total_time": 1.0,
            }
        ]


class FakeSessionManager:
    def __init__(self) -> None:
        self.db = FakeTraceDB()

    async def initialize(self) -> None:
        return None

    async def start_cleanup(self) -> None:
        return None


@pytest.fixture
def fake_session_manager(monkeypatch: pytest.MonkeyPatch) -> FakeSessionManager:
    manager = FakeSessionManager()
    monkeypatch.setattr(api, "session_manager", manager)
    api._trace_rate_limiter.clear()
    return manager


@pytest.fixture
def client(fake_session_manager: FakeSessionManager) -> TestClient:
    return TestClient(api.app)


def test_list_traces_route_returns_filtered_page(client: TestClient, fake_session_manager: FakeSessionManager):
    response = client.get(
        "/api/v1/traces",
        params={
            "page": 1,
            "page_size": 20,
            "session_id": "session-1",
            "request_type": "diagnosis",
            "query": "firewall",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["trace_id"] == "trace_20260424T120000Z_ab12cd34"
    assert fake_session_manager.db.list_calls[0]["query"] == "firewall"


def test_get_trace_detail_route_validates_and_returns_detail(
    client: TestClient,
    fake_session_manager: FakeSessionManager,
):
    response = client.get("/api/v1/traces/trace_20260424T120000Z_ab12cd34")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trace"]["trace_id"] == "trace_20260424T120000Z_ab12cd34"
    assert payload["reasoning_steps"][0]["step_number"] == 1
    assert fake_session_manager.db.detail_calls == ["trace_20260424T120000Z_ab12cd34"]

    invalid = client.get("/api/v1/traces/not-a-trace-id")
    assert invalid.status_code == 400


def test_get_trace_detail_route_returns_404_when_missing(client: TestClient):
    response = client.get("/api/v1/traces/trace_20260424T120000Z_ab12cd35")

    assert response.status_code == 404


def test_list_session_traces_route_returns_trace_summaries(
    client: TestClient,
    fake_session_manager: FakeSessionManager,
):
    response = client.get("/api/v1/sessions/session-1/traces")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["session_id"] == "session-1"
    assert fake_session_manager.db.session_calls == ["session-1"]


def test_traces_route_returns_429_when_rate_limited(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(api, "check_trace_rate_limit", lambda client_id: False)

    response = client.get("/api/v1/traces")

    assert response.status_code == 429


def test_get_trace_stats_route_returns_aggregates(
    client: TestClient,
    fake_session_manager: FakeSessionManager,
):
    response = client.get("/api/v1/traces/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["by_request_type"]["diagnosis"] == 1
    assert payload["average_total_time"] == 1.25
    assert "runtime_metrics" in payload
    assert "query_count" in payload["runtime_metrics"]
    assert "sqlite_file_size_bytes" in payload["runtime_metrics"]
    assert fake_session_manager.db.stats_calls == 1


def test_export_traces_route_returns_csv_and_reuses_filters(
    client: TestClient,
    fake_session_manager: FakeSessionManager,
):
    response = client.post(
        "/api/v1/traces/export",
        json={
            "page": 1,
            "page_size": 200,
            "session_id": "session-1",
            "request_type": "diagnosis",
            "query": "firewall",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment;" in response.headers["content-disposition"]
    body = response.text
    assert "trace_id,session_id,request_type,status,user_input,created_at,completed_at,total_time" in body
    assert "trace_20260424T120000Z_ab12cd34,session-1,diagnosis,completed,firewall blocked" in body
    assert fake_session_manager.db.export_calls[0]["query"] == "firewall"
    assert fake_session_manager.db.export_calls[0]["page_size"] == 200


def test_export_traces_route_rejects_export_limit(client: TestClient):
    response = client.post(
        "/api/v1/traces/export",
        json={"page": 1, "page_size": 1001},
    )

    assert response.status_code == 400
