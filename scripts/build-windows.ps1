$ErrorActionPreference = "Stop"
$srcRoot = Split-Path $PSScriptRoot -Parent
function Run-Checked([string] $Program, [string[]] $Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed ($LASTEXITCODE)" }
}
Get-ChildItem "$srcRoot/resources/translations" -Filter *.ts -Recurse | ForEach-Object {
    Run-Checked "lrelease" @($_.FullName, "-qm", "$srcRoot/resources/qm/$($_.BaseName).qm")
}
$buildDir = "$srcRoot/build_AI/objects-build"
New-Item -ItemType Directory -Force $buildDir | Out-Null
Push-Location $buildDir
try {
    Run-Checked "qmake" @("$srcRoot/AI.pro")
    Run-Checked "mingw32-make" @("-j4")
} finally { Pop-Location }
$outputDir = "$srcRoot/build_AI/executables/SimulIDE_2.0.0-"
Copy-Item "$srcRoot/resources/data" $outputDir -Recurse -Force
# Use the actual downloaded Qt paths instead of the deployment tool's compiled prefix.
$qtBin = Split-Path (Get-Command "qmake.exe" -ErrorAction Stop).Source -Parent
$qtPrefix = Split-Path $qtBin -Parent
$mingwBin = Split-Path (Get-Command "mingw32-make.exe" -ErrorAction Stop).Source -Parent
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
Get-ChildItem -LiteralPath $pluginSource | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination "$outputDir/plugins" -Recurse -Force
}
Set-Content -LiteralPath "$outputDir/qt.conf" -Encoding ASCII -Value "[Paths]`r`nPrefix=.`r`nPlugins=plugins"
foreach ($file in @("Qt5Core.dll", "Qt5Gui.dll", "Qt5Widgets.dll", "Qt5Network.dll", "Qt5Multimedia.dll", "Qt5SerialPort.dll", "Qt5Svg.dll", "Qt5Xml.dll", "libstdc++-6.dll", "libgcc_s_seh-1.dll", "libwinpthread-1.dll", "plugins/platforms/qwindows.dll")) {
    if (!(Test-Path -LiteralPath (Join-Path $outputDir $file))) { throw "Manjka datoteka za zagon: $file" }
}
Write-Host "Built program: $outputDir/simulide.exe"
Write-Host "Qt gradnja je koncana. Zaganjalnik nato pripravi TLS knjiznice."
