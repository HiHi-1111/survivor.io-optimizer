param(
  [string]$ZipPath = "data\sio_training\archive\sio_tools.exp0.dev.zip",
  [string]$Out = "data\sio_training\generated"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
Set-Location $repoRoot

New-Item -ItemType Directory -Force -Path $Out | Out-Null
$logPath = Join-Path $Out "powershell_run.log"
$unknownsPath = Join-Path $Out "unknowns_report.md"
$manifestPath = Join-Path $Out "sio_training_corpus_manifest.json"

function Say($msg) {
  $stamp = Get-Date -Format "HH:mm:ss"
  Write-Host "[$stamp] $msg"
}

Start-Transcript -Path $logPath -Force | Out-Null
try {
  Say "Repo root: $repoRoot"
  Say "Zip path: $ZipPath"
  Say "Output: $Out"

  if (!(Test-Path $ZipPath)) {
    Say "ERROR: zip not found at $ZipPath"
    Say "Put sio_tools.exp0.dev.zip at data\sio_training\archive\sio_tools.exp0.dev.zip or pass -ZipPath"
    exit 2
  }

  $zipSize = (Get-Item $ZipPath).Length
  Say "Zip size: $zipSize bytes"
  Say "Starting extractor. This should usually take under 1 minute; large bundles can take a few minutes."
  Say "The Python script prints live progress, ETA, current file, and what is taking time."

  python -u tools\sio_training\extract_sio_bundle.py $ZipPath --out $Out
  $code = $LASTEXITCODE

  if ($code -ne 0) {
    Say "Extractor failed with exit code $code"
    exit $code
  }

  Say "Finished successfully."
  Say "Manifest: $manifestPath"
  Say "Unknowns/problems report: $unknownsPath"
  Say "Full live log: $logPath"
} finally {
  Stop-Transcript | Out-Null
}
