from pathlib import Path

from fastapi.testclient import TestClient

from src.api import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "static"


def read_static_file(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_root_serves_chat_homepage_templates():
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/")

    assert response.status_code == 200
    assert 'id="messages-container"' in response.text
    assert 'id="welcome-message-template"' in response.text
    assert 'id="quick-prompts-template"' in response.text
    assert 'id="quick-prompt-card-template"' in response.text


def test_app_js_defines_quick_prompt_config_and_copy():
    app_js = read_static_file("app.js")

    assert "const QUICK_PROMPTS = [" in app_js
    assert "category: '故障诊断'" in app_js
    assert "category: '访问关系'" in app_js
    assert "category: '权限提单'" in app_js
    assert "title: '访问关系如何开通提单'" in app_js
    assert "template: '请帮我分析为什么 10.0.1.10 到 10.0.2.20 的 80 端口不通。'" in app_js


def test_app_js_bootstraps_initial_state_and_new_chat_path():
    app_js = read_static_file("app.js")

    assert "const restored = await restoreSession();" in app_js
    assert "if (!restored) {" in app_js
    assert "renderInitialState();" in app_js
    assert "function renderQuickPrompts()" in app_js
    assert "function fillPromptTemplate(template)" in app_js
    assert "function startNewChat()" in app_js
    assert "hideQuickPrompts();" in app_js


def test_style_css_contains_quick_prompt_layout_rules():
    css = read_static_file("style.css")

    assert ".quick-prompts-section" in css
    assert ".quick-prompts-header" in css
    assert ".quick-prompt-group-title" in css
    assert ".quick-prompt-card-list" in css
    assert ".quick-prompt-card:hover" in css
    assert "grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));" in css
