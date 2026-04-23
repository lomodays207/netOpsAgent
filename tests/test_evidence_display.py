"""
Tests for RAG evidence display functionality.

This test file verifies that:
1. HTML templates for evidence display are present
2. JavaScript functions for evidence handling are implemented
3. SSE event handler for evidence_sources is added
"""

from pathlib import Path

from fastapi.testclient import TestClient

from src.api import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "static"


def read_static_file(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_index_html_contains_evidence_templates():
    """Verify that index.html contains all required evidence display templates."""
    index_html = read_static_file("index.html")

    # Check for evidence sources panel template
    assert 'id="evidence-sources-template"' in index_html
    assert 'class="evidence-sources-panel"' in index_html
    assert 'class="evidence-header"' in index_html
    assert 'class="evidence-count"' in index_html
    assert 'class="evidence-list"' in index_html

    # Check for evidence card template
    assert 'id="evidence-card-template"' in index_html
    assert 'class="evidence-card"' in index_html
    assert 'class="evidence-filename"' in index_html
    assert 'class="evidence-score-badge"' in index_html
    assert 'class="evidence-score-fill"' in index_html
    assert 'class="evidence-preview"' in index_html

    # Check for document preview modal template
    assert 'id="document-preview-modal-template"' in index_html
    assert 'class="modal-overlay"' in index_html
    assert 'class="modal-content"' in index_html
    assert 'class="modal-close-btn"' in index_html
    assert 'class="modal-loading"' in index_html
    assert 'class="modal-content-text"' in index_html
    assert 'class="modal-error"' in index_html


def test_app_js_contains_evidence_rendering_functions():
    """Verify that app.js contains evidence rendering functions."""
    app_js = read_static_file("app.js")

    # Check for evidence source data model (JSDoc)
    assert "@typedef {Object} EvidenceSource" in app_js
    assert "evidenceSources" in app_js

    # Check for evidence rendering functions
    assert "function renderEvidenceSourcePanel(sources)" in app_js
    assert "function renderEvidenceCard(source)" in app_js
    assert "function showDocumentPreview(docId)" in app_js

    # Check for sorting by relevance score
    assert "sort((a, b) => b.relevance_score - a.relevance_score)" in app_js

    # Check for score-based color classes
    assert "score-high" in app_js
    assert "score-medium" in app_js
    assert "score-low" in app_js


def test_app_js_handles_evidence_sources_sse_event():
    """Verify that app.js handles evidence_sources SSE event."""
    app_js = read_static_file("app.js")

    # Check for evidence_sources case in handleEvent switch
    assert "case 'evidence_sources':" in app_js
    assert "handleEvidenceSourcesEvent(event);" in app_js

    # Check for handleEvidenceSourcesEvent function
    assert "function handleEvidenceSourcesEvent(event)" in app_js
    assert "renderEvidenceSourcePanel(event.sources)" in app_js
    assert "messageEl.evidenceSources = event.sources" in app_js


def test_app_js_implements_click_event_for_evidence_cards():
    """Verify that evidence cards have click event listeners."""
    app_js = read_static_file("app.js")

    # Check that click event is added to evidence cards
    assert "cardEl.addEventListener('click', () => {" in app_js
    assert "showDocumentPreview(source.id)" in app_js


def test_app_js_implements_error_handling_for_document_preview():
    """Verify that document preview has proper error handling."""
    app_js = read_static_file("app.js")

    # Check for error handling in showDocumentPreview
    assert "if (response.status === 404)" in app_js
    assert "throw new Error('文档不存在')" in app_js
    assert "if (response.status === 429)" in app_js
    assert "throw new Error('请求过于频繁，请稍后重试')" in app_js
    assert "throw new Error('无法加载文档内容')" in app_js
    assert "error.message || '请求超时，请重试'" in app_js


def test_app_js_implements_lazy_loading_for_documents():
    """Verify that documents are loaded lazily (only on click)."""
    app_js = read_static_file("app.js")

    # Check that fetch is inside showDocumentPreview (called on click)
    # and not in renderEvidenceCard (called on panel render)
    assert "async function showDocumentPreview(docId)" in app_js
    assert "await fetch(`/api/v1/knowledge/document/${docId}`)" in app_js


def test_app_js_implements_html_escaping_for_document_content():
    """Verify that document content is HTML-escaped to prevent XSS."""
    app_js = read_static_file("app.js")

    # Check that content is set using textContent (which escapes HTML)
    # instead of innerHTML
    assert "contentEl.textContent = doc.content" in app_js


def test_homepage_serves_with_evidence_templates():
    """Integration test: verify homepage serves with evidence templates."""
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/")

    assert response.status_code == 200
    assert 'id="evidence-sources-template"' in response.text
    assert 'id="evidence-card-template"' in response.text
    assert 'id="document-preview-modal-template"' in response.text
