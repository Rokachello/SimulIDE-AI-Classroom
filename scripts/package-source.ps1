param([string] $SourceRoot = (Split-Path $PSScriptRoot -Parent), [string] $OutputRoot)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'windows-common.ps1')
. (Join-Path $PSScriptRoot 'runtime-inventory.ps1')
if (-not $OutputRoot) { $OutputRoot = Join-Path $SourceRoot 'dist' }
$probe = Invoke-Probe 'git' @('-C', $SourceRoot, 'rev-parse', '--show-toplevel')
if ($probe.Code -ne 0 -or [IO.Path]::GetFullPath($probe.Output) -ne [IO.Path]::GetFullPath($SourceRoot)) { throw 'Izvorni paket pripravi iz lastnega Git repozitorija.' }
$revision = Get-SourceRevision $SourceRoot
if ($revision -notmatch '^[a-f0-9]{12}$') { throw 'Izvorni paket zahteva cisto sledeno kodo. Najprej shrani spremembe v commit.' }
$commit = (Invoke-Probe 'git' @('-C', $SourceRoot, 'rev-parse', 'HEAD')).Output
New-Item -ItemType Directory -Force $OutputRoot | Out-Null
$stage = Join-Path $OutputRoot 'source-package'
$raw = Join-Path $OutputRoot 'source-git.zip'
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
Invoke-Checked 'git' @('-C', $SourceRoot, 'archive', '--format=zip', "--output=$raw", $commit) 'Izvoz javne izvorne kode'
Expand-Archive -LiteralPath $raw -DestinationPath $stage
Remove-Item -LiteralPath $raw
# Git archive exports tracked public files, never the tools cache or local data.
if (Get-ChildItem -LiteralPath $stage -Recurse -File -Force | Where-Object { $_.Extension -in @('.exe', '.dll', '.sqlite', '.sqlite3', '.db') -or $_.Name -eq '.env' }) { throw 'Izvorni paket vsebuje nepricakovano binarno ali zasebno datoteko.' }
@"
SimulIDE AI 0.12 - IZVORNA KODA ZA LOKALNO GRADNJO
Commit: $commit
https://github.com/Rokachello/SimulIDE-AI-Classroom/tree/$commit

Razsiri celoten ZIP v novo zapisljivo mapo in dvoklikni ZAZENI.cmd.
Program se prevede iz te mape; ni prilozenega CI simulide.exe ali DLL-jev.
Orodja ponovno uporabi iz %LOCALAPPDATA%\SimulIDE-AI-V0.2\tools.
Ce so orodja popolna, jih ne prenasa; manjkajoce pripravi iz uradnih virov.
TLS pregled je enak kot v prevedenem paketu in se ne preskoci.
Naslov programa iz ZIP-a brez .git ima Git unknown; tocna revizija je zgoraj.
Spreminjanje kode zazna SHA256 vhodov in sprozi ponovno gradnjo.
Zascite ne izklapljaj in ne dodajaj izjem. Ob blokadi shrani zaznavo in setup.log.
Ne kopiraj starega programa, baze ali uciteljevih nastavitev v ta projekt.
"@ | Set-Content -LiteralPath (Join-Path $stage 'PREBERI-IZVOR.txt') -Encoding UTF8
Write-FileChecksums $stage (Join-Path $stage 'SOURCE-FILES-SHA256SUMS.txt')
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = Join-Path $OutputRoot 'SimulIDE-AI-Source.zip'
if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive }
# ZipFile includes dotfiles on Linux too; Compress-Archive can omit them.
[IO.Compression.ZipFile]::CreateFromDirectory($stage, $archive, [IO.Compression.CompressionLevel]::Optimal, $false)
Write-Host "Izvorni paket za lokalni prevod: $archive (Git $commit)"
