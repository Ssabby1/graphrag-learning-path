param(
    [string]$Neo4jPassword = "kg_learning_path_2026",
    [switch]$SkipNeo4jImport
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$neo4jHome = Join-Path $root "neo4j\neo4j-community-2025.12.1"
$neo4jBat = Join-Path $neo4jHome "bin\neo4j.bat"
$neo4jAdminBat = Join-Path $neo4jHome "bin\neo4j-admin.bat"
$backendVenv = Join-Path $backendDir ".venv"
$backendPython = Join-Path $backendVenv "Scripts\python.exe"

function Assert-Command {
    param(
        [string]$Name,
        [string]$Hint
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is not available. $Hint"
    }
}

function Invoke-Python {
    param([string[]]$Arguments)

    $py = Get-Command "py" -ErrorAction SilentlyContinue
    if ($py) {
        & $py.Source -3 @Arguments
        return
    }

    $python = Get-Command "python" -ErrorAction SilentlyContinue
    if ($python) {
        & $python.Source @Arguments
        return
    }

    throw "Python is not available. Install Python 3.11 or 3.12 and add it to PATH."
}

function Set-DotEnvValue {
    param(
        [string]$Path,
        [string]$Key,
        [string]$Value
    )

    $lines = @()
    if (Test-Path $Path) {
        $lines = Get-Content -LiteralPath $Path
    }

    $found = $false
    $updated = foreach ($line in $lines) {
        if ($line -match "^\s*$([regex]::Escape($Key))=") {
            $found = $true
            "$Key=$Value"
        } else {
            $line
        }
    }

    if (-not $found) {
        $updated += "$Key=$Value"
    }

    Set-Content -LiteralPath $Path -Value $updated -Encoding UTF8
}

function Get-DotEnvValue {
    param(
        [string]$Path,
        [string]$Key
    )

    if (-not (Test-Path $Path)) {
        return ""
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match "^\s*$([regex]::Escape($Key))=(.*)$") {
            return $Matches[1].Trim()
        }
    }

    return ""
}

function Wait-TcpPort {
    param(
        [string]$HostName,
        [int]$Port,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $client = New-Object System.Net.Sockets.TcpClient
        try {
            $async = $client.BeginConnect($HostName, $Port, $null, $null)
            if ($async.AsyncWaitHandle.WaitOne(1000)) {
                $client.EndConnect($async)
                return $true
            }
        } catch {
            Start-Sleep -Milliseconds 500
        } finally {
            $client.Close()
        }
    }

    return $false
}

Write-Host ""
Write-Host "[1/5] Checking required commands..." -ForegroundColor Cyan
Assert-Command -Name "npm.cmd" -Hint "Install Node.js 18+ from https://nodejs.org/."
Assert-Command -Name "java" -Hint "Install JDK 21+ and add java.exe to PATH."

if (-not (Test-Path $neo4jBat)) {
    throw "Neo4j launcher not found: $neo4jBat"
}
if (-not (Test-Path $neo4jAdminBat)) {
    throw "Neo4j admin launcher not found: $neo4jAdminBat"
}

Write-Host ""
Write-Host "[2/5] Preparing environment files..." -ForegroundColor Cyan
$backendEnv = Join-Path $backendDir ".env"
$backendEnvExample = Join-Path $backendDir ".env.example"
if (-not (Test-Path $backendEnv)) {
    Copy-Item -LiteralPath $backendEnvExample -Destination $backendEnv
}
$systemDbDir = Join-Path $neo4jHome "data\databases\system"
$existingNeo4jPassword = Get-DotEnvValue -Path $backendEnv -Key "NEO4J_PASSWORD"
$effectiveNeo4jPassword = $Neo4jPassword
if ((Test-Path $systemDbDir) -and $existingNeo4jPassword) {
    $effectiveNeo4jPassword = $existingNeo4jPassword
    Write-Host "Existing Neo4j data detected; keeping NEO4J_PASSWORD from backend\.env." -ForegroundColor Yellow
}
Set-DotEnvValue -Path $backendEnv -Key "NEO4J_URI" -Value "bolt://127.0.0.1:7687"
Set-DotEnvValue -Path $backendEnv -Key "NEO4J_USER" -Value "neo4j"
Set-DotEnvValue -Path $backendEnv -Key "NEO4J_PASSWORD" -Value $effectiveNeo4jPassword
Set-DotEnvValue -Path $backendEnv -Key "NEO4J_DATABASE" -Value "neo4j"
Set-DotEnvValue -Path $backendEnv -Key "LLM_ENABLED" -Value "false"

$frontendEnv = Join-Path $frontendDir ".env"
$frontendEnvExample = Join-Path $frontendDir ".env.example"
if (-not (Test-Path $frontendEnv)) {
    Copy-Item -LiteralPath $frontendEnvExample -Destination $frontendEnv
}

Write-Host ""
Write-Host "[3/5] Installing backend dependencies..." -ForegroundColor Cyan
if (-not (Test-Path $backendPython)) {
    Invoke-Python -Arguments @("-m", "venv", $backendVenv)
}
& $backendPython -m pip install --upgrade pip
& $backendPython -m pip install -r (Join-Path $backendDir "requirements.txt")

Write-Host ""
Write-Host "[4/5] Installing frontend dependencies..." -ForegroundColor Cyan
Push-Location $frontendDir
try {
    & npm.cmd install
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "[5/5] Preparing Neo4j data..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path (Join-Path $neo4jHome "data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $neo4jHome "logs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $neo4jHome "run") | Out-Null

if (-not (Test-Path $systemDbDir)) {
    & $neo4jAdminBat dbms set-initial-password $effectiveNeo4jPassword | Out-Host
} else {
    Write-Host "Existing Neo4j system database detected; keeping its current password."
}

if (-not $SkipNeo4jImport) {
    & $neo4jBat start | Out-Host
    if (-not (Wait-TcpPort -HostName "127.0.0.1" -Port 7687 -TimeoutSeconds 90)) {
        throw "Neo4j did not open Bolt port 7687 within 90 seconds."
    }

    Push-Location $root
    try {
        $env:NEO4J_URI = "bolt://127.0.0.1:7687"
        $env:NEO4J_USER = "neo4j"
        $env:NEO4J_PASSWORD = $effectiveNeo4jPassword
        $env:NEO4J_DATABASE = "neo4j"
        & $backendPython "scripts\import_data.py" --clear-target
    } finally {
        Pop-Location
    }

    & $neo4jBat stop | Out-Host
}

Write-Host ""
Write-Host "Setup finished." -ForegroundColor Green
Write-Host "Run .\start-dev.ps1 to start the system."
