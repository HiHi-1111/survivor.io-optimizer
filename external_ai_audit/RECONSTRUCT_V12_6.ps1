$ErrorActionPreference = 'Stop'

$base = 'https://raw.githubusercontent.com/HiHi-1111/survivor.io-optimizer/v12-6-external-ai-audit/external_ai_audit'
$parts = 1..6 | ForEach-Object {
    $name = 'V12_6_ZIP_BASE64_PART_{0:D2}.txt' -f $_
    (Invoke-WebRequest -UseBasicParsing "$base/$name").Content.Trim()
}

$bytes = [Convert]::FromBase64String(($parts -join ''))
$out = Join-Path $PWD 'SurvivorIO_Optimizer_V12_6_SECOND_PASS_RESOURCE_AUDITED_ONE_ZIP.zip'
[IO.File]::WriteAllBytes($out, $bytes)

$expected = 'de7084395b476f00fd004fa4888479bf45bfd152830f73faef6ed29023ad62cb'
$actual = (Get-FileHash -LiteralPath $out -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) {
    Remove-Item -LiteralPath $out -Force -ErrorAction SilentlyContinue
    throw "Checksum mismatch. Expected $expected but got $actual"
}

Write-Host "Reconstructed and verified: $out" -ForegroundColor Green
Write-Host "SHA-256: $actual"
