<#
Long walk-away Survivor.io optimizer run.

Goal: user sends ONE file back:
  data\sio_training\SEND_THIS_ONE_REPORT.md

This still does NOT fake a best-spend answer. It reruns the pipeline, burns CPU on
nested fullpower choice-space validation, reruns after-state/scoring checks, then
combines the important reports into one markdown file.
#>
$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

$Repo = "$env:USERPROFILE\Downloads\survivor-optimizer"
$Raw = "https://raw.githubusercontent.com/HiHi-1111/survivor.io-optimizer/main"
Set-Location $Repo

function Ensure-Dir($p) {
  if (!(Test-Path $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null }
}

function Log($msg) {
  $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  $line = "[$ts] $msg"
  Write-Host $line
  Add-Content -Path $Global:WalkLog -Value $line -Encoding UTF8
}

function Download-Fresh($remotePath, $localPath) {
  Ensure-Dir (Split-Path $localPath -Parent)
  $url = "$Raw/$remotePath?fresh=walkaway_$(Get-Date -Format 'yyyyMMddHHmmss')"
  Log "Downloading $remotePath"
  Invoke-WebRequest $url -OutFile $localPath -UseBasicParsing
}

function Run-Step($name, [scriptblock]$block) {
  Log "START $name"
  $start = Get-Date
  try {
    & $block 2>&1 | Tee-Object -FilePath $Global:WalkLog -Append
    $code = $LASTEXITCODE
    if ($null -eq $code) { $code = 0 }
    if ($code -ne 0) { Log "WARN $name exit code $code" }
  } catch {
    Log "ERROR in $name"
    $_ | Out-String | Tee-Object -FilePath $Global:WalkLog -Append
  }
  $elapsed = [math]::Round(((Get-Date) - $start).TotalSeconds, 1)
  Log "END $name after $elapsed sec"
}

Ensure-Dir "data\sio_training\ONE_SEND"
Ensure-Dir "tools\sio_training"
$Global:WalkLog = "data\sio_training\ONE_SEND\walkaway_run.log"
$OneReport = "data\sio_training\SEND_THIS_ONE_REPORT.md"
"" | Set-Content -Path $Global:WalkLog -Encoding UTF8

# Make it a real walk-away run by default. Override before running if wanted:
#   $env:SIO_FULLPOWER_PASSES="15"
#   $env:SIO_FULLPOWER_WORKERS="8"
if (-not $env:SIO_FULLPOWER_PASSES) { $env:SIO_FULLPOWER_PASSES = "10" }
if (-not $env:SIO_FULLPOWER_VERBOSE_EVERY) { $env:SIO_FULLPOWER_VERBOSE_EVERY = "2" }

Log "WALKAWAY one-report run started"
Log "Repo: $Repo"
Log "Fullpower passes: $env:SIO_FULLPOWER_PASSES"

Run-Step "refresh latest scripts" {
  Download-Fresh "tools/sio_training/run_sio_deep_autopilot.ps1" "tools\sio_training\run_sio_deep_autopilot.ps1"
  Download-Fresh "tools/sio_training/run_sio_normalize.ps1" "tools\sio_training\run_sio_normalize.ps1"
  Download-Fresh "tools/sio_training/extract_sio_bundle.py" "tools\sio_training\extract_sio_bundle.py"
  Download-Fresh "tools/sio_training/normalize_sio_bundle.py" "tools\sio_training\normalize_sio_bundle.py"
  Download-Fresh "tools/sio_training/generate_sio_candidates.py" "tools\sio_training\generate_sio_candidates.py"
  Download-Fresh "tools/sio_training/fullpower_candidate_index.py" "tools\sio_training\fullpower_candidate_index.py"
  Download-Fresh "tools/sio_training/build_afterstate_probe.py" "tools\sio_training\build_afterstate_probe.py"
  Download-Fresh "tools/sio_training/check_sio_scoring_readiness.py" "tools\sio_training\check_sio_scoring_readiness.py"
  Download-Fresh "tools/sio_training/build_walkaway_one_report.py" "tools\sio_training\build_walkaway_one_report.py"
  Download-Fresh "data/sio_training/dtlgrind_state_v2.json" "data\sio_training\dtlgrind_state_v2.json"
}

Run-Step "make sure sIO zip exists" {
  Ensure-Dir "data\sio_training\archive"
  $TargetZip = "data\sio_training\archive\sio_tools.exp0.dev.zip"
  if (!(Test-Path $TargetZip)) {
    $Candidate1 = "$env:USERPROFILE\Downloads\sio_tools.exp0.dev.zip"
    $Candidate2 = "$env:USERPROFILE\Downloads\latest.zip"
    if (Test-Path $Candidate1) { Copy-Item $Candidate1 $TargetZip -Force }
    elseif (Test-Path $Candidate2) { Copy-Item $Candidate2 $TargetZip -Force }
  }
  if (!(Test-Path $TargetZip)) {
    Write-Host "MISSING ZIP: put sio_tools.exp0.dev.zip in Downloads or data\sio_training\archive"
    exit 2
  }
  Get-Item $TargetZip | Format-List FullName,Length,LastWriteTime
}

Run-Step "deep autopilot warmup and repair" {
  powershell -ExecutionPolicy Bypass -File "tools\sio_training\run_sio_deep_autopilot.ps1"
}

Run-Step "nested fullpower choice-space validation" {
  python tools\sio_training\fullpower_candidate_index.py --state data\sio_training\dtlgrind_state_v2.json --candidate data\sio_training\candidates\dtlgrind_candidate_space.json --out data\sio_training\fullpower\latest
}

Run-Step "after-state bridge probe" {
  python tools\sio_training\build_afterstate_probe.py --fullpower data\sio_training\fullpower\latest\fullpower_candidate_index.json --normalized data\sio_training\normalized\sio_normalized_tables.json --distribution data\sio_training\fullpower\latest\fullpower_distribution_index.csv --out data\sio_training\afterstate
}

Run-Step "scoring readiness check" {
  python tools\sio_training\check_sio_scoring_readiness.py --candidate data\sio_training\candidates\dtlgrind_candidate_space.json --normalized data\sio_training\normalized\sio_normalized_tables.json --out data\sio_training\scoring
}

Run-Step "build ONE report file" {
  python tools\sio_training\build_walkaway_one_report.py --repo-root . --out $OneReport --log $Global:WalkLog
}

Log "WALKAWAY one-report run finished"
Write-Host ""
Write-Host "SEND ONLY THIS ONE FILE:"
Write-Host $OneReport
Write-Host ""
Write-Host "Quick check:"
Test-Path $OneReport
