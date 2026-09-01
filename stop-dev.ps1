$ErrorActionPreference = "Continue"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runDir = Join-Path $root ".codex-tmp\runtime"

foreach ($name in @("backend", "frontend")) {
    $pidPath = Join-Path $runDir "$name.pid"
    if (-not (Test-Path $pidPath)) {
        Write-Host "No saved PID for $name."
        continue
    }

    $processId = Get-Content -LiteralPath $pidPath | Select-Object -First 1
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process) {
        & taskkill.exe /PID $processId /T /F | Out-Null
        Write-Host "Stopped $name (PID $processId)."
    } else {
        Write-Host "$name was not running (stale PID $processId)."
    }
    Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
}

Write-Host "Stop routine finished." -ForegroundColor Green
