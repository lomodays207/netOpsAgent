from pathlib import Path

from fastapi.testclient import TestClient

from src.api import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "static"


def read_static_file(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_index_html_and_app_js_expose_trace_navigation():
    index_html = read_static_file("index.html")
    app_js = read_static_file("app.js")

    assert "/static/traces.html" in index_html
    assert "function addTraceCenterButton()" in app_js
    assert "window.location.href = '/static/traces.html'" in app_js


def test_traces_list_page_contains_filters_and_export_logic():
    traces_html = read_static_file("traces.html")
    traces_js = read_static_file("traces.js")

    assert 'id="trace-search-input"' in traces_html
    assert 'id="trace-request-type-filter"' in traces_html
    assert 'id="export-traces-btn"' in traces_html
    assert 'id="traces-list"' in traces_html
    assert 'id="trace-stats-grid"' in traces_html

    assert "function debounce(fn, wait)" in traces_js
    assert "function loadTraces()" in traces_js
    assert "function exportTracesCsv()" in traces_js
    assert "trace_detail.html?trace_id=" in traces_js


def test_trace_detail_and_history_pages_expose_trace_sections():
    trace_detail_html = read_static_file("trace_detail.html")
    trace_detail_js = read_static_file("trace_detail.js")
    history_html = read_static_file("history.html")
    history_js = read_static_file("history.js")

    assert 'id="trace-overview"' in trace_detail_html
    assert 'id="reasoning-steps-list"' in trace_detail_html
    assert 'id="tool-calls-list"' in trace_detail_html
    assert 'id="final-answer"' in trace_detail_html

    assert "function loadTraceDetail(traceId)" in trace_detail_js
    assert "无法加载追踪详情" in trace_detail_js

    assert 'id="session-traces-panel"' in history_html
    assert 'id="session-traces-toggle"' in history_html
    assert 'id="session-traces-list"' in history_html

    assert "function loadSessionTraces(sessionId)" in history_js
    assert "function toggleSessionTraces()" in history_js


def test_static_trace_pages_are_served():
    client = TestClient(app, raise_server_exceptions=False)

    traces_response = client.get("/static/traces.html")
    detail_response = client.get("/static/trace_detail.html")

    assert traces_response.status_code == 200
    assert detail_response.status_code == 200
