$ErrorActionPreference = "Continue"
$Start = Get-Date
$Repo = "$env:USERPROFILE\Downloads\survivor-optimizer"
$RepoZip = "$env:TEMP\survivor_optimizer_main.zip"
$Extract = "$env:TEMP\survivor_optimizer_extract"
$RawBase = "https://raw.githubusercontent.com/HiHi-1111/survivor.io-optimizer/main"

function Say($msg, $color="White") {
  $elapsed = [math]::Round(((Get-Date) - $Start).TotalSeconds, 1)
  Write-Host "[$elapsed s] $msg" -ForegroundColor $color
}

function DownloadFile($url, $out) {
  Say "Downloading $url" "DarkCyan"
  Invoke-WebRequest $url -OutFile $out
}

Say "=== FULL SIO TRAINING / INDEXING RUN ===" "Cyan"
Say "This builds data reports only. It must not invent optimizer advice." "Yellow"
Say "Repo target: $Repo"

if (!(Test-Path $Repo)) {
  Say "Repo folder missing. Downloading repo as ZIP instead of git clone." "Yellow"
  Remove-Item $Extract -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item $RepoZip -Force -ErrorAction SilentlyContinue
  Invoke-WebRequest "https://github.com/HiHi-1111/survivor.io-optimizer/archive/refs/heads/main.zip" -OutFile $RepoZip
  Expand-Archive $RepoZip -DestinationPath $Extract -Force
  $Src = Get-ChildItem $Extract -Directory | Select-Object -First 1
  Copy-Item $Src.FullName $Repo -Recurse -Force
}

Set-Location $Repo
Say "Now in repo: $(Get-Location)" "Green"

New-Item -ItemType Directory -Force tools\sio_training | Out-Null
New-Item -ItemType Directory -Force data\sio_training\archive | Out-Null
New-Item -ItemType Directory -Force data\sio_training\generated | Out-Null
New-Item -ItemType Directory -Force data\sio_training\normalized | Out-Null
New-Item -ItemType Directory -Force data\sio_training\training_runs\latest | Out-Null

Say "Refreshing latest training scripts from GitHub raw..." "Cyan"
DownloadFile "$RawBase/tools/sio_training/extract_sio_bundle.py" "tools\sio_training\extract_sio_bundle.py"
DownloadFile "$RawBase/tools/sio_training/normalize_sio_bundle.py" "tools\sio_training\normalize_sio_bundle.py"
DownloadFile "$RawBase/tools/sio_training/run_sio_training.ps1" "tools\sio_training\run_sio_training.ps1"
DownloadFile "$RawBase/tools/sio_training/run_sio_normalize.ps1" "tools\sio_training\run_sio_normalize.ps1"
DownloadFile "$RawBase/data/sio_training/mechanics_rules_practicality_v1.json" "data\sio_training\mechanics_rules_practicality_v1.json"

$ZipPath = "data\sio_training\archive\sio_tools.exp0.dev.zip"
if (!(Test-Path $ZipPath)) {
  Say "Looking for sio_tools.exp0.dev.zip in Downloads..." "Yellow"
  $SioZip = Get-ChildItem "$env:USERPROFILE\Downloads" -Filter "sio_tools.exp0.dev.zip" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
  if (!$SioZip) {
    Say "ERROR: Could not find sio_tools.exp0.dev.zip." "Red"
    Say "Put it in Downloads or in data\sio_training\archive\sio_tools.exp0.dev.zip then rerun." "Red"
    Read-Host "Press Enter to close"
    exit 1
  }
  Copy-Item $SioZip.FullName $ZipPath -Force
  Say "Copied holy-grail zip from: $($SioZip.FullName)" "Green"
}

$FullLog = "data\sio_training\training_runs\latest\full_run.log"
$Summary = "data\sio_training\training_runs\latest\full_training_summary.md"
$MechanicsUnknowns = "data\sio_training\training_runs\latest\mechanics_unknowns_report.md"
Remove-Item $FullLog -Force -ErrorAction SilentlyContinue

Say "Step 1/4: Extract sIO zip and find important modules. Usually under 1 minute." "Cyan"
powershell -ExecutionPolicy Bypass -File tools\sio_training\run_sio_training.ps1 2>&1 | Tee-Object -FilePath $FullLog -Append

Say "Step 2/4: Normalize sIO tables. If Node is missing, Python fallback should still write reports." "Cyan"
powershell -ExecutionPolicy Bypass -File tools\sio_training\run_sio_normalize.ps1 2>&1 | Tee-Object -FilePath $FullLog -Append

Say "Step 3/4: Build practical-mechanics training summary and unknowns..." "Cyan"
$py = @'
import json, hashlib, pathlib, datetime
root = pathlib.Path('.')
latest = root/'data/sio_training/training_runs/latest'
latest.mkdir(parents=True, exist_ok=True)
paths = {
  'zip': root/'data/sio_training/archive/sio_tools.exp0.dev.zip',
  'extract_manifest': root/'data/sio_training/generated/sio_training_corpus_manifest.json',
  'extract_unknowns': root/'data/sio_training/generated/unknowns_report.md',
  'normalized': root/'data/sio_training/normalized/sio_normalized_tables.json',
  'normalizer_unknowns': root/'data/sio_training/normalized/normalizer_unknowns_report.md',
  'mechanics': root/'data/sio_training/mechanics_rules_practicality_v1.json',
  'state': root/'data/sio_training/dtlgrind_state_v2.json'
}

def sha(p):
    if not p.exists(): return None
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()

def load_json(p):
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception as e: return {'_load_error': str(e)}

extract = load_json(paths['extract_manifest']) if paths['extract_manifest'].exists() else {}
normal = load_json(paths['normalized']) if paths['normalized'].exists() else {}
mech = load_json(paths['mechanics']) if paths['mechanics'].exists() else {}
state = load_json(paths['state']) if paths['state'].exists() else {}

unknowns=[]
if not paths['zip'].exists(): unknowns.append('Missing holy-grail zip at data/sio_training/archive/sio_tools.exp0.dev.zip')
if not paths['extract_manifest'].exists(): unknowns.append('Extractor manifest missing; extraction did not finish.')
if not paths['normalized'].exists(): unknowns.append('Normalized tables missing; normalizer did not finish or only wrote unknown report.')
if not paths['mechanics'].exists(): unknowns.append('Practical mechanics rules missing.')
if not paths['state'].exists(): unknowns.append('DTlgrind state file missing.')

# These are intentional unknowns until the simulator can prove them from data or user patch.
unknowns += [
  'Need exact AF downgrade/refund rules per SS side/level before counting committed AF resources as movable.',
  'Need exact S gear fodder recovery/re-implementation cost if moving AF investment between slots/sides.',
  'Need exact survivor shard conversion ratio/limits/cooldown before treating S survivor shard movement as cheap/free.',
  'Need exact Xeno pet awakening reset/refund behavior before counting all committed awakening cores as movable.',
  'Need next resonance breakpoint costs/effects for current tech setup before valuing Resonance Chips precisely.',
  'Need candidate generator to enumerate all choice outputs and respec/move paths together, not by separated lanes.',
  'Need damage scorer to calculate before/after from normalized sIO stat formulas instead of hardcoded spend plan.'
]

summary = []
summary.append('# Full sIO training/indexing summary')
summary.append('')
summary.append(f'Generated: {datetime.datetime.now().isoformat(timespec="seconds")}')
summary.append('')
summary.append('## What this run did')
summary.append('- Extracted the uploaded sIO static-export zip.')
summary.append('- Found webpack data/formula modules if present.')
summary.append('- Ran normalizer or fallback normalizer.')
summary.append('- Loaded practical movement rules so the optimizer does not treat committed resources as free.')
summary.append('- Wrote unknowns that need data patches instead of guesses.')
summary.append('')
summary.append('## Source truth')
summary.append(f'- Zip exists: {paths["zip"].exists()}')
summary.append(f'- Zip SHA256: {sha(paths["zip"])}')
summary.append(f'- Extract manifest exists: {paths["extract_manifest"].exists()}')
summary.append(f'- Normalized tables exists: {paths["normalized"].exists()}')
summary.append(f'- Mechanics rules exists: {paths["mechanics"].exists()}')
summary.append('')
summary.append('## Extractor modules found')
mods = extract.get('module_hints_found', {}) or extract.get('modules_found', {})
if mods:
    for k,v in mods.items(): summary.append(f'- {k}: {v}')
else:
    summary.append('- none listed')
summary.append('')
summary.append('## Training rule now enforced')
summary.append('- No forced relic cores / xeno cores / resonance chips / S selectors.')
summary.append('- Enumerate all valid allocations from inventory and movable build resources.')
summary.append('- A committed material is movable only if the simulator models the move/undo/refund path.')
summary.append('- AF downlevel/reprioritize is legal only if refund and re-implementation cost are known.')
summary.append('- S survivor switching can be cheaper only if shard conversion data proves it.')
summary.append('- Output must be data-backed: source item -> picked item -> end item -> final build -> damage delta.')
summary.append('')
summary.append('## Current known player-state resource rule')
summary.append('- Resources in current build are committed, not automatically free.')
summary.append('- Some committed resources may be movable, but only with modeled move/refund cost.')
summary.append('- If the rule is unknown, write unknown instead of guessing.')
summary.append('')
summary.append('## Next code step')
summary.append('Build the candidate generator + simulator from the normalized tables. This run prepares the data; it does not yet produce a final best spend order.')

unknown_md = ['# Training mechanics unknowns report',''] + [f'- {u}' for u in unknowns]
latest.joinpath('full_training_summary.md').write_text('\n'.join(summary), encoding='utf-8')
latest.joinpath('mechanics_unknowns_report.md').write_text('\n'.join(unknown_md), encoding='utf-8')
print('\n'.join(summary))
print('\nWROTE:', latest/'full_training_summary.md')
print('WROTE:', latest/'mechanics_unknowns_report.md')
'@
python -c $py 2>&1 | Tee-Object -FilePath $FullLog -Append

Say "Step 4/4: Done. Files to send back if anything seems wrong:" "Green"
Say "- data\sio_training\training_runs\latest\full_training_summary.md" "Yellow"
Say "- data\sio_training\training_runs\latest\mechanics_unknowns_report.md" "Yellow"
Say "- data\sio_training\generated\unknowns_report.md" "Yellow"
Say "- data\sio_training\normalized\normalizer_unknowns_report.md" "Yellow"
Say "Full log: $FullLog" "Cyan"
$Elapsed = [math]::Round(((Get-Date) - $Start).TotalSeconds, 1)
Say "Elapsed total: $Elapsed seconds" "Green"

Write-Host ""
Write-Host "Opening latest training folder..." -ForegroundColor Cyan
explorer "data\sio_training\training_runs\latest"
Read-Host "Press Enter to close"
