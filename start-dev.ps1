$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$backendPython = Join-Path $backendDir ".venv-windows\Scripts\python.exe"
$runDir = Join-Path $root ".codex-tmp\runtime"

if (-not (Test-Path $backendPython)) {
    throw "Windows virtual environment not found. Run .\setup.ps1 first."
}
if (-not (Get-Command "npm.cmd" -ErrorAction SilentlyContinue)) {
    throw "npm.cmd is unavailable. Install Node.js 18+ first."
}

New-Item -ItemType Directory -Force -Path $runDir | Out-Null

# Children inherit these values. CSV is the portable default on a clean clone.
$env:GRAPH_BACKEND = if ($env:GRAPH_BACKEND) { $env:GRAPH_BACKEND } else { "csv" }
$env:GRAPH_CONCEPTS_CSV = if ($env:GRAPH_CONCEPTS_CSV) { $env:GRAPH_CONCEPTS_CSV } else { Join-Path $root "data\seed\concepts.csv" }
$env:GRAPH_RELATIONS_CSV = if ($env:GRAPH_RELATIONS_CSV) { $env:GRAPH_RELATIONS_CSV } else { Join-Path $root "data\seed\relations.csv" }
$env:HF_HOME = if ($env:HF_HOME) { $env:HF_HOME } else { Join-Path $backendDir ".cache\huggingface" }
$env:LLM_ENABLED = if ($env:LLM_ENABLED) { $env:LLM_ENABLED } else { "false" }
$env:PYTHONPATH = $backendDir

Write-Host "[1/2] Starting backend in $($env:GRAPH_BACKEND) mode..." -ForegroundColor Cyan
$backendProcess = Start-Process -FilePath $backendPython `
    -ArgumentList "run.py" `
    -WorkingDirectory $backendDir `
    -RedirectStandardOutput (Join-Path $runDir "backend.log") `
    -RedirectStandardError (Join-Path $runDir "backend-error.log") `
    -PassThru
$backendProcess.Id | Set-Content -LiteralPath (Join-Path $runDir "backend.pid") -Encoding ASCII

Write-Host "[2/2] Starting frontend..." -ForegroundColor Cyan
$frontendProcess = Start-Process -FilePath "cmd.exe" `
    -ArgumentList @("/d", "/c", "npm run dev") `
    -WorkingDirectory $frontendDir `
    -RedirectStandardOutput (Join-Path $runDir "frontend.log") `
    -RedirectStandardError (Join-Path $runDir "frontend-error.log") `
    -PassThru
$frontendProcess.Id | Set-Content -LiteralPath (Join-Path $runDir "frontend.pid") -Encoding ASCII

Write-Host "Services started." -ForegroundColor Green
Write-Host "Frontend: http://127.0.0.1:5173"
Write-Host "API docs: http://127.0.0.1:8000/docs"
Write-Host "Graph backend: $($env:GRAPH_BACKEND)"
Write-Host "Logs: $runDir"
