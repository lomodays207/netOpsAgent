# netOpsAgent API Server Startup Script
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Starting netOpsAgent API Server..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "API Documentation: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "Health Check:      http://localhost:8000/health" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Change to project root directory
Set-Location "$PSScriptRoot\.."

# Start API server
& .venv\Scripts\uvicorn.exe src.api:app --host 0.0.0.0 --port 8000 --reload
