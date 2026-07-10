<#
Run the nested-choice recheck after the after-state probe exposed that Relic Core Chest
can create extra S-grade Excellent Choice Packs.

This does not rank a final build. It fixes/counts the legal choice space more correctly.
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
Ensure-Dir "data\sio_training\candidates"
Ensure-Dir "data\sio_training\fullpower\latest"
Ensure-Dir "data\sio_training\afterstate"

Invoke-WebRequest "$Raw/tools/sio_training/generate_sio_candidates.py?fresh=nested1" -OutFile "tools\sio_training\generate_sio_candidates.py" -UseBasicParsing
Invoke-WebRequest "$Raw/tools/sio_training/fullpower_candidate_index.py?fresh=nested1" -OutFile "tools\sio_training\fullpower_candidate_index.py" -UseBasicParsing
Invoke-WebRequest "$Raw/tools/sio_training/build_afterstate_probe.py?fresh=nested1" -OutFile "tools\sio_training\build_afterstate_probe.py" -UseBasicParsing

Write-Host "=== Regenerating candidates with nested S-grade pack counting ==="
python tools\sio_training\generate_sio_candidates.py `
  --state data\sio_training\dtlgrind_state_v2.json `
  --out data\sio_training\candidates

Write-Host ""
Write-Host "=== Running fullpower nested-choice validation ==="
if (-not $env:SIO_FULLPOWER_PASSES) { $env:SIO_FULLPOWER_PASSES = "3" }
python tools\sio_training\fullpower_candidate_index.py `
  --state data\sio_training\dtlgrind_state_v2.json `
  --candidate data\sio_training\candidates\dtlgrind_candidate_space.json `
  --out data\sio_training\fullpower\latest

Write-Host ""
Write-Host "=== Rebuilding after-state probe against corrected fullpower index ==="
python tools\sio_training\build_afterstate_probe.py `
  --fullpower data\sio_training\fullpower\latest\fullpower_candidate_index.json `
  --normalized data\sio_training\normalized\sio_normalized_tables.json `
  --distribution data\sio_training\fullpower\latest\fullpower_distribution_index.csv `
  --out data\sio_training\afterstate

Write-Host ""
Write-Host "=== Corrected fullpower report ==="
Get-Content data\sio_training\fullpower\latest\fullpower_candidate_index_report.md

Write-Host ""
Write-Host "SEND:"
Write-Host "data\sio_training\fullpower\latest\fullpower_candidate_index_report.md"
Write-Host "data\sio_training\afterstate\afterstate_bridge_probe_report.md"
