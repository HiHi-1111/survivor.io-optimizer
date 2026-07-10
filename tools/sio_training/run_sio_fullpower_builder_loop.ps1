<#
Full-power Survivor.io optimizer data run.

This is intentionally heavy. It refreshes scripts, reruns the validated pipeline,
then enumerates the full choice-output space multiple times using CPU workers.
It still does NOT rank a final build until apply_to_build_state + sIO damage scorer exist.
#>

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"
$Repo = "$env:USERPROFILE\Downloads\survivor-optimizer"
$Raw = "https://raw.githubusercontent.com/HiHi-1111/survivor.io-optimizer/main"

function Log($msg) {
  $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Write-Host "[$ts] $msg"
}

function Ensure-Dir($p) {
  if (!(Test-Path $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null }
}

function Download-File($url, $out) {
  try {
    Ensure-Dir (Split-Path $out -Parent)
    Invoke-WebRequest $url -OutFile $out -UseBasicParsing
    return $true
  } catch {
    Write-Host "DOWNLOAD FAILED: $url"
    Write-Host $_
    return $false
  }
}

function Run-Step($name, $scriptBlock) {
  Log "START $name"
  try {
    & $scriptBlock
    $code = $LASTEXITCODE
    if ($null -eq $code) { $code = 0 }
    if ($code -ne 0) { Log "WARN $name exited with code $code" }
  } catch {
    Log "ERROR in $name"
    Write-Host $_
  }
  Log "END $name"
}

Set-Location $Repo
Ensure-Dir "data\sio_training\fullpower\latest"
$Transcript = "data\sio_training\fullpower\latest\fullpower_builder_loop.log"
try { Stop-Transcript | Out-Null } catch {}
Start-Transcript -Path $Transcript -Force | Out-Null

Log "Full-power builder loop started"
Log "Repo root: $Repo"

Run-Step "refresh scripts" {
  Download-File "$Raw/tools/sio_training/extract_sio_bundle.py?fresh=fp1" "tools\sio_training\extract_sio_bundle.py" | Out-Null
  Download-File "$Raw/tools/sio_training/normalize_sio_bundle.py?fresh=fp1" "tools\sio_training\normalize_sio_bundle.py" | Out-Null
  Download-File "$Raw/tools/sio_training/generate_sio_candidates.py?fresh=fp1" "tools\sio_training\generate_sio_candidates.py" | Out-Null
  Download-File "$Raw/tools/sio_training/check_sio_scoring_readiness.py?fresh=fp1" "tools\sio_training\check_sio_scoring_readiness.py" | Out-Null
  Download-File "$Raw/tools/sio_training/fullpower_candidate_index.py?fresh=fp1" "tools\sio_training\fullpower_candidate_index.py" | Out-Null
  Download-File "$Raw/tools/sio_training/run_sio_deep_autopilot.ps1?fresh=fp1" "tools\sio_training\run_sio_deep_autopilot.ps1" | Out-Null
  Download-File "$Raw/tools/sio_training/run_sio_normalize.ps1?fresh=fp1" "tools\sio_training\run_sio_normalize.ps1" | Out-Null
  Download-File "$Raw/tools/sio_training/run_sio_candidates.ps1?fresh=fp1" "tools\sio_training\run_sio_candidates.ps1" | Out-Null
  Download-File "$Raw/data/sio_training/dtlgrind_state_v2.json?fresh=fp1" "data\sio_training\dtlgrind_state_v2.json" | Out-Null
}

Run-Step "deep autopilot warmup" {
  powershell -ExecutionPolicy Bypass -File "tools\sio_training\run_sio_deep_autopilot.ps1"
}

Run-Step "resource sanity check before fullpower" {
  python - <<'PY'
import json, pathlib, sys
p=pathlib.Path('data/sio_training/candidates/dtlgrind_candidate_space.json')
if not p.exists():
    print('candidate json missing')
    sys.exit(3)
data=json.loads(p.read_text(encoding='utf-8-sig'))
rv=data.get('resource_view',{})
bag=rv.get('bag_free',{})
emb=rv.get('embedded_committed',{})
print('Resource view:', {'eternal':bag.get('eternal_cores'), 'void':bag.get('void_cores'), 'chaos':bag.get('chaos_cores'), 'gems':bag.get('gems'), 'embedded_relic':emb.get('relic_cores_in_current_build'), 'awakening':emb.get('movable_awakening_cores_claimed')})
if bag.get('eternal_cores') != 240 or bag.get('void_cores') != 170 or bag.get('chaos_cores') != 120 or emb.get('relic_cores_in_current_build') != 45:
    print('BAD RESOURCE MAP: rerun candidate generator directly')
    sys.exit(4)
print('OK resource sanity check')
PY
  if ($LASTEXITCODE -ne 0) {
    Log "Repairing stale candidate files"
    python tools\sio_training\generate_sio_candidates.py --state data\sio_training\dtlgrind_state_v2.json --out data\sio_training\candidates
  }
}

# Use most of the machine. Override before running if wanted:
#   $env:SIO_FULLPOWER_PASSES="5"
#   $env:SIO_FULLPOWER_WORKERS="8"
if (-not $env:SIO_FULLPOWER_PASSES) { $env:SIO_FULLPOWER_PASSES = "3" }
if (-not $env:SIO_FULLPOWER_VERBOSE_EVERY) { $env:SIO_FULLPOWER_VERBOSE_EVERY = "4" }

Run-Step "FULL CPU candidate-space index" {
  python tools\sio_training\fullpower_candidate_index.py --state data\sio_training\dtlgrind_state_v2.json --candidate data\sio_training\candidates\dtlgrind_candidate_space.json --out data\sio_training\fullpower\latest
}

Run-Step "post fullpower scoring readiness" {
  python tools\sio_training\check_sio_scoring_readiness.py --candidate data\sio_training\candidates\dtlgrind_candidate_space.json --normalized data\sio_training\normalized\sio_normalized_tables.json --out data\sio_training\scoring
}

Run-Step "build final bundle" {
  $bundle = "data\sio_training\fullpower\latest\sio_fullpower_reports.zip"
  if (Test-Path $bundle) { Remove-Item $bundle -Force }
  $files = @(
    "data\sio_training\fullpower\latest\fullpower_candidate_index_report.md",
    "data\sio_training\fullpower\latest\fullpower_candidate_index.json",
    "data\sio_training\fullpower\latest\fullpower_distribution_index.csv",
    "data\sio_training\fullpower\latest\fullpower_builder_loop.log",
    "data\sio_training\scoring\scoring_readiness_report.md",
    "data\sio_training\candidates\candidate_generator_report.md",
    "data\sio_training\normalized\normalizer_unknowns_report.md",
    "data\sio_training\generated\unknowns_report.md"
  ) | Where-Object { Test-Path $_ }
  Compress-Archive -Path $files -DestinationPath $bundle -Force
  Write-Host "BUNDLE: $bundle"
}

Log "Full-power builder loop finished"
Write-Host ""
Write-Host "SEND THIS FILE: data\sio_training\fullpower\latest\sio_fullpower_reports.zip"
Write-Host "Or send: data\sio_training\fullpower\latest\fullpower_candidate_index_report.md"
try { Stop-Transcript | Out-Null } catch {}
