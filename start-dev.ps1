$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$neo4jBin = Join-Path $root "neo4j\neo4j-community-2025.12.1\bin"
$neo4jBat = Join-Path $neo4jBin "neo4j.bat"
$backendDir = Join-Path $root "backend"
$backendPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$backendRun = Join-Path $backendDir "run.py"
$frontendDir = Join-Path $root "frontend"
$npmCmd = "npm.cmd"

function Assert-Exists {
    param(
        [string]$Path,
        [string]$Label
    )

    if (-not (Test-Path $Path)) {
        throw "$Label not found: $Path"
    }
}

Assert-Exists -Path $neo4jBat -Label "Neo4j launcher"
Assert-Exists -Path $backendPython -Label "Backend Python"
Assert-Exists -Path $backendRun -Label "Backend entry"
Assert-Exists -Path $frontendDir -Label "Frontend directory"

Write-Host ""
Write-Host "[1/3] Starting Neo4j..." -ForegroundColor Cyan
& $neo4jBat start | Out-Host
& $neo4jBat status | Out-Host

Write-Host ""
Write-Host "[2/3] Starting backend..." -ForegroundColor Cyan
$backendCommand = @(
    '$env:PYTHONPATH=''.''',
    '& ''.\.venv\Scripts\python.exe'' ''run.py'''
) -join '; '
Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$backendDir'; $backendCommand"
) | Out-Null

Write-Host ""
Write-Host "[3/3] Starting frontend..." -ForegroundColor Cyan
$frontendCommand = @(
    'if (-not (Test-Path ''.\node_modules'')) { & npm.cmd install }',
    '& npm.cmd run dev'
) -join '; '
Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$frontendDir'; $frontendCommand"
) | Out-Null

Write-Host ""
Write-Host "All services have been triggered." -ForegroundColor Green
Write-Host "Frontend: http://127.0.0.1:5173"
Write-Host "Backend docs: http://127.0.0.1:8000/docs"
Write-Host ""
Write-Host "If you need to stop Neo4j later:"
Write-Host "  cd '$neo4jBin'"
Write-Host "  .\neo4j.bat stop"
