# Tracing Guide

## Overview

LLM request tracing records each diagnosis run and general chat run into the existing `runtime/sessions.db`.

Tracing stores:

- trace metadata: `trace_id`, `session_id`, request type, status, timestamps, final answer, error
- reasoning steps for diagnosis flows
- tool call arguments, results, status, and timing

## Configuration

Tracing is controlled by environment variables in `.env`:

```env
ENABLE_TRACING=false
TRACE_RETENTION_DAYS=30
TRACE_QUERY_RATE_LIMIT_PER_MINUTE=30
TRACE_REASONING_MAX_BYTES=5120
TRACE_TOOL_RESULT_MAX_BYTES=10240
```

Notes:

- `ENABLE_TRACING=false` keeps the main diagnosis/chat flow unchanged.
- reasoning and tool payloads are truncated before storage.
- sensitive keys such as `token`, `password`, `secret`, and `authorization` are masked before persistence.

## API

Available tracing endpoints:

- `GET /api/v1/traces`
- `GET /api/v1/traces/{trace_id}`
- `GET /api/v1/traces/stats`
- `POST /api/v1/traces/export`
- `GET /api/v1/sessions/{session_id}/traces`

`GET /api/v1/traces/stats` also includes `runtime_metrics`, which contains:

- write success/failure counters
- query counters and average query latency
- cleanup counters
- SQLite file size in bytes when available

## Static Pages

Frontend entry points:

- `/static/traces.html`
- `/static/trace_detail.html`
- `/static/history.html`

The homepage also links to the tracing list page.

## Cleanup

When tracing is enabled, expired records are deleted by the existing session manager startup chain.

- retention window: `TRACE_RETENTION_DAYS`
- cleanup schedule: every day at 02:00 local time

## Verification

Useful commands:

```bash
python -m pytest tests/unit/tracing/test_trace_utils.py tests/unit/tracing/test_trace_recorder.py tests/unit/db/test_trace_storage.py tests/unit/agent/test_llm_agent_simple.py tests/test_general_chat_agent.py tests/integration/test_traces_api.py tests/test_trace_pages.py tests/e2e/test_traces_e2e.py -q
```
