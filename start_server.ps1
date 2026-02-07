<#
start_server.ps1

Aktiviert das virtuelle Environment (venv), setzt die Umgebungsvariable PYTHON
damit der uvicorn --reload subprocess die richtige Python-Exe verwendet, lädt
optional Variablen aus einer `.env`-Datei und startet `uvicorn` aus dem venv.

Usage (PowerShell):
  .\start_server.ps1
  .\start_server.ps1 -VenvFolder env -Port 8000

Parameter:
  -VenvFolder: Name des venv-Ordners (standard: "venv"). Falls nicht vorhanden,
              versucht es mit "env".
  -Port: Port für uvicorn (Standard: 8000)
  -AppModule: Modul:App (Standard: "main:app")
  -SetPythonEnv: Setzt `$env:PYTHON` auf die venv-Python (Standard: true)
#>

param(
    [string]$VenvFolder = "venv",
    [int]$Port = 8000,
    [string]$AppModule = "main:app",
    [switch]$SetPythonEnv = $true
)

try {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    Set-Location $scriptDir
} catch {
    Write-Error "Konnte Arbeitsverzeichnis nicht setzen: $_"
}

if (-not (Test-Path (Join-Path $scriptDir $VenvFolder))) {
    if (Test-Path (Join-Path $scriptDir 'env')) {
        $VenvFolder = 'env'
    } else {
        Write-Error "Venv-Ordner '$VenvFolder' nicht gefunden. Bitte erstelle ein venv oder übergib -VenvFolder.";
        exit 1
    }
}

$venvPath = Join-Path $scriptDir $VenvFolder
$activate = Join-Path $venvPath 'Scripts\Activate.ps1'
$pythonExe = Join-Path $venvPath 'Scripts\python.exe'
$uvicornExe = Join-Path $venvPath 'Scripts\uvicorn.exe'

if ($SetPythonEnv) {
    $resolved = Resolve-Path $pythonExe -ErrorAction SilentlyContinue
    if ($resolved) { $env:PYTHON = $resolved.Path }
}

# Load .env simple parser (KEY=VALUE) if exists
$envFile = Join-Path $scriptDir '.env'
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^[\s#]') { return }
        if ($_ -match '^[\s]*$') { return }
        $parts = $_ -split '=',2
        if ($parts.Count -eq 2) {
            $k = $parts[0].Trim()
            $v = $parts[1].Trim().Trim('"')
            if ($k) { ${env:$k} = $v }
        }
    }
}

# Allow running the Activate.ps1 in this session
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

# FIX: Do NOT use the Activate.ps1 from the venv if it was copied, as it contains hardcoded paths.
# Instead, we explicitly use the python executable from the current venv folder.
$pythonExe = Join-Path $venvPath 'Scripts\python.exe'
$uvicornExe = Join-Path $venvPath 'Scripts\uvicorn.exe'

# Define default values for missing variables
$reload = "--reload"
$hostAddr = "0.0.0.0"

Write-Host "Starte Server mit Python: $pythonExe"

# Ensure we are using the local python to run uvicorn module
& $pythonExe -m uvicorn $AppModule $reload --host $hostAddr --port $Port
