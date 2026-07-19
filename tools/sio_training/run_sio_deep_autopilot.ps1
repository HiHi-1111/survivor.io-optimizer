$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Start = Get-Date
$Repo = if ($env:SIO_REPO) { $env:SIO_REPO } else { "$env:USERPROFILE\Downloads\survivor-optimizer" }
$RunRoot = Join-Path $Repo "training_outputs\champion_lineage\runs\latest"
$LineageRoot = Join-Path $Repo "training_outputs\champion_lineage"
$Log = Join-Path $RunRoot "lineage_autopilot.log"
$Summary = Join-Path $RunRoot "lineage_autopilot_summary.md"

function Say([string]$Message, [string]$Color = "White") {
    $Elapsed = [math]::Round(((Get-Date) - $Start).TotalSeconds, 1)
    Write-Host "[$Elapsed s] $Message" -ForegroundColor $Color
}

function Ensure-Directory([string]$Path) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

function Run-Step([string]$Name, [scriptblock]$Block) {
    Say "==== $Name ====" "Cyan"
    Add-Content -Path $Log -Value "[$(Get-Date -Format s)] START $Name" -Encoding UTF8
    try {
        & $Block 2>&1 | Tee-Object -FilePath $Log -Append
        if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
            throw "$Name exited with code $LASTEXITCODE"
        }
        Add-Content -Path $Log -Value "[$(Get-Date -Format s)] END $Name" -Encoding UTF8
    } catch {
        Add-Content -Path $Log -Value "[$(Get-Date -Format s)] ERROR $Name : $($_.Exception.Message)" -Encoding UTF8
        throw
    }
}

function Find-Python {
    if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
    if (Get-Command py -ErrorAction SilentlyContinue) { return "py" }
    throw "Python was not found."
}

function Find-SioBundle {
    $Candidates = @()
    if ($env:SIO_TOOLS_BUNDLE) { $Candidates += $env:SIO_TOOLS_BUNDLE }
    $Candidates += @(
        (Join-Path $Repo "data\sio_training\archive\sio_tools.exp0.dev.zip"),
        (Join-Path $Repo "data\sio_training\archive\sio_tools.exp0.dev(1).zip"),
        (Join-Path $env:USERPROFILE "Downloads\sio_tools.exp0.dev.zip"),
        (Join-Path $env:USERPROFILE "Downloads\sio_tools.exp0.dev(1).zip")
    )
    foreach ($Candidate in $Candidates) {
        if ($Candidate -and (Test-Path $Candidate)) { return (Resolve-Path $Candidate).Path }
    }
    throw "The supplied sIO bundle was not found. Set SIO_TOOLS_BUNDLE or place it in data\sio_training\archive."
}

if (!(Test-Path $Repo)) {
    throw "Repository not found at $Repo. This workflow does not download main over the current work anymore."
}
Set-Location $Repo
Ensure-Directory $RunRoot
Ensure-Directory $LineageRoot
Remove-Item $Log -Force -ErrorAction SilentlyContinue
$Python = Find-Python
$Bundle = Find-SioBundle
$env:SIO_TOOLS_BUNDLE = $Bundle
$env:SIO_CHAMPION_LINEAGE_ROOT = $LineageRoot
$env:PYTHONUNBUFFERED = "1"

$Branch = "unknown"
try { $Branch = (git rev-parse --abbrev-ref HEAD 2>$null).Trim() } catch {}
Say "Repository: $Repo" "Green"
Say "Branch: $Branch" "Green"
Say "sIO bundle: $Bundle" "Green"
Say "Champion lineage: $LineageRoot" "Green"

# Keep source extraction and normalization as Bible refresh steps. They never
# delete or replace champions.
if (Test-Path "tools\sio_training\run_sio_training.ps1") {
    Run-Step "Extract supplied sIO Bible" {
        powershell -ExecutionPolicy Bypass -File "tools\sio_training\run_sio_training.ps1"
    }
}
if (Test-Path "tools\sio_training\run_sio_normalize.ps1") {
    Run-Step "Normalize supplied sIO Bible" {
        powershell -ExecutionPolicy Bypass -File "tools\sio_training\run_sio_normalize.ps1"
    }
}

Run-Step "Focused exact CE tests" {
    & $Python "tools\run_sio_ce_tests.py"
}

$Dataset = if ($env:SIO_LINEAGE_DATASET) { $env:SIO_LINEAGE_DATASET } else { "training_outputs\exact_ce_labels.jsonl" }
$Profiles = if ($env:SIO_LINEAGE_PROFILES) { $env:SIO_LINEAGE_PROFILES } else { "data\sio_training\exact_ce_profiles.jsonl" }
$Generations = if ($env:SIO_LINEAGE_GENERATIONS) { [int]$env:SIO_LINEAGE_GENERATIONS } else { 8 }
$Children = if ($env:SIO_LINEAGE_CHILDREN) { [int]$env:SIO_LINEAGE_CHILDREN } else { 6 }
$Epochs = if ($env:SIO_LINEAGE_EPOCHS) { [int]$env:SIO_LINEAGE_EPOCHS } else { 5 }
$TrainingReport = Join-Path $RunRoot "champion_training_report.json"
$TrainingSource = $null

if (Test-Path $Dataset) {
    $TrainingSource = "dataset"
    Run-Step "Train inherited champion children from exact labels" {
        & $Python "tools\sio_training\train_champion_lineage.py" `
            --dataset $Dataset `
            --lineage-root $LineageRoot `
            --generations $Generations `
            --children $Children `
            --epochs $Epochs `
            --report $TrainingReport
    }
} elseif (Test-Path $Profiles) {
    $TrainingSource = "profiles"
    Run-Step "Create exact sIO labels and train inherited champion children" {
        & $Python "tools\sio_training\train_champion_lineage.py" `
            --profiles $Profiles `
            --lineage-root $LineageRoot `
            --generations $Generations `
            --children $Children `
            --epochs $Epochs `
            --report $TrainingReport
    }
} else {
    Say "No exact lineage dataset or exact profile set was found. Training was skipped instead of inventing labels." "Yellow"
    Add-Content -Path $Log -Value "Training skipped: missing $Dataset and $Profiles" -Encoding UTF8
}

$Registry = Join-Path $LineageRoot "registry.json"
$CurrentChampion = "none"
$HallCount = 0
if (Test-Path $Registry) {
    try {
        $RegistryData = Get-Content $Registry -Raw | ConvertFrom-Json
        $CurrentChampion = $RegistryData.current_champion_id
        $HallCount = @($RegistryData.hall_of_fame).Count
    } catch {}
}

$Lines = @(
    "# sIO champion-lineage autopilot summary",
    "",
    "Generated: $(Get-Date -Format s)",
    "Repository branch: $Branch",
    "Training source: $(if ($TrainingSource) { $TrainingSource } else { 'skipped: no exact labels' })",
    "Current champion: $CurrentChampion",
    "Hall-of-fame champions: $HallCount",
    "",
    "## Rules enforced",
    "",
    "- The workflow uses the current checkout; it never downloads main over local work.",
    "- The sIO runtime is the exact Clan Expedition teacher.",
    "- Every child inherits the current champion and may inherit older champions.",
    "- Parent checkpoints are immutable while children train.",
    "- A failed child is saved as rejected and cannot damage the champion.",
    "- Promotion requires exact holdout improvement and all no-op/mandatory gates.",
    "- Missing exact data skips training instead of creating labels.",
    "- The champion orders proposals only; exact CE before/after damage chooses recommendations.",
    "",
    "Log: $Log",
    "Lineage registry: $Registry",
    "Training report: $TrainingReport"
)
$Lines | Set-Content -Path $Summary -Encoding UTF8
Say "Finished. Summary: $Summary" "Green"
