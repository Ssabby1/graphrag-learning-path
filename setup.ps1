param(
    [switch]$Embeddings
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$backendVenv = Join-Path $backendDir ".venv-windows"
$backendPython = Join-Path $backendVenv "Scripts\python.exe"

function New-PythonVirtualEnvironment {
    param([string]$Path)

    $py = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if ($py) {
        & $py.Source -3 -m venv $Path
        return
    }

    $python = Get-Command "python.exe" -ErrorAction SilentlyContinue
    if ($python) {
        & $python.Source -m venv $Path
        return
    }

    throw "Python 3.11-3.13 is required and must be available on PATH."
}

if (-not (Get-Command "npm.cmd" -ErrorAction SilentlyContinue)) {
    throw "Node.js 18+ is required and npm.cmd must be available on PATH."
}

Write-Host "[1/4] Preparing environment files..." -ForegroundColor Cyan
foreach ($area in @("backend", "frontend")) {
    $envPath = Join-Path $root "$area\.env"
    if (-not (Test-Path $envPath)) {
        Copy-Item -LiteralPath (Join-Path $root "$area\.env.example") -Destination $envPath
    }
}

Write-Host "[2/4] Installing backend dependencies..." -ForegroundColor Cyan
if (-not (Test-Path $backendPython)) {
    New-PythonVirtualEnvironment -Path $backendVenv
}
& $backendPython -m pip install --upgrade pip
$requirements = if ($Embeddings) { "requirements-embeddings.txt" } else { "requirements.txt" }
& $backendPython -m pip install -r (Join-Path $backendDir $requirements)

if ($Embeddings) {
    Write-Host "[3/4] Downloading multilingual E5 (explicit -Embeddings mode)..." -ForegroundColor Cyan
    $env:HF_HOME = Join-Path $backendDir ".cache\huggingface"
    & $backendPython -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"
} else {
    Write-Host "[3/4] Lightweight mode selected; semantic model download skipped." -ForegroundColor Cyan
}

Write-Host "[4/4] Installing frontend dependencies..." -ForegroundColor Cyan
Push-Location $frontendDir
try {
    & npm.cmd ci
} finally {
    Pop-Location
}

Write-Host "Setup complete. Run .\start-dev.ps1." -ForegroundColor Green
if (-not $Embeddings) {
    Write-Host "The UI will label retrieval as degraded hashing. Run .\setup.ps1 -Embeddings for real multilingual E5." -ForegroundColor Yellow
}
