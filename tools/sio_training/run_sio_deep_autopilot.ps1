$ErrorActionPreference = "Continue"
$ProgressPreference = "Continue"
$Start = Get-Date
$RawBase = "https://raw.githubusercontent.com/HiHi-1111/survivor.io-optimizer/main"
$Repo = "$env:USERPROFILE\Downloads\survivor-optimizer"
$RepoZip = "$env:TEMP\survivor_optimizer_main_deep.zip"
$Extract = "$env:TEMP\survivor_optimizer_main_deep_extract"
$RunRoot = "data\sio_training\deep_runs\latest"
$Log = "$RunRoot\deep_autopilot.log"
$Summary = "$RunRoot\deep_autopilot_summary.md"
$SendMe = "$RunRoot\SEND_ME_THESE_FILES.md"

function Say($msg, $color="White") {
  $elapsed = [math]::Round(((Get-Date) - $Start).TotalSeconds, 1)
  Write-Host "[$elapsed s] $msg" -ForegroundColor $color
}

function AppendLog($msg) {
  $stamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
  Add-Content -Path $Log -Value "[$stamp] $msg" -Encoding UTF8
}

function EnsureDir($path) {
  New-Item -ItemType Directory -Force $path | Out-Null
}

function DownloadFresh($relative, $target) {
  $url = "$RawBase/$relative?fresh=$([int][double]::Parse((Get-Date -UFormat %s)))"
  Say "Refreshing $relative" "DarkCyan"
  EnsureDir (Split-Path $target -Parent)
  Invoke-WebRequest $url -OutFile $target -UseBasicParsing
  if (!(Test-Path $target)) { throw "Download failed: $relative" }
}

function RunStep($name, $scriptBlock) {
  Say "==== $name ====" "Cyan"
  AppendLog "START $name"
  try {
    & $scriptBlock 2>&1 | Tee-Object -FilePath $Log -Append
    AppendLog "END $name"
  } catch {
    Say "ERROR in $name : $($_.Exception.Message)" "Red"
    AppendLog "ERROR $name : $($_.Exception.Message)"
  }
}

function FindPython() {
  $py = Get-Command python -ErrorAction SilentlyContinue
  if ($py) { return "python" }
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) { return "py" }
  return $null
}

function TryPortableNode() {
  $nodeCmd = Get-Command node -ErrorAction SilentlyContinue
  if ($nodeCmd) {
    Say "Node already found: $($nodeCmd.Source)" "Green"
    return
  }
  $NodeRoot = "$Repo\.tools\node"
  $NodeZip = "$env:TEMP\node_portable_sio.zip"
  $NodeVersion = "v22.13.1"
  $NodeFolder = "$NodeRoot\node-$NodeVersion-win-x64"
  if (Test-Path "$NodeFolder\node.exe") {
    $env:PATH = "$NodeFolder;$env:PATH"
    Say "Using existing portable Node: $NodeFolder" "Green"
    return
  }
  Say "Node not found. Trying portable Node download. This is non-admin and local to this repo." "Yellow"
  EnsureDir $NodeRoot
  try {
    Invoke-WebRequest "https://nodejs.org/dist/$NodeVersion/node-$NodeVersion-win-x64.zip" -OutFile $NodeZip -UseBasicParsing
    Expand-Archive $NodeZip -DestinationPath $NodeRoot -Force
    if (Test-Path "$NodeFolder\node.exe") {
      $env:PATH = "$NodeFolder;$env:PATH"
      Say "Portable Node ready: $NodeFolder" "Green"
    } else {
      Say "Portable Node download did not produce node.exe. Continuing with Python fallback." "Yellow"
    }
  } catch {
    Say "Portable Node setup failed. Continuing with Python fallback. $($_.Exception.Message)" "Yellow"
  }
}

function EnsureRepo() {
  if (Test-Path $Repo) {
    Set-Location $Repo
    Say "Using repo: $(Get-Location)" "Green"
    return
  }
  Say "Repo missing. Downloading GitHub ZIP instead of git clone." "Yellow"
  Remove-Item $Extract -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item $RepoZip -Force -ErrorAction SilentlyContinue
  Invoke-WebRequest "https://github.com/HiHi-1111/survivor.io-optimizer/archive/refs/heads/main.zip" -OutFile $RepoZip -UseBasicParsing
  Expand-Archive $RepoZip -DestinationPath $Extract -Force
  $Src = Get-ChildItem $Extract -Directory | Select-Object -First 1
  Copy-Item $Src.FullName $Repo -Recurse -Force
  Set-Location $Repo
  Say "Repo ready: $(Get-Location)" "Green"
}

function EnsureHolyZip() {
  EnsureDir "data\sio_training\archive"
  $ZipPath = "data\sio_training\archive\sio_tools.exp0.dev.zip"
  if (Test-Path $ZipPath) {
    Say "Holy-grail zip found: $ZipPath" "Green"
    return
  }
  Say "Looking for sio_tools.exp0.dev.zip anywhere under Downloads..." "Yellow"
  $found = Get-ChildItem "$env:USERPROFILE\Downloads" -Filter "sio_tools.exp0.dev.zip" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
  if (!$found) {
    Say "ERROR: cannot find sio_tools.exp0.dev.zip. Put it in Downloads or data\sio_training\archive." "Red"
    throw "Missing sio_tools.exp0.dev.zip"
  }
  Copy-Item $found.FullName $ZipPath -Force
  Say "Copied zip from $($found.FullName)" "Green"
}

function RefreshTrainingFiles() {
  $files = @(
    @{r="tools/sio_training/extract_sio_bundle.py"; t="tools\sio_training\extract_sio_bundle.py"},
    @{r="tools/sio_training/normalize_sio_bundle.py"; t="tools\sio_training\normalize_sio_bundle.py"},
    @{r="tools/sio_training/generate_sio_candidates.py"; t="tools\sio_training\generate_sio_candidates.py"},
    @{r="tools/sio_training/check_sio_scoring_readiness.py"; t="tools\sio_training\check_sio_scoring_readiness.py"},
    @{r="tools/sio_training/run_sio_training.ps1"; t="tools\sio_training\run_sio_training.ps1"},
    @{r="tools/sio_training/run_sio_normalize.ps1"; t="tools\sio_training\run_sio_normalize.ps1"},
    @{r="tools/sio_training/run_sio_candidates.ps1"; t="tools\sio_training\run_sio_candidates.ps1"},
    @{r="tools/sio_training/run_sio_scoring_readiness.ps1"; t="tools\sio_training\run_sio_scoring_readiness.ps1"},
    @{r="data/sio_training/dtlgrind_state_v2.json"; t="data\sio_training\dtlgrind_state_v2.json"},
    @{r="data/sio_training/mechanics_rules_practicality_v1.json"; t="data\sio_training\mechanics_rules_practicality_v1.json"}
  )
  foreach ($f in $files) {
    try { DownloadFresh $f.r $f.t } catch { Say "Could not refresh $($f.r): $($_.Exception.Message)" "Yellow" }
  }
}

function ValidateCandidates() {
  $py = FindPython
  if (!$py) { Say "Python missing; cannot validate candidates." "Red"; return $false }
  $code = @'
import json, pathlib, sys
p=pathlib.Path('data/sio_training/candidates/dtlgrind_candidate_space.json')
if not p.exists():
    print('BAD: candidate json missing')
    sys.exit(2)
d=json.loads(p.read_text(encoding='utf-8'))
rv=d.get('resource_view',{})
b=rv.get('bag_free',{})
e=rv.get('embedded_committed',{})
checks={
  'eternal_cores': b.get('eternal_cores'),
  'void_cores': b.get('void_cores'),
  'chaos_cores': b.get('chaos_cores'),
  'gems': b.get('gems'),
  'relic_cores_in_current_build': e.get('relic_cores_in_current_build'),
  'movable_awakening_cores_claimed': e.get('movable_awakening_cores_claimed'),
}
print('Candidate resource checks:', checks)
if checks['eternal_cores'] != 240 or checks['void_cores'] != 170 or checks['chaos_cores'] != 120 or checks['relic_cores_in_current_build'] != 45 or checks['movable_awakening_cores_claimed'] != 23:
    print('BAD: resource mapping mismatch')
    sys.exit(3)
counts=d.get('choice_candidate_space',{}).get('counts',{})
if counts.get('core_x_relic_allocations') != 252:
    print('BAD: core/relic count mismatch')
    sys.exit(4)
print('OK: candidate resources and counts validated')
'@
  & $py -c $code 2>&1 | Tee-Object -FilePath $Log -Append
  return ($LASTEXITCODE -eq 0)
}

function WriteFinalSummary() {
  EnsureDir $RunRoot
  $now = Get-Date
  $lines = @()
  $lines += "# Deep sIO autopilot summary"
  $lines += ""
  $lines += "Generated: $($now.ToString('yyyy-MM-dd HH:mm:ss'))"
  $lines += ""
  $lines += "## What this run attempted"
  $lines += "- Refreshed latest training scripts."
  $lines += "- Verified the sIO zip exists."
  $lines += "- Tried portable Node for fuller runtime normalization, but falls back to Python safely."
  $lines += "- Ran extractor, normalizer, candidate generator, scoring readiness, tests, and validation loops."
  $lines += "- Re-ran candidate generation if resource mapping was wrong."
  $lines += "- Created a report bundle zip."
  $lines += ""
  $lines += "## Key files"
  $lines += "- data/sio_training/generated/unknowns_report.md"
  $lines += "- data/sio_training/normalized/normalizer_unknowns_report.md"
  $lines += "- data/sio_training/candidates/candidate_generator_report.md"
  $lines += "- data/sio_training/scoring/scoring_readiness_report.md"
  $lines += "- data/sio_training/deep_runs/latest/deep_autopilot.log"
  $lines += "- data/sio_training/deep_runs/latest/sio_deep_run_reports.zip"
  $lines += ""
  $lines += "## Rule"
  $lines += "No final spend recommendation is allowed unless the candidate after-state is simulated and scored with extracted sIO formulas."
  $lines | Set-Content $Summary -Encoding UTF8

  $send = @()
  $send += "# Send me these files first"
  $send += ""
  $send += "1. data/sio_training/deep_runs/latest/sio_deep_run_reports.zip"
  $send += "2. data/sio_training/scoring/scoring_readiness_report.md"
  $send += "3. data/sio_training/candidates/candidate_generator_report.md"
  $send += "4. data/sio_training/deep_runs/latest/deep_autopilot_summary.md"
  $send += ""
  $send += "If the zip is too annoying, send only scoring_readiness_report.md and candidate_generator_report.md."
  $send | Set-Content $SendMe -Encoding UTF8
}

function BundleReports() {
  $bundle = "$RunRoot\sio_deep_run_reports.zip"
  Remove-Item $bundle -Force -ErrorAction SilentlyContinue
  $items = @(
    "data\sio_training\generated\unknowns_report.md",
    "data\sio_training\generated\sio_training_corpus_manifest.json",
    "data\sio_training\normalized\normalizer_unknowns_report.md",
    "data\sio_training\normalized\sio_normalized_tables.json",
    "data\sio_training\candidates\candidate_generator_report.md",
    "data\sio_training\candidates\dtlgrind_candidate_space.json",
    "data\sio_training\scoring\scoring_readiness_report.md",
    "data\sio_training\scoring\scoring_readiness.json",
    $Log,
    $Summary,
    $SendMe
  ) | Where-Object { Test-Path $_ }
  if ($items.Count -gt 0) {
    Compress-Archive -Path $items -DestinationPath $bundle -Force
    Say "Bundled reports: $bundle" "Green"
  } else {
    Say "No report files found to bundle." "Yellow"
  }
}

# Main
EnsureRepo
EnsureDir $RunRoot
Remove-Item $Log -Force -ErrorAction SilentlyContinue
AppendLog "Deep autopilot started"
try { [System.Diagnostics.Process]::GetCurrentProcess().PriorityClass = 'High'; Say "Set PowerShell process priority to High." "Green" } catch { Say "Could not set priority. Continuing." "Yellow" }
$env:PYTHONUNBUFFERED = "1"

RunStep "Preflight: refresh scripts and source files" { RefreshTrainingFiles }
RunStep "Preflight: find/copy sIO holy-grail zip" { EnsureHolyZip }
RunStep "Preflight: optional portable Node setup" { TryPortableNode }

# Do multiple passes. This is intentional so the laptop works for a while and self-repairs stale scripts/output.
for ($pass = 1; $pass -le 3; $pass++) {
  Say "######## AUTOPILOT PASS $pass / 3 ########" "Magenta"
  RunStep "Pass $pass extractor" { powershell -ExecutionPolicy Bypass -File tools\sio_training\run_sio_training.ps1 }
  RunStep "Pass $pass normalizer" { powershell -ExecutionPolicy Bypass -File tools\sio_training\run_sio_normalize.ps1 }
  RunStep "Pass $pass candidate generation" { python tools\sio_training\generate_sio_candidates.py --state data\sio_training\dtlgrind_state_v2.json --mechanics data\sio_training\mechanics_rules_practicality_v1.json --normalized data\sio_training\normalized\sio_normalized_tables.json --out data\sio_training\candidates --preview 200 }
  $ok = ValidateCandidates
  if (!$ok) {
    Say "Candidate validation failed. Forcing fresh candidate/state scripts and rerunning." "Yellow"
    try { DownloadFresh "tools/sio_training/generate_sio_candidates.py" "tools\sio_training\generate_sio_candidates.py" } catch {}
    try { DownloadFresh "data/sio_training/dtlgrind_state_v2.json" "data\sio_training\dtlgrind_state_v2.json" } catch {}
    RunStep "Pass $pass candidate generation repair rerun" { python tools\sio_training\generate_sio_candidates.py --state data\sio_training\dtlgrind_state_v2.json --mechanics data\sio_training\mechanics_rules_practicality_v1.json --normalized data\sio_training\normalized\sio_normalized_tables.json --out data\sio_training\candidates --preview 200 }
    ValidateCandidates | Out-Null
  }
  RunStep "Pass $pass scoring readiness" { powershell -ExecutionPolicy Bypass -File tools\sio_training\run_sio_scoring_readiness.ps1 }
}

RunStep "Repository tests if present" {
  if (Test-Path "tests") {
    python -m pytest -q
  } else {
    Write-Host "No tests folder found. Skipping pytest."
  }
}

RunStep "Final report bundle" {
  WriteFinalSummary
  BundleReports
}

Say "DONE. Opening deep run folder." "Green"
explorer $RunRoot
Read-Host "Press Enter to close"