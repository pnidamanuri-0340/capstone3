# FinLit installer for Windows (PowerShell 5.1+).
# Usage: powershell -ExecutionPolicy Bypass -File scripts\install.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Find-Python {
    foreach ($cand in @(@("py", "-3.12"), @("py", "-3.11"), @("py", "-3.13"), @("py", "-3"), @("python"), @("python3"))) {
        $exe = $cand[0]
        $args_ = @($cand | Select-Object -Skip 1)
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        try {
            $ver = & $exe @args_ -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        } catch { continue }
        if ($LASTEXITCODE -ne 0 -or -not $ver) { continue }
        $parts = $ver.Trim().Split(".")
        if ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 11) {
            return [pscustomobject]@{ Exe = $exe; Args = $args_; Version = $ver.Trim() }
        }
    }
    return $null
}

Write-Host "==> Looking for Python 3.11+" -ForegroundColor Cyan
$py = Find-Python
if (-not $py) {
    Write-Host "Python 3.11 or newer was not found. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH') and re-run." -ForegroundColor Red
    exit 1
}
$pyExe = $py.Exe; $pyArgs = @($py.Args)
Write-Host "    using: $pyExe $($pyArgs -join ' ') (Python $($py.Version))"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "==> Creating virtual environment (.venv)" -ForegroundColor Cyan
    & $pyExe @pyArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
}
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"

Write-Host "==> Installing FinLit and dependencies (first run takes a few minutes)" -ForegroundColor Cyan
& $venvPy -m pip install --upgrade pip --quiet
& $venvPy -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

if (-not (Test-Path ".env")) {
    Write-Host "==> Creating .env from .env.example" -ForegroundColor Cyan
    Copy-Item ".env.example" ".env"
    $oai = Read-Host "Paste your OPENAI_API_KEY (Enter to skip)"
    $goog = ""; $anth = ""
    if (-not $oai) { $goog = Read-Host "Or paste a free GOOGLE_API_KEY from aistudio.google.com/apikey (Enter to skip)" }
    if (-not $oai -and -not $goog) { $anth = Read-Host "Or paste an ANTHROPIC_API_KEY (Enter to add a key later)" }
    $av = Read-Host "Paste your ALPHA_VANTAGE_API_KEY (or press Enter to use sample market data)"
    $envText = Get-Content ".env" -Raw
    if ($oai) { $envText = $envText -replace "(?m)^OPENAI_API_KEY=.*$", "OPENAI_API_KEY=$oai" }
    if ($goog) { $envText = $envText -replace "(?m)^GOOGLE_API_KEY=.*$", "GOOGLE_API_KEY=$goog" }
    if ($anth) { $envText = $envText -replace "(?m)^ANTHROPIC_API_KEY=.*$", "ANTHROPIC_API_KEY=$anth" }
    if ($av) { $envText = $envText -replace "(?m)^ALPHA_VANTAGE_API_KEY=.*$", "ALPHA_VANTAGE_API_KEY=$av" }
    [IO.File]::WriteAllText((Join-Path $Root ".env"), $envText, (New-Object Text.UTF8Encoding $false))
} else {
    Write-Host "==> Keeping existing .env"
}

Write-Host "==> Building the knowledge base (downloads a ~80MB embedding model once)" -ForegroundColor Cyan
& (Join-Path $Root ".venv\Scripts\finlit.exe") ingest
if ($LASTEXITCODE -ne 0) { throw "ingest failed" }

Write-Host "==> Running smoke test" -ForegroundColor Cyan
& (Join-Path $Root ".venv\Scripts\finlit.exe") smoke

Write-Host ""
Write-Host "Install complete. Start the app with:  scripts\run.bat   (or scripts\run.ps1)" -ForegroundColor Green
