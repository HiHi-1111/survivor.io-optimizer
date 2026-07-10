$ErrorActionPreference = "Continue"
$Start = Get-Date
$Repo = (Get-Location).Path
$Zip = "data\sio_training\archive\sio_tools.exp0.dev.zip"
$Out = "data\sio_training\normalized"

Write-Host "=== SIO NORMALIZER LIVE RUN ===" -ForegroundColor Cyan
Write-Host "Repo root: $Repo"
Write-Host "Zip path: $Zip"
Write-Host "Output: $Out"

if (!(Test-Path $Zip)) {
  Write-Host "ERROR: Missing $Zip" -ForegroundColor Red
  Write-Host "Put sio_tools.exp0.dev.zip in data\sio_training\archive first."
  exit 1
}

$Node = Get-Command node -ErrorAction SilentlyContinue
if ($Node) {
  Write-Host "Node found: $($Node.Source). Exact webpack export mode will be used." -ForegroundColor Green
} else {
  Write-Host "Node.js not found. Continuing with Python-only static fallback mode." -ForegroundColor Yellow
  Write-Host "This is OK for now. It extracts modules, field hints, and parser targets without installing Node."
}

New-Item -ItemType Directory -Force $Out | Out-Null
$Log = Join-Path $Out "powershell_normalize_run.log"
Write-Host "Running normalizer. This should usually take under 1 minute." -ForegroundColor Yellow
Write-Host "It writes normalized tables and a normalizer unknowns report."

python tools\sio_training\normalize_sio_bundle.py $Zip --out $Out 2>&1 | Tee-Object -FilePath $Log

Write-Host ""
Write-Host "Finished. Check these files:" -ForegroundColor Cyan
Write-Host "data\sio_training\normalized\sio_normalized_tables.json"
Write-Host "data\sio_training\normalized\normalizer_unknowns_report.md" -ForegroundColor Yellow
Write-Host "data\sio_training\normalized\normalizer_run.log"
Write-Host "data\sio_training\normalized\powershell_normalize_run.log"

$Elapsed = (Get-Date) - $Start
Write-Host "Elapsed: $([math]::Round($Elapsed.TotalSeconds, 1)) seconds"
