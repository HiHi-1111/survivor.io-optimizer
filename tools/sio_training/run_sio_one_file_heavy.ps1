<#
Clean walk-away one-file runner for the Survivor.io optimizer.

Goals:
- no deep-autopilot pause
- no pytest dependency
- no zip packaging lock
- one final report in an easy location
- heavier fullpower validation controlled by SIO_FULLPOWER_PASSES
#>
$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Repo = "$env:USERPROFILE\Downloads\survivor-optimizer"
$Raw = "https://raw.githubusercontent.com/HiHi-1111/survivor.io-optimizer/main"
Set-Location $Repo

New-Item -ItemType Directory -Force -Path "tools\sio_training" | Out-Null
New-Item -ItemType Directory -Force -Path "data\sio_training\walkaway" | Out-Null
New-Item -ItemType Directory -Force -Path "data\sio_training\fullpower\latest" | Out-Null
New-Item -ItemType Directory -Force -Path "data\sio_training\afterstate" | Out-Null
New-Item -ItemType Directory -Force -Path "data\sio_training\scoring" | Out-Null

$Log = "data\sio_training\walkaway\walkaway_one_report.log"
$OneReport = "data\sio_training\SEND_THIS_ONE_REPORT.md"
$RootReport = "SEND_THIS_ONE_REPORT.md"
Remove-Item $Log -Force -ErrorAction SilentlyContinue

function Log-Line([string]$msg) {
  $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
  Write-Host $line
  Add-Content -Path $Log -Value $line -Encoding UTF8
}

function Download-Known([string]$remotePath, [string]$localPath) {
  $url = "$Raw/$remotePath?fresh=$(Get-Date -Format yyyyMMddHHmmss)"
  try {
    Log-Line "Downloading $remotePath"
    Invoke-WebRequest $url -OutFile $localPath -UseBasicParsing
  } catch {
    Log-Line "Could not download $remotePath; keeping local copy if it exists. $($_.Exception.Message)"
    if (!(Test-Path $localPath)) {
      throw "Missing local script after download failed: $localPath"
    }
  }
}

function Run-Step([string]$name, [scriptblock]$block) {
  Log-Line "START $name"
  $sw = [Diagnostics.Stopwatch]::StartNew()
  try {
    & $block 2>&1 | ForEach-Object {
      $s = $_.ToString()
      Write-Host $s
      Add-Content -Path $Log -Value $s -Encoding UTF8
    }
    Log-Line "END $name after $([math]::Round($sw.Elapsed.TotalSeconds,1)) sec"
  } catch {
    Log-Line "ERROR in $name after $([math]::Round($sw.Elapsed.TotalSeconds,1)) sec: $($_.Exception.Message)"
  }
}

if (-not $env:SIO_FULLPOWER_PASSES) { $env:SIO_FULLPOWER_PASSES = "10" }
if (-not $env:SIO_FULLPOWER_WORKERS) { $env:SIO_FULLPOWER_WORKERS = "0" }

try {
  (Get-Process -Id $PID).PriorityClass = "High"
  Log-Line "Set process priority to High"
} catch {
  Log-Line "Could not set process priority: $($_.Exception.Message)"
}

Log-Line "ONE-FILE heavy run started"
Log-Line "Repo: $Repo"
Log-Line "Passes: $env:SIO_FULLPOWER_PASSES"

Run-Step "refresh known scripts only" {
  Download-Known "tools/sio_training/generate_sio_candidates.py" "tools\sio_training\generate_sio_candidates.py"
  Download-Known "tools/sio_training/fullpower_candidate_index.py" "tools\sio_training\fullpower_candidate_index.py"
  Download-Known "tools/sio_training/build_afterstate_probe.py" "tools\sio_training\build_afterstate_probe.py"
  Download-Known "tools/sio_training/check_sio_scoring_readiness.py" "tools\sio_training\check_sio_scoring_readiness.py"
  Download-Known "tools/sio_training/build_send_this_one_report.py" "tools\sio_training\build_send_this_one_report.py"
}

Run-Step "verify holy-grail sIO zip" {
  if (!(Test-Path "data\sio_training\archive\sio_tools.exp0.dev.zip")) {
    throw "Missing data\sio_training\archive\sio_tools.exp0.dev.zip"
  }
  Get-Item "data\sio_training\archive\sio_tools.exp0.dev.zip" | Format-List FullName,Length,LastWriteTime
}

Run-Step "extract sIO bundle if local extractor exists" {
  if (Test-Path "tools\sio_training\run_sio_training.ps1") {
    powershell -ExecutionPolicy Bypass -File "tools\sio_training\run_sio_training.ps1"
  } elseif (Test-Path "tools\sio_training\extract_sio_bundle.py") {
    python "tools\sio_training\extract_sio_bundle.py" --zip "data\sio_training\archive\sio_tools.exp0.dev.zip" --out "data\sio_training\generated"
  } else {
    Write-Host "SKIP: no local extractor script found; using existing generated files."
  }
}

Run-Step "normalize sIO bundle if local normalizer exists" {
  if (Test-Path "tools\sio_training\run_sio_normalize.ps1") {
    powershell -ExecutionPolicy Bypass -File "tools\sio_training\run_sio_normalize.ps1"
  } elseif (Test-Path "tools\sio_training\normalize_sio_bundle.py") {
    python "tools\sio_training\normalize_sio_bundle.py" --zip "data\sio_training\archive\sio_tools.exp0.dev.zip" --out "data\sio_training\normalized"
  } else {
    Write-Host "SKIP: no local normalizer script found; using existing normalized files."
  }
}

Run-Step "generate nested candidates" {
  python "tools\sio_training\generate_sio_candidates.py" --state "data\sio_training\dtlgrind_state_v2.json" --out "data\sio_training\candidates"
}

Run-Step "scoring readiness before fullpower" {
  python "tools\sio_training\check_sio_scoring_readiness.py" --candidates "data\sio_training\candidates\dtlgrind_candidate_space.json" --normalized "data\sio_training\normalized\sio_normalized_tables.json" --out "data\sio_training\scoring"
}

Run-Step "FULL CPU nested candidate-space validation" {
  python "tools\sio_training\fullpower_candidate_index.py" --state "data\sio_training\dtlgrind_state_v2.json" --candidate "data\sio_training\candidates\dtlgrind_candidate_space.json" --out "data\sio_training\fullpower\latest"
}

Run-Step "after-state bridge probe" {
  python "tools\sio_training\build_afterstate_probe.py" --fullpower "data\sio_training\fullpower\latest\fullpower_candidate_index.json" --normalized "data\sio_training\normalized\sio_normalized_tables.json" --distribution "data\sio_training\fullpower\latest\fullpower_distribution_index.csv" --out "data\sio_training\afterstate"
}

Run-Step "scoring readiness after fullpower" {
  python "tools\sio_training\check_sio_scoring_readiness.py" --candidates "data\sio_training\candidates\dtlgrind_candidate_space.json" --normalized "data\sio_training\normalized\sio_normalized_tables.json" --out "data\sio_training\scoring"
}

Run-Step "build SEND_THIS_ONE_REPORT" {
  python "tools\sio_training\build_send_this_one_report.py" --out $OneReport --also-root $RootReport
}

Log-Line "ONE-FILE heavy run finished"
Write-Host ""
Write-Host "DONE. SEND ONLY ONE OF THESE:"
Resolve-Path $OneReport -ErrorAction SilentlyContinue
Resolve-Path $RootReport -ErrorAction SilentlyContinue
try {
  explorer.exe /select,"$(Resolve-Path $RootReport)"
} catch {}
