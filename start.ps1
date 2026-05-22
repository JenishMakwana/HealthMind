# ============================================================
#  start.ps1  —  Launch Backend (FastAPI) + Frontend (Vite)
# ============================================================

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Starting HealthMind Dev Environment" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ── Backend ─────────────────────────────────────────────────
Write-Host "[Backend]  Starting FastAPI server..." -ForegroundColor Green

if (-not (Test-Path "$ROOT\venv\Scripts\python.exe")) {
    throw "Virtual environment Python not found at $ROOT\venv\Scripts\python.exe"
}

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$ROOT'; Write-Host 'Backend running at http://127.0.0.1:8000' -ForegroundColor Green; & '$ROOT\\venv\\Scripts\\python.exe' -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --log-level info --access-log"
) -WindowStyle Normal -WorkingDirectory $ROOT

# ── Frontend ────────────────────────────────────────────────
Write-Host "[Frontend] Starting Vite dev server..." -ForegroundColor Yellow

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$ROOT\frontend'; if (-not (Test-Path 'node_modules')) { Write-Host 'Installing npm dependencies...' -ForegroundColor Yellow; npm install }; Write-Host 'Frontend starting...' -ForegroundColor Yellow; npx --no vite"
) -WindowStyle Normal

Write-Host ""
Write-Host "Both servers are launching in separate windows." -ForegroundColor Cyan
Write-Host "  Backend  -> http://localhost:8000"            -ForegroundColor Green
Write-Host "  Frontend -> http://localhost:5173"            -ForegroundColor Yellow
Write-Host ""
Write-Host "Close those windows (or press Ctrl+C in each) to stop the servers." -ForegroundColor Gray
