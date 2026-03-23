$ErrorActionPreference = "SilentlyContinue"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$neo4jBin = Join-Path $root "neo4j\neo4j-community-2025.12.1\bin"
$neo4jBat = Join-Path $neo4jBin "neo4j.bat"
$portsToStop = @(8000, 5173)

function Stop-ProcessesByPort {
    param(
        [int]$Port
    )

    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $connections) {
        Write-Host "No listening process found on port $Port."
        return
    }

    $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($pid in $pids) {
        if ($pid -and $pid -ne 0) {
            try {
                $process = Get-Process -Id $pid -ErrorAction Stop
                Stop-Process -Id $pid -Force -ErrorAction Stop
                Write-Host "Stopped $($process.ProcessName) (PID $pid) on port $Port."
            } catch {
                Write-Host "Failed to stop PID $pid on port $Port."
            }
        }
    }
}

Write-Host ""
Write-Host "[1/2] Stopping backend/frontend dev processes..." -ForegroundColor Cyan
foreach ($port in $portsToStop) {
    Stop-ProcessesByPort -Port $port
}

Write-Host ""
Write-Host "[2/2] Stopping Neo4j..." -ForegroundColor Cyan
if (Test-Path $neo4jBat) {
    & $neo4jBat stop | Out-Host
} else {
    Write-Host "Neo4j launcher not found: $neo4jBat"
}

Write-Host ""
Write-Host "Stop routine finished." -ForegroundColor Green
