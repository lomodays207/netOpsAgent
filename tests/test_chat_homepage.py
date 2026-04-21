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
