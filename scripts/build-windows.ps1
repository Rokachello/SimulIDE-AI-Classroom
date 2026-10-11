param([string] $QtBin, [string] $MingwBin, [string] $TlsBin, [string] $CrtBin)
$ErrorActionPreference = "Stop"
$srcRoot = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot 'windows-common.ps1')
if (-not $script:SetupLog) { Initialize-SetupLog $srcRoot }
if (-not $QtBin) { $QtBin = Split-Path (Get-Command qmake.exe -ErrorAction Stop).Source -Parent }
if (-not $MingwBin) { $MingwBin = Split-Path (Get-Command mingw32-make.exe -ErrorAction Stop).Source -Parent }
if (-not $TlsBin) { throw 'Za gradnjo podaj mapo OpenSSL knjiznic ali uporabi ZAZENI.cmd.' }
if (-not $CrtBin) { throw 'Za gradnjo podaj mapo Visual C++ runtime knjiznic ali uporabi ZAZENI.cmd.' }
$env:PATH = "$QtBin;$MingwBin;$env:PATH"
Get-ChildItem "$srcRoot/resources/translations" -Filter *.ts -Recurse | ForEach-Object {
    Invoke-Checked (Join-Path $QtBin 'lrelease.exe') @($_.FullName, "-qm", "$srcRoot/resources/qm/$($_.BaseName).qm") 'Priprava prevodov'
}
$buildDir = "$srcRoot/build_AI/objects-build"
New-Item -ItemType Directory -Force $buildDir | Out-Null
Push-Location $buildDir
try {
    Invoke-Checked (Join-Path $QtBin 'qmake.exe') @("$srcRoot/AI.pro") 'Priprava gradnje Qt'
    # The launcher compares contents, while make only compares timestamps. A ZIP
    # extraction or editor can preserve mtimes: discard objects whenever the
    # launcher requests a build so those changed sources cannot stay stale.
    Invoke-Checked (Join-Path $MingwBin 'mingw32-make.exe') @('clean') 'Ciscenje gradilnih objektov'
    Invoke-Checked (Join-Path $MingwBin 'mingw32-make.exe') @('-j4') 'Gradnja SimulIDE'
} finally { Pop-Location }
. (Join-Path $PSScriptRoot 'runtime-inventory.ps1')
$outputDir = "$srcRoot/build_AI/executables/SimulIDE_2.0.0-"
Copy-Item "$srcRoot/resources/data" $outputDir -Recurse -Force
# Use the actual downloaded Qt paths instead of the deployment tool's compiled prefix.
$qtBin = $QtBin
$qtPrefix = Split-Path $qtBin -Parent
$mingwBin = $MingwBin
$platformPlugin = Join-Path $qtPrefix "plugins/platforms/qwindows.dll"
if (!(Test-Path -LiteralPath $platformPlugin)) {
    $matches = @(Get-ChildItem -LiteralPath $qtPrefix -Recurse -File -Filter "qwindows.dll")
    if ($matches.Count -eq 0) { throw "Qt ne vsebuje qwindows.dll. Preveri prenos qtbase: $qtPrefix" }
    $platformPlugin = $matches[0].FullName
}
$pluginSource = Split-Path (Split-Path $platformPlugin -Parent) -Parent
New-Item -ItemType Directory -Force "$outputDir/plugins" | Out-Null
Get-ChildItem -LiteralPath $qtBin -Filter "*.dll" -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $outputDir -Force
}
Get-ChildItem -LiteralPath $mingwBin -Filter "*.dll" -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $outputDir -Force
}
Get-ChildItem -LiteralPath $TlsBin -Filter '*.dll' -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $outputDir -Force
}
foreach ($file in @('vcruntime140.dll', 'vcruntime140_1.dll')) {
    Copy-Item -LiteralPath (Join-Path $CrtBin $file) -Destination $outputDir -Force
}
Get-ChildItem -LiteralPath $pluginSource | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination "$outputDir/plugins" -Recurse -Force
}
Set-Content -LiteralPath "$outputDir/qt.conf" -Encoding ASCII -Value "[Paths]`r`nPrefix=.`r`nPlugins=plugins"
foreach ($file in @("Qt5Core.dll", "Qt5Gui.dll", "Qt5Widgets.dll", "Qt5Network.dll", "Qt5Multimedia.dll", "Qt5SerialPort.dll", "Qt5Svg.dll", "Qt5Xml.dll", "libstdc++-6.dll", "libgcc_s_seh-1.dll", "libwinpthread-1.dll", "plugins/platforms/qwindows.dll", "libssl-1_1-x64.dll", "libcrypto-1_1-x64.dll", "vcruntime140.dll", "vcruntime140_1.dll")) {
    if (!(Test-Path -LiteralPath (Join-Path $outputDir $file))) { throw "Manjka datoteka za zagon: $file" }
}
if (Test-Path (Join-Path $CrtBin 'LICENSE.txt')) {
    New-Item -ItemType Directory -Force (Join-Path $outputDir 'licenses/Python-runtime') | Out-Null
    Copy-Item -LiteralPath (Join-Path $CrtBin 'LICENSE.txt') -Destination (Join-Path $outputDir 'licenses/Python-runtime') -Force
}
# Preserve the notices shipped by the actual Qt, GCC/MinGW and OpenSSL archives.
foreach ($component in @(@('Qt', $qtPrefix), @('MinGW', (Split-Path $mingwBin -Parent)), @('OpenSSL', (Split-Path $TlsBin -Parent)))) {
    $licenseRoot = Join-Path $outputDir ("licenses/" + $component[0])
    foreach ($notice in (Get-ChildItem -LiteralPath $component[1] -Recurse -File | Where-Object { $_.Name -match '^(LICENSE|LICENCE|COPYING|COPYRIGHT|NOTICE)' })) {
        $relative = $notice.FullName.Substring($component[1].Length).TrimStart('\', '/')
        $target = Join-Path $licenseRoot $relative
        New-Item -ItemType Directory -Force (Split-Path $target -Parent) | Out-Null
        Copy-Item -LiteralPath $notice.FullName -Destination $target -Force
    }
}
$inventory = @(Get-RuntimeInventory $outputDir)
# Record the actual origins, including cached DLLs; a filename/version alone does
# not establish byte identity. Later copy operations take precedence over Qt.
$origins = @(@('CRT', $CrtBin), @('TLS', $TlsBin), @('MinGW', $MingwBin), @('Qt', $qtBin))
foreach ($entry in $inventory) {
    $origin = 'unmatched-existing-file'
    if ($entry.path -eq 'simulide.exe') { $origin = 'this-source-build' }
    elseif ($entry.path.StartsWith('plugins/')) {
        $sourceFile = Join-Path $pluginSource $entry.path.Substring(8)
        if ((Test-Path -LiteralPath $sourceFile) -and (Get-FileHash -LiteralPath $sourceFile).Hash.ToLowerInvariant() -eq $entry.sha256) { $origin = 'Qt/plugins' }
    } else {
        foreach ($component in $origins) {
            $sourceFile = Join-Path $component[1] $entry.path
            if ((Test-Path -LiteralPath $sourceFile) -and (Get-FileHash -LiteralPath $sourceFile).Hash.ToLowerInvariant() -eq $entry.sha256) { $origin = $component[0]; break }
        }
    }
    $entry | Add-Member -NotePropertyName origin -NotePropertyValue $origin
}
$sourceRevision = Get-SourceRevision $srcRoot
$fullCommit = $null
if ($sourceRevision -ne 'unknown') {
    $commit = Invoke-Probe 'git' @('-C', $srcRoot, 'rev-parse', 'HEAD')
    if ($commit.Code -eq 0 -and $commit.Output -match '^[0-9a-f]{40}$') { $fullCommit = $commit.Output }
}
Write-JsonFile (Join-Path $outputDir 'build-info.json') ([ordered]@{
    schema = 1
    source_revision = $sourceRevision
    source_commit = $fullCommit
    source_url = if ($fullCommit) { "https://github.com/Rokachello/SimulIDE-AI-Classroom/tree/$fullCommit" } else { $null }
    built_at_utc = [DateTime]::UtcNow.ToString('o')
    qt_version = (Invoke-Probe (Join-Path $QtBin 'qmake.exe') @('-query', 'QT_VERSION')).Output
    compiler_version = (Invoke-Probe (Join-Path $MingwBin 'g++.exe') @('-dumpfullversion')).Output
    compiler_target = (Invoke-Probe (Join-Path $MingwBin 'g++.exe') @('-dumpmachine')).Output
    build_command = 'qmake AI.pro; mingw32-make clean; mingw32-make -j4'
    workflow_run = if ($env:GITHUB_ACTIONS) { "https://github.com/$env:GITHUB_REPOSITORY/actions/runs/$env:GITHUB_RUN_ID" } else { $null }
    workflow_ref = $env:GITHUB_WORKFLOW_REF
    workflow_sha = $env:GITHUB_WORKFLOW_SHA
    runner_os = [Environment]::OSVersion.VersionString
    powershell_version = $PSVersionTable.PSVersion.ToString()
    runtime = $inventory
})
Write-SetupLog "Prevedeni program: $outputDir/simulide.exe"
