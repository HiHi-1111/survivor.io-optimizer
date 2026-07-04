# First run helper for Survivor.io screenshot bot
# Run this from the repo root in PowerShell.

$ErrorActionPreference = "Stop"

Write-Host "== Survivor.io Screenshot Bot first run ==" -ForegroundColor Cyan

if (-not (Test-Path ".venv")) {
  Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
  python -m venv .venv
}

Write-Host "Activating virtual environment..." -ForegroundColor Yellow
. .\.venv\Scripts\Activate.ps1

Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

Write-Host "Installing screenshot bot requirements..." -ForegroundColor Yellow
pip install -r screenshot_bot\requirements.txt

New-Item -ItemType Directory -Force screenshots\input | Out-Null
New-Item -ItemType Directory -Force screenshots\output | Out-Null
New-Item -ItemType Directory -Force screenshots\debug | Out-Null
New-Item -ItemType Directory -Force knowledge\icons\equipment | Out-Null
New-Item -ItemType Directory -Force knowledge\icons\items | Out-Null

Write-Host "Done." -ForegroundColor Green
Write-Host "Put screenshots in screenshots\input, then run:" -ForegroundColor Cyan
Write-Host "python -m screenshot_bot.batch_run screenshots\input --type auto" -ForegroundColor White
