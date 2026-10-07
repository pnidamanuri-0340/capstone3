# Launch the FinLit Streamlit app. Usage: powershell -ExecutionPolicy Bypass -File scripts\run.ps1 [-Port 8501]
param([int]$Port = 8501)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$finlit = Join-Path $Root ".venv\Scripts\finlit.exe"
if (-not (Test-Path $finlit)) {
    Write-Host "FinLit is not installed yet. Run scripts\install.bat first." -ForegroundColor Red
    exit 1
}
Write-Host "Starting FinLit on http://localhost:$Port  (press Ctrl+C to stop)" -ForegroundColor Green
& $finlit ui --port $Port
