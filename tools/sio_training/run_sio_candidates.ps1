$ErrorActionPreference = "Continue"
$Start = Get-Date
$Repo = (Get-Location).Path
$RawBase = "https://raw.githubusercontent.com/HiHi-1111/survivor.io-optimizer/main"

function Say($msg, $color="White") {
  $elapsed = [math]::Round(((Get-Date) - $Start).TotalSeconds, 1)
  Write-Host "[$elapsed s] $msg" -ForegroundColor $color
}

Say "=== SIO CANDIDATE GENERATOR RUN ===" "Cyan"
Say "Repo root: $Repo"

New-Item -ItemType Directory -Force tools\sio_training | Out-Null
New-Item -ItemType Directory -Force data\sio_training\candidates | Out-Null

Say "Refreshing candidate generator..." "Cyan"
Invoke-WebRequest "$RawBase/tools/sio_training/generate_sio_candidates.py" -OutFile "tools\sio_training\generate_sio_candidates.py"

$State = "data\sio_training\dtlgrind_state_v2.json"
$Norm = "data\sio_training\normalized\sio_normalized_tables.json"
$Mech = "data\sio_training\mechanics_rules_practicality_v1.json"
$Out = "data\sio_training\candidates"
$Log = "data\sio_training\candidates\candidate_run.log"

if (!(Test-Path $State)) { Say "ERROR: Missing $State" "Red"; exit 1 }
if (!(Test-Path $Norm)) { Say "ERROR: Missing $Norm. Run full training first." "Red"; exit 1 }
if (!(Test-Path $Mech)) { Say "ERROR: Missing $Mech" "Red"; exit 1 }

Say "Generating legal choice allocation candidates. This should take under 1 minute." "Yellow"
python tools\sio_training\generate_sio_candidates.py --state $State --normalized $Norm --mechanics $Mech --out $Out 2>&1 | Tee-Object -FilePath $Log

Say "Done. Files:" "Green"
Say "- data\sio_training\candidates\dtlgrind_candidate_space.json" "Yellow"
Say "- data\sio_training\candidates\candidate_generator_report.md" "Yellow"
Say "- data\sio_training\candidates\candidate_run.log" "Yellow"
explorer "data\sio_training\candidates"
