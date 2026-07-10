<#
Run the after-state bridge probe.
This does not rank a final build. It checks whether fullpower outputs can start feeding apply_to_build_state.
#>
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$Repo = "$env:USERPROFILE\Downloads\survivor-optimizer"
$Raw = "https://raw.githubusercontent.com/HiHi-1111/survivor.io-optimizer/main"
Set-Location $Repo

function Ensure-Dir($p) {
  if (!(Test-Path $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null }
}

Ensure-Dir "tools\sio_training"
Ensure-Dir "data\sio_training\afterstate"

Invoke-WebRequest "$Raw/tools/sio_training/build_afterstate_probe.py?fresh=1" -OutFile "tools\sio_training\build_afterstate_probe.py" -UseBasicParsing

if (!(Test-Path "data\sio_training\fullpower\latest\fullpower_candidate_index.json")) {
  Write-Host "Missing fullpower_candidate_index.json. Run fullpower first or copy it into data\sio_training\fullpower\latest."
  exit 2
}

python tools\sio_training\build_afterstate_probe.py `
  --fullpower data\sio_training\fullpower\latest\fullpower_candidate_index.json `
  --normalized data\sio_training\normalized\sio_normalized_tables.json `
  --distribution data\sio_training\fullpower\latest\fullpower_distribution_index.csv `
  --out data\sio_training\afterstate

Get-Content data\sio_training\afterstate\afterstate_bridge_probe_report.md
Write-Host ""
Write-Host "SEND: data\sio_training\afterstate\afterstate_bridge_probe_report.md"
