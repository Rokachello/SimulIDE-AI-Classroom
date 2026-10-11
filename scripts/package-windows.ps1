param([string] $SourceRoot = (Split-Path $PSScriptRoot -Parent), [string] $OutputRoot)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'windows-common.ps1')
. (Join-Path $PSScriptRoot 'runtime-inventory.ps1')
if (-not $OutputRoot) { $OutputRoot = Join-Path $SourceRoot 'dist' }
$built = Join-Path $SourceRoot 'build_AI/executables/SimulIDE_2.0.0-'
$stage = Join-Path $OutputRoot 'student-package'
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
New-Item -ItemType Directory -Force (Join-Path $stage 'bin'), (Join-Path $stage 'scripts') | Out-Null
# Allowlist: never recursively copy the checkout, build folder or server runtime.
foreach ($file in @('simulide.exe', 'qt.conf')) {
    Copy-Item -LiteralPath (Join-Path $built $file) -Destination (Join-Path $stage 'bin')
}
if (Test-Path -LiteralPath (Join-Path $built 'build-info.json')) {
    Copy-Item -LiteralPath (Join-Path $built 'build-info.json') -Destination $stage
}
Get-ChildItem -LiteralPath $built -Filter '*.dll' -File | Copy-Item -Destination (Join-Path $stage 'bin')
Copy-Item -LiteralPath (Join-Path $built 'plugins') -Destination (Join-Path $stage 'bin') -Recurse
Copy-Item -LiteralPath (Join-Path $SourceRoot 'resources/data') -Destination (Join-Path $stage 'bin') -Recurse
if (Test-Path (Join-Path $built 'licenses')) { Copy-Item -LiteralPath (Join-Path $built 'licenses') -Destination $stage -Recurse }
Copy-Item -LiteralPath (Join-Path $SourceRoot 'third_party/windows-notices') -Destination (Join-Path $stage 'licenses') -Recurse
Copy-Item -LiteralPath (Join-Path $SourceRoot 'ZAZENI.cmd') -Destination $stage
foreach ($file in @('zazeni.ps1', 'windows-common.ps1')) {
    Copy-Item -LiteralPath (Join-Path $SourceRoot "scripts/$file") -Destination (Join-Path $stage 'scripts')
}
foreach ($file in @('LICENSE-GPL-3.0.txt', 'LICENSE-AGPL-3.0.txt', 'COPYING', 'copyright.txt')) {
    Copy-Item -LiteralPath (Join-Path $SourceRoot $file) -Destination $stage
}
$revision = Get-SourceRevision $SourceRoot
@"
SimulIDE AI 0.12 (Git $revision)
Razsiri celoten ZIP v zapisljivo mapo in dvoklikni ZAZENI.cmd.
Ta studentski paket je ze preveden; ne potrebuje Qt, MinGW ali Python namestitve.
Naslov uciteljskega streznika in studentski racun dobis pri ucitelju.
API kljuc, uciteljeve nastavitve in podatkovna baza niso del tega paketa.
Izvorna koda in licence: https://github.com/Rokachello/SimulIDE-AI-Classroom
Za isto revizijo: https://github.com/Rokachello/SimulIDE-AI-Classroom/tree/$revision
Za posodobitev prevedenega paketa prenesi novo izdajo in razsiri celoten ZIP.
POSODOBI.cmd je namenjen Git klonu izvorne kode.
"@ | Set-Content -LiteralPath (Join-Path $stage 'PREBERI.txt') -Encoding UTF8
Write-FileChecksums $stage (Join-Path $stage 'FILES-SHA256SUMS.txt')
$archive = Join-Path $OutputRoot 'SimulIDE-AI-Windows.zip'
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $archive -Force
Write-Host "Studentski prenosni paket: $archive"
