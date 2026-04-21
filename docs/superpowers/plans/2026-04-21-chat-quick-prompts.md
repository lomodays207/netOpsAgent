# Chat Quick Prompts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-visit quick question cards to the default chat homepage so users can click a categorized prompt template into the input box without auto-sending.

**Architecture:** Replace the hardcoded welcome message in the live DOM with template-driven bootstrap rendering in `static/app.js`, so first load, restored sessions, and “新对话” all use the same UI path. Keep the feature front-end-only via a `QUICK_PROMPTS` constant, and use lightweight `pytest` regression tests to validate the homepage shell and static asset contracts because this repo does not have a browser-side JavaScript test harness.

**Tech Stack:** FastAPI static file serving, vanilla HTML/CSS/JavaScript, pytest, FastAPI `TestClient`

---

## File Structure

- `static/index.html`
  - Convert the initial hardcoded welcome message into reusable `<template>` blocks.
  - Add template anchors for the quick-prompts section and quick-prompt cards.
- `static/app.js`
  - Add prompt configuration data.
  - Bootstrap the initial screen only when no session is restored.
  - Render/hide/show quick prompts.
  - Rework “新对话” to rebuild the welcome screen instead of only clearing messages.
- `static/style.css`
  - Add layout and responsive styles for the quick-prompts section and cards.
- `tests/test_chat_homepage.py`
  - Add regression coverage for homepage template anchors, prompt configuration presence, and style selectors.

### Task 1: Add Homepage Shell Templates And Root Regression Test

**Files:**
- Create: `tests/test_chat_homepage.py`
- Modify: `static/index.html`
- Test: `tests/test_chat_homepage.py`

- [ ] **Step 1: Write the failing test for homepage template anchors**

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
pytest tests/test_chat_homepage.py::test_root_serves_chat_homepage_templates -v
```

Expected:

```text
FAIL ... assert 'id="welcome-message-template"' in response.text
```

- [ ] **Step 3: Replace the live welcome markup with reusable HTML templates**

Update the `messages-container` area in `static/index.html` to this structure:

```html
<div class="messages-container" id="messages-container"></div>
```

Add these templates before the existing `loading-template`:

```html
<template id="welcome-message-template">
    <div class="message assistant-message welcome-message">
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="message-text">
                你好！我是 AI 网络访问关系智能助手。请描述你遇到的网络故障，我会帮你分析根本原因。
                <br><br>
                例如：<code>10.0.1.10到10.0.2.20端口80不通</code>
            </div>
        </div>
    </div>
</template>

<template id="quick-prompts-template">
    <section class="quick-prompts-section" id="quick-prompts-section">
        <div class="quick-prompts-header">
            <h2 class="quick-prompts-title">猜你想问</h2>
            <p class="quick-prompts-subtitle">点击即可填入输入框，可继续补充具体 IP、端口、系统名称</p>
        </div>
        <div class="quick-prompt-groups"></div>
    </section>
</template>

<template id="quick-prompt-card-template">
    <button type="button" class="quick-prompt-card">
        <span class="quick-prompt-card-title"></span>
        <span class="quick-prompt-card-description"></span>
    </button>
</template>
```

- [ ] **Step 4: Run the test again to verify the homepage shell passes**

Run:

```powershell
pytest tests/test_chat_homepage.py::test_root_serves_chat_homepage_templates -v
```

Expected:

```text
PASSED tests/test_chat_homepage.py::test_root_serves_chat_homepage_templates
```

- [ ] **Step 5: Commit the shell scaffolding**

```powershell
git add tests/test_chat_homepage.py static/index.html
git commit -m "feat: add chat homepage prompt templates"
```

### Task 2: Add Prompt Configuration And Bootstrap Logic In `static/app.js`

**Files:**
- Modify: `tests/test_chat_homepage.py`
- Modify: `static/app.js`
- Test: `tests/test_chat_homepage.py`

- [ ] **Step 1: Add failing regression tests for prompt config and bootstrap helpers**

Append these tests to `tests/test_chat_homepage.py`:

```python
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
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```powershell
pytest tests/test_chat_homepage.py -k "app_js" -v
```

Expected:

```text
FAIL ... assert "const QUICK_PROMPTS = [" in app_js
FAIL ... assert "function startNewChat()" in app_js
```

- [ ] **Step 3: Implement the prompt config and the shared bootstrap path**

At the top of `static/app.js`, after the global state declarations, add the prompt config:

```js
const QUICK_PROMPTS = [
    {
        category: '故障诊断',
        items: [
            {
                title: '源到目标端口不通',
                description: '排查网络路径、防火墙、ACL 和服务监听',
                template: '请帮我分析为什么 10.0.1.10 到 10.0.2.20 的 80 端口不通。'
            },
            {
                title: '主机间网络不通',
                description: '检查连通性、路由和安全策略',
                template: '请帮我分析为什么 10.0.1.10 无法访问 10.0.2.20。'
            },
            {
                title: '服务监听异常',
                description: '确认端口监听、进程状态和主机防火墙',
                template: '请帮我检查 XX 主机上的 XX 服务是否正常监听目标端口。'
            }
        ]
    },
    {
        category: '访问关系',
        items: [
            {
                title: '查询系统访问关系清单',
                description: '查看某系统的上下游访问关系',
                template: '请查询 XX 系统的访问关系清单，包括源系统、目标系统、协议、端口和访问方向。'
            },
            {
                title: '查询主机访问关系',
                description: '按 IP 查看与其他资产的访问关系',
                template: '请查询 IP 为 10.0.1.10 的主机有哪些访问关系。'
            },
            {
                title: '查询两个系统是否已开通',
                description: '确认系统间是否已有访问放通记录',
                template: '请帮我查询 XX 系统到 XX 系统之间是否已经开通访问关系。'
            }
        ]
    },
    {
        category: '权限提单',
        items: [
            {
                title: '访问关系如何开通提单',
                description: '查看权限、流程和必填信息',
                template: '访问关系如何进行开通提单？需要哪些权限、审批节点和必填信息？'
            },
            {
                title: '提单需要准备什么',
                description: '提前准备源目地址、端口和用途说明',
                template: '开通访问关系前需要准备哪些信息，例如源 IP、目标 IP、端口、协议和用途说明？'
            },
            {
                title: '谁有权限提单',
                description: '确认申请角色和审批边界',
                template: '哪些角色有权限发起访问关系开通提单？审批边界是什么？'
            }
        ]
    }
];
```

Add these template lookups near the existing DOM element lookups:

```js
const welcomeMessageTemplate = document.getElementById('welcome-message-template');
const quickPromptsTemplate = document.getElementById('quick-prompts-template');
const quickPromptCardTemplate = document.getElementById('quick-prompt-card-template');
```

Change the `DOMContentLoaded` handler to wait for session restore before drawing the initial screen:

```js
document.addEventListener('DOMContentLoaded', async () => {
    console.log('🤖 AI 网络访问关系智能助手已加载');

    userInput.addEventListener('input', autoResizeTextarea);
    form.addEventListener('submit', handleSubmit);

    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            form.requestSubmit();
        }
    });

    addNewChatButton();
    stopBtn.addEventListener('click', stopGeneration);

    const restored = await restoreSession();
    if (!restored) {
        renderInitialState();
    }
});
```

Update `restoreSession()` so it returns a boolean and clears the live message container before replaying stored history:

```js
async function restoreSession() {
    const urlParams = new URLSearchParams(window.location.search);
    const urlSessionId = urlParams.get('session_id');

    if (urlSessionId) {
        console.log('📥 从 URL 加载会话:', urlSessionId);
        const restored = await loadSessionFromServer(urlSessionId);
        window.history.replaceState({}, document.title, '/');
        return restored;
    }

    const savedSessionId = localStorage.getItem('currentSessionId');
    const savedMessages = localStorage.getItem('chatMessages');

    if (!savedSessionId || !savedMessages) {
        return false;
    }

    currentSessionId = savedSessionId;
    messagesContainer.innerHTML = '';

    try {
        const messages = JSON.parse(savedMessages);
        if (!Array.isArray(messages) || messages.length === 0) {
            clearSession();
            return false;
        }

        messages.forEach((msg) => {
            if (msg.role === 'user') {
                addUserMessage(msg.content, false);
            } else if (msg.role === 'assistant') {
                addAssistantMessage(msg.content, false);
            }
        });

        addSystemMessage(`会话已恢复 (ID: ${currentSessionId.substring(0, 20)}...)`);
        return true;
    } catch (error) {
        console.error('恢复会话失败:', error);
        clearSession();
        return false;
    }
}
```

Update `loadSessionFromServer()` so it also clears the bootstrap screen and returns success/failure:

```js
async function loadSessionFromServer(sessionId) {
    try {
        const sessionsResponse = await fetch('/api/v1/sessions');
        const sessions = await sessionsResponse.json();
        const sessionInfo = sessions.find((session) => session.session_id === sessionId);

        const response = await fetch(`/api/v1/sessions/${sessionId}/messages`);
        if (!response.ok) {
            throw new Error('会话不存在或已过期');
        }

        const messages = await response.json();

        messagesContainer.innerHTML = '';
        currentSessionId = sessionId;
        saveSession();

        const isGeneralChat = sessionInfo &&
            (sessionInfo.task_description.includes('general_chat') ||
                !sessionInfo.task_description.includes('诊断'));

        localStorage.setItem('sessionType', isGeneralChat ? 'general' : 'diagnostic');

        messages.forEach((msg) => {
            if (msg.role === 'user') {
                addUserMessage(msg.content, false);
                return;
            }

            let metadata = null;
            if (msg.metadata) {
                try {
                    metadata = typeof msg.metadata === 'string' ? JSON.parse(msg.metadata) : msg.metadata;
                } catch (error) {
                    console.warn('Failed to parse metadata:', error);
                }
            }

            if (metadata && metadata.tool_call) {
                const assistantMsg = createAssistantMessage();
                const toolCard = createToolCallCardFromHistory(metadata.tool_call);
                appendToAssistantMessage(toolCard, assistantMsg);
            } else if (metadata && metadata.report) {
                const assistantMsg = createAssistantMessage();
                const reportEl = createFinalReport(metadata.report);
                appendToAssistantMessage(reportEl, assistantMsg);
            } else {
                addAssistantMessage(msg.content, false);
            }
        });

        addSystemMessage(`会话已加载，可以继续对话 (ID: ${sessionId.substring(0, 20)}...)`);
        return true;
    } catch (error) {
        console.error('加载会话失败:', error);
        addSystemMessage(`❌ 加载会话失败: ${error.message}`);
        return false;
    }
}
```

Add these new bootstrap helpers below `clearSession()`:

```js
function renderInitialState() {
    messagesContainer.innerHTML = '';
    messagesContainer.appendChild(createWelcomeMessage());
    showQuickPrompts();
    scrollToBottom();
}

function createWelcomeMessage() {
    return welcomeMessageTemplate.content.cloneNode(true).firstElementChild;
}

function renderQuickPrompts() {
    if (!Array.isArray(QUICK_PROMPTS) || QUICK_PROMPTS.length === 0) {
        return null;
    }

    const fragment = quickPromptsTemplate.content.cloneNode(true);
    const section = fragment.querySelector('#quick-prompts-section');
    const groupsContainer = fragment.querySelector('.quick-prompt-groups');

    QUICK_PROMPTS.forEach((group) => {
        const validItems = group.items.filter((item) => item.template);
        if (validItems.length === 0) {
            return;
        }

        const groupEl = document.createElement('section');
        groupEl.className = 'quick-prompt-group';

        const titleEl = document.createElement('h3');
        titleEl.className = 'quick-prompt-group-title';
        titleEl.textContent = group.category;

        const cardsEl = document.createElement('div');
        cardsEl.className = 'quick-prompt-card-list';

        validItems.forEach((item) => {
            const cardFragment = quickPromptCardTemplate.content.cloneNode(true);
            const card = cardFragment.querySelector('.quick-prompt-card');
            card.querySelector('.quick-prompt-card-title').textContent = item.title;
            card.querySelector('.quick-prompt-card-description').textContent = item.description;
            card.addEventListener('click', () => fillPromptTemplate(item.template));
            cardsEl.appendChild(card);
        });

        groupEl.appendChild(titleEl);
        groupEl.appendChild(cardsEl);
        groupsContainer.appendChild(groupEl);
    });

    return groupsContainer.childElementCount > 0 ? section : null;
}

function showQuickPrompts() {
    hideQuickPrompts();
    const section = renderQuickPrompts();
    if (section) {
        messagesContainer.appendChild(section);
    }
}

function hideQuickPrompts() {
    const section = document.getElementById('quick-prompts-section');
    if (section) {
        section.remove();
    }
}

function fillPromptTemplate(template) {
    userInput.value = template;
    autoResizeTextarea();
    userInput.focus();
}

function startNewChat() {
    clearSession();
    userInput.value = '';
    autoResizeTextarea();
    setInputEnabled(true);
    toggleStopButton(false);
    stopBtn.disabled = false;
    renderInitialState();
}
```

Replace the existing new-chat click handler with the shared reset path:

```js
newChatBtn.addEventListener('click', () => {
    if (confirm('确定要开始新对话吗？当前对话将被清除。')) {
        startNewChat();
    }
});
```

Update the form submit path so the first successful submit removes the quick prompts before the user message appears:

```js
async function handleSubmit(e) {
    e.preventDefault();

    const message = userInput.value.trim();
    if (!message || isWaitingForResponse) {
        return;
    }

    hideQuickPrompts();
    addUserMessage(message);
    userInput.value = '';
    autoResizeTextarea();

    setInputEnabled(false);
    toggleStopButton(true);
    showTypingIndicator();

    try {
        await submitMessage(message);
    } catch (error) {
        console.error('Failed to submit message:', error);
        addAssistantMessage(`Request failed: ${error.message}`);
    } finally {
        if (!isWaitingForResponse) {
            hideTypingIndicator();
            setInputEnabled(true);
            toggleStopButton(false);
        }
    }
}
```

- [ ] **Step 4: Run the homepage tests again to verify the JavaScript contract passes**

Run:

```powershell
pytest tests/test_chat_homepage.py -v
```

Expected:

```text
PASSED tests/test_chat_homepage.py::test_root_serves_chat_homepage_templates
PASSED tests/test_chat_homepage.py::test_app_js_defines_quick_prompt_config_and_copy
PASSED tests/test_chat_homepage.py::test_app_js_bootstraps_initial_state_and_new_chat_path
```

- [ ] **Step 5: Commit the JavaScript bootstrap work**

```powershell
git add tests/test_chat_homepage.py static/app.js
git commit -m "feat: add chat homepage quick prompt bootstrap"
```

### Task 3: Add Quick Prompt Layout Styles And Run Regression Verification

**Files:**
- Modify: `tests/test_chat_homepage.py`
- Modify: `static/style.css`
- Test: `tests/test_chat_homepage.py`
- Regression: `tests/unit/test_chat_stream.py`

- [ ] **Step 1: Add failing style regression tests**

Append this test to `tests/test_chat_homepage.py`:

```python
def test_style_css_contains_quick_prompt_layout_rules():
    css = read_static_file("style.css")

    assert ".quick-prompts-section" in css
    assert ".quick-prompts-header" in css
    assert ".quick-prompt-group-title" in css
    assert ".quick-prompt-card-list" in css
    assert ".quick-prompt-card:hover" in css
    assert "grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));" in css
```

- [ ] **Step 2: Run the style test to verify it fails**

Run:

```powershell
pytest tests/test_chat_homepage.py::test_style_css_contains_quick_prompt_layout_rules -v
```

Expected:

```text
FAIL ... assert ".quick-prompts-section" in css
```

- [ ] **Step 3: Add the quick prompt section styles**

Insert this block in `static/style.css` after the assistant-message styles and before the typing-indicator styles:

```css
.welcome-message .message-text {
    max-width: min(85%, 760px);
}

.quick-prompts-section {
    margin: 0 0 1.5rem 3.25rem;
    padding: 1rem 1.25rem;
    border: 1px solid #dbeafe;
    border-radius: 1rem;
    background: linear-gradient(180deg, #f8fbff 0%, #eef4ff 100%);
    box-shadow: 0 8px 24px rgba(37, 99, 235, 0.08);
}

.quick-prompts-header {
    margin-bottom: 1rem;
}

.quick-prompts-title {
    font-size: 1rem;
    font-weight: 700;
    color: #1d4ed8;
}

.quick-prompts-subtitle {
    margin-top: 0.25rem;
    font-size: 0.85rem;
    color: var(--text-secondary);
}

.quick-prompt-groups {
    display: grid;
    gap: 1rem;
}

.quick-prompt-group-title {
    margin-bottom: 0.75rem;
    font-size: 0.92rem;
    font-weight: 700;
    color: #334155;
}

.quick-prompt-card-list {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0.75rem;
}

.quick-prompt-card {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    width: 100%;
    padding: 0.9rem 1rem;
    border: 1px solid #cbd5e1;
    border-radius: 0.9rem;
    background: white;
    color: var(--text-primary);
    text-align: left;
    cursor: pointer;
    transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.quick-prompt-card:hover {
    transform: translateY(-2px);
    border-color: #60a5fa;
    box-shadow: 0 10px 20px rgba(37, 99, 235, 0.12);
}

.quick-prompt-card:focus-visible {
    outline: 2px solid #2563eb;
    outline-offset: 2px;
}

.quick-prompt-card-title {
    font-size: 0.92rem;
    font-weight: 700;
    color: #0f172a;
}

.quick-prompt-card-description {
    margin-top: 0.35rem;
    font-size: 0.82rem;
    line-height: 1.5;
    color: #475569;
}
```

Extend the existing mobile media-query block to keep the section aligned on small screens:

```css
@media (max-width: 768px) {
    .chat-header h1 {
        font-size: 1.5rem;
    }

    .messages-container {
        padding: 1rem;
    }

    .message-text {
        max-width: 90%;
    }

    .quick-prompts-section {
        margin-left: 0;
        padding: 1rem;
    }

    .quick-prompt-card-list {
        grid-template-columns: 1fr;
    }

    .input-options {
        flex-direction: column;
        gap: 0.5rem;
    }
}
```

- [ ] **Step 4: Run the full homepage regression tests and an existing chat regression test**

Run:

```powershell
pytest tests/test_chat_homepage.py tests/unit/test_chat_stream.py -v
```

Expected:

```text
PASSED tests/test_chat_homepage.py::test_root_serves_chat_homepage_templates
PASSED tests/test_chat_homepage.py::test_app_js_defines_quick_prompt_config_and_copy
PASSED tests/test_chat_homepage.py::test_app_js_bootstraps_initial_state_and_new_chat_path
PASSED tests/test_chat_homepage.py::test_style_css_contains_quick_prompt_layout_rules
PASSED tests/unit/test_chat_stream.py::test_chat_stream_clarify_uses_lightweight_session
PASSED tests/unit/test_chat_stream.py::test_general_chat_stream_creates_llm_for_lightweight_session
PASSED tests/unit/test_chat_stream.py::test_general_chat_non_stream_creates_llm_for_lightweight_session
```

- [ ] **Step 5: Commit the styling and regression coverage**

```powershell
git add tests/test_chat_homepage.py static/style.css
git commit -m "feat: style chat homepage quick prompts"
```

## Manual Smoke Test

After the three tasks above are complete, run the browser smoke test once:

1. Start the app:

```powershell
.venv\Scripts\python -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

2. Open `http://127.0.0.1:8000/`
3. Confirm the first screen shows:
   - The welcome assistant message
   - The `猜你想问` section
   - Three groups: `故障诊断` / `访问关系` / `权限提单`
4. Click `访问关系如何开通提单`
   - Expected: the full template appears in the textarea
   - Expected: nothing is sent automatically
5. Send the edited message
   - Expected: the quick prompts disappear before the user bubble is added
6. Refresh the page with the restored session
   - Expected: the quick prompts do not reappear
7. Click `新对话`
   - Expected: history clears, welcome message returns, quick prompts return

## Self-Review Checklist

- Spec coverage:
  - Homepage display timing is covered in Task 2 bootstrap changes.
  - Click-to-fill without auto-send is covered in Task 2 helper functions.
  - New chat re-bootstrap is covered in Task 2 `startNewChat()`.
  - Responsive layout is covered in Task 3 CSS work.
  - Regression verification is covered by `tests/test_chat_homepage.py` plus `tests/unit/test_chat_stream.py`.
- Placeholder scan:
  - No placeholder markers remain in any task body.
  - Every task contains exact file paths, code, commands, and expected results.
- Type consistency:
  - Template IDs are consistent across `static/index.html` and `static/app.js`.
  - Class names used in tests match the CSS selectors named in Task 3.
