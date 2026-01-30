@echo off
echo ============================================================
echo Starting netOpsAgent API Server...
echo ============================================================
echo.
echo API Documentation: http://localhost:8000/docs
echo Health Check:      http://localhost:8000/health
echo Web Interface:     http://localhost:8000/
echo.
echo Press Ctrl+C to stop the server
echo ============================================================
echo.

REM Change to project root directory
cd /d "%~dp0\.."

REM Start API server with streaming support
REM --timeout-keep-alive 300: Keep connection alive for 5 minutes
REM --reload: Enable auto-reload on file changes
.venv\Scripts\python.exe -u -m uvicorn src.api:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 300 --reload
