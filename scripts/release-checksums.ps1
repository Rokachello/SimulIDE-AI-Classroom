param([string] $OutputRoot = (Join-Path (Split-Path $PSScriptRoot -Parent) 'dist'))
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'runtime-inventory.ps1')
$files = @('SimulIDE-AI-Windows.zip', 'SimulIDE-AI-Source.zip', 'build-info.json')
$lines = foreach ($name in $files) {
    $path = Join-Path $OutputRoot $name
    if (-not (Test-Path -LiteralPath $path)) { throw "Za izdajo manjka $name." }
    '{0}  {1}' -f (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant(), $name
}
[IO.File]::WriteAllLines((Join-Path $OutputRoot 'SHA256SUMS.txt'), [string[]] $lines, (New-Object Text.UTF8Encoding $false))
Write-Host 'Kontrolne vsote ZIP-ov in porocila so v dist/SHA256SUMS.txt.'
