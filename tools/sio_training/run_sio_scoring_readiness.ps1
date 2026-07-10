$ErrorActionPreference = "Continue"
$Start = Get-Date
$Repo = (Get-Location).Path

Write-Host "=== SIO SCORING READINESS CHECK ===" -ForegroundColor Cyan
Write-Host "Repo root: $Repo"

New-Item -ItemType Directory -Force tools\sio_training | Out-Null
New-Item -ItemType Directory -Force data\sio_training\scoring | Out-Null

$Raw = "https://raw.githubusercontent.com/HiHi-1111/survivor.io-optimizer/main/tools/sio_training/check_sio_scoring_readiness.py?fresh=1"
Invoke-WebRequest $Raw -OutFile "tools\sio_training\check_sio_scoring_readiness.py"

$Log = "data\sio_training\scoring\scoring_readiness_run.log"
python tools\sio_training\check_sio_scoring_readiness.py 2>&1 | Tee-Object -FilePath $Log

Write-Host ""
Write-Host "Finished. Files:" -ForegroundColor Cyan
Write-Host "data\sio_training\scoring\scoring_readiness_report.md" -ForegroundColor Yellow
Write-Host "data\sio_training\scoring\scoring_readiness.json"
Write-Host "data\sio_training\scoring\scoring_readiness_run.log"

$Elapsed = (Get-Date) - $Start
Write-Host "Elapsed: $([math]::Round($Elapsed.TotalSeconds, 1)) seconds" -ForegroundColor Green
