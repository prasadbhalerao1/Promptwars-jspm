# Hard restart of the whole local stack: kills every TRACE dev process (frontend, API —
# whether or not it holds a port), then starts everything fresh via dev-up.ps1.
#
# Use this when things are in a weird state: a stale server holding port 3000, a uvicorn
# reloader whose parent died, or the frontend
# serving from a deleted .next directory.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\dev-restart.ps1
#
#   -KeepDocker   leave Postgres/Qdrant/Redis running (default: they are left running)
#   -RestartDocker  also recreate the containers
#   -Clean        additionally delete apps\web\.next before restarting
#   -NoStart      only kill; don't start anything back up

param(
    [switch]$RestartDocker,
    [switch]$Clean,
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "== TRACE hard restart ==" -ForegroundColor Cyan

# --- 1. Kill by port ----------------------------------------------------------
# Covers the frontend (3000) and API (8000). Also 3001, because Next silently falls
# forward to the next free port when 3000 is taken, which strands a second dev server.
$ports = 3000, 3001, 8000
Write-Host "Freeing ports: $($ports -join ', ')" -ForegroundColor Yellow

foreach ($port in $ports) {
    $pids = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $pids) {
        $name = (Get-Process -Id $procId -ErrorAction SilentlyContinue).ProcessName
        # taskkill /T kills the process tree: uvicorn --reload and next dev both spawn a
        # child that survives if you only kill the parent, and then re-binds the port.
        taskkill /PID $procId /T /F *>$null
        if ($?) {
            Write-Host "  Killed $name (PID $procId) on port $port" -ForegroundColor Yellow
        } else {
            Write-Host "  Could not kill PID $procId on port $port" -ForegroundColor Red
        }
    }
}

$rootEscaped = [regex]::Escape($root)

# --- 2. Kill orphaned uvicorn / next processes from this repo ------------------
# Catches servers that crashed out of their port but left the process alive.
$killedOrphans = 0
Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'node.exe'" -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and
        ($_.CommandLine -match "services\.api\.main" -or $_.CommandLine -match "next(\s|-)dev") -and
        ($_.CommandLine -match $rootEscaped -or $_.ExecutablePath -match $rootEscaped)
    } |
    ForEach-Object {
        taskkill /PID $_.ProcessId /T /F *>$null
        if ($?) {
            Write-Host "  Killed orphan $($_.Name) (PID $($_.ProcessId))" -ForegroundColor Yellow
            $killedOrphans++
        }
    }
if ($killedOrphans -eq 0) { Write-Host "  No orphaned servers" -ForegroundColor DarkGray }

# Give Windows a moment to actually release the socket handles. Without this, a restart
# that follows immediately can still hit "port in use".
Start-Sleep -Seconds 2

# --- 3. Optional: Docker + build cache ----------------------------------------
if ($RestartDocker) {
    Write-Host "Restarting infra containers..." -ForegroundColor Yellow
    docker compose -f "$root\infra\docker-compose.yml" restart
}

if ($Clean) {
    $nextDir = Join-Path $root "apps\web\.next"
    if (Test-Path $nextDir) {
        Write-Host "Removing $nextDir ..." -ForegroundColor Yellow
        Remove-Item -LiteralPath $nextDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# --- 4. Verify the ports actually came free -----------------------------------
$stillBound = @()
foreach ($port in $ports) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        $stillBound += $port
    }
}
if ($stillBound.Count -gt 0) {
    Write-Host "WARNING: ports still bound: $($stillBound -join ', ')" -ForegroundColor Red
    Write-Host "  Find the owner with:  netstat -ano | findstr :$($stillBound[0])" -ForegroundColor Red
} else {
    Write-Host "All dev ports free." -ForegroundColor Green
}

# --- 5. Start back up ---------------------------------------------------------
if ($NoStart) {
    Write-Host ""
    Write-Host "Stopped everything (-NoStart). Run scripts\dev-up.ps1 when ready." -ForegroundColor Cyan
    exit 0
}

Write-Host ""
Write-Host "Starting fresh..." -ForegroundColor Green
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "dev-up.ps1")
