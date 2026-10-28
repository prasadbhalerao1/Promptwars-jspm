# Starts everything needed for local development: Docker infra (Postgres, Qdrant, Redis),
# the FastAPI backend, and the Next.js frontend. All data services run locally in
# containers - there is no cloud dependency. Run from anywhere; paths are resolved
# relative to this script's location.
#
# First-time setup (see SETUP.md for the full walkthrough):
#   uv sync                                      # creates .venv from pyproject.toml
#   cd apps\web; npm install; cd ..\..
#   .venv\Scripts\python.exe -m alembic upgrade head    # once containers are up
#   .venv\Scripts\python.exe scripts\seed_db.py
#
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\dev-up.ps1 [-Prod]
#
#   -Prod  build the frontend and serve it with `next start`. Pages load instantly
#          instead of compiling on first visit, but code edits need a re-run.

param([switch]$Prod)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "== TRACE dev environment ==" -ForegroundColor Cyan

# --- 0. Kill anything already bound to the dev ports --------------------------
Write-Host "Freeing ports 3000 (web) and 8000 (api)..." -ForegroundColor Yellow
foreach ($port in 3000, 8000) {
    $pids = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $pids) {
        try {
            Stop-Process -Id $procId -Force -Confirm:$false -ErrorAction Stop
            Write-Host "  Killed PID $procId on port $port" -ForegroundColor Yellow
        } catch {
            # Stop-Process can fail on Windows for processes with child watchers (e.g. uvicorn --reload).
            # Fall back to taskkill /T to also terminate the process tree.
            taskkill /PID $procId /T /F *>$null
            if ($?) {
                Write-Host "  Killed PID $procId on port $port (via taskkill)" -ForegroundColor Yellow
            } else {
                Write-Host "  Could not kill PID $procId on port $port" -ForegroundColor Red
            }
        }
    }
}

# --- 1. Docker Desktop + infra containers ------------------------------
function Test-DockerRunning {
    try {
        docker info *>$null
        return $true
    } catch {
        return $false
    }
}

$dockerOk = Test-DockerRunning

if (-not $dockerOk) {
    Write-Host "Docker daemon not running, starting Docker Desktop..." -ForegroundColor Yellow
    $dockerExe = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerExe) {
        Start-Process $dockerExe
        Write-Host "Waiting for Docker daemon (up to 90s)..."
        $waited = 0
        while ($waited -lt 90) {
            Start-Sleep -Seconds 3
            $waited += 3
            if (Test-DockerRunning) { $dockerOk = $true; break }
        }
    } else {
        Write-Host "Docker Desktop.exe not found - start it manually, then re-run this script." -ForegroundColor Red
    }
}

if ($dockerOk) {
    Write-Host "Starting postgres, qdrant and redis containers..." -ForegroundColor Green
    docker compose -f "$root\infra\docker-compose.yml" up -d
} else {
    Write-Host "Skipping infra containers - Docker not available. The API cannot reach Postgres/Qdrant without them." -ForegroundColor Red
}

# --- 2. FastAPI backend --------------------------------------------------------
Write-Host "Starting FastAPI backend (new window)..." -ForegroundColor Green
# Root .venv, created by `uv sync` from pyproject.toml. Falls back to the older
# services/api/.venv so an environment predating the uv migration still starts.
$apiPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $apiPython)) {
    $apiPython = Join-Path $root "services\api\.venv\Scripts\python.exe"
}
if (-not (Test-Path $apiPython)) {
    Write-Host "No Python environment found. Run 'uv sync' in the repo root first." -ForegroundColor Red
    exit 1
}
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root'; & '$apiPython' -m uvicorn services.api.main:app --reload --port 8000"
)

# --- 3. Next.js frontend --------------------------------------------------------
$webCommand = if ($Prod) { 'npm run build; if ($?) { npm run start }' } else { 'npm run dev' }
Write-Host "Starting Next.js frontend (new window, $(if ($Prod) { 'production build' } else { 'dev' }))..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root\apps\web'; $webCommand"
)

Write-Host ""
Write-Host "== Started. See DEV_SERVERS.md for the full list of local URLs. ==" -ForegroundColor Cyan
Write-Host "  Frontend : http://localhost:3000"
Write-Host "  API      : http://localhost:8000  (docs at /docs)"
