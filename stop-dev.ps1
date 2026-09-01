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
        $taskkillOutput = & taskkill.exe /PID $processId /T /F 2>&1
        if ($LASTEXITCODE -eq 0 -or -not (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
            Write-Host "Stopped $name (PID $processId)."
        } else {
            Write-Warning "Could not stop $name (PID $processId): $($taskkillOutput -join ' ')"
        }
    } else {
        Write-Host "$name was not running (stale PID $processId)."
    }
    Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
}

Write-Host "Stop routine finished." -ForegroundColor Green
$global:LASTEXITCODE = 0
