$ErrorActionPreference = 'Stop'
$repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
. (Join-Path $repo 'scripts/windows-common.ps1')
. (Join-Path $repo 'scripts/runtime-inventory.ps1')
$temp = Join-Path ([IO.Path]::GetTempPath()) ('simulide-release-' + [Guid]::NewGuid())
New-Item -ItemType Directory -Force $temp | Out-Null
$checks = 0
function Assert-Release($Condition, [string] $Message) {
    if (-not $Condition) { throw "FAIL: $Message" }
    $script:checks++
    Write-Host "PASS: $Message"
}
try {
    $fixture = Join-Path $temp 'public source'
    New-Item -ItemType Directory -Force $fixture | Out-Null
    Invoke-Checked git @('init', $fixture) 'Git test'
    Invoke-Checked git @('-C', $fixture, 'config', 'user.email', 'test@example.invalid') 'Git test'
    Invoke-Checked git @('-C', $fixture, 'config', 'user.name', 'Test') 'Git test'
    Set-Content (Join-Path $fixture 'ZAZENI.cmd') 'fixture'
    Set-Content (Join-Path $fixture '.gitignore') "dist/`n.env"
    Invoke-Checked git @('-C', $fixture, 'add', '.') 'Git test'
    Invoke-Checked git @('-C', $fixture, 'commit', '-m', 'Public source fixture') 'Git test'
    Set-Content (Join-Path $fixture '.env') 'private test fixture'
    & (Join-Path $repo 'scripts/package-source.ps1') -SourceRoot $fixture -OutputRoot (Join-Path $temp 'out')
    $stage = Join-Path $temp 'out/source-package'
    Assert-Release ((Test-Path "$stage/ZAZENI.cmd") -and (Test-Path "$stage/.gitignore")) 'source ZIP contains the entrypoint and Git dotfiles'
    Assert-Release (-not (Test-Path "$stage/.env") -and -not (Test-Path "$stage/.git")) 'source export excludes local credentials and Git internals'
    $commit = (& git -C $fixture rev-parse HEAD).Trim()
    Assert-Release ((Get-Content "$stage/PREBERI-IZVOR.txt" -Raw).Contains($commit)) 'source instructions identify the full exported commit'
    Assert-Release ((Get-Content "$stage/SOURCE-FILES-SHA256SUMS.txt" -Raw).Contains('.gitignore')) 'source files have content checksums including dotfiles'
    # Inspect the actual ZIP, not only the staging directory.
    Expand-Archive "$temp/out/SimulIDE-AI-Source.zip" "$temp/extracted"
    Assert-Release ((Test-Path "$temp/extracted/.gitignore") -and -not (Test-Path "$temp/extracted/.env")) 'the final source archive retains dotfiles and omits private files'
    Set-Content "$fixture/ZAZENI.cmd" 'local modification'
    $failed = $false
    try { & (Join-Path $repo 'scripts/package-source.ps1') -SourceRoot $fixture -OutputRoot "$temp/rejected" } catch { $failed = $true }
    Assert-Release $failed 'source exporter rejects a dirty tracked tree instead of labeling it as a clean commit'

    $binaryRoot = Join-Path $temp 'passive'
    New-Item -ItemType Directory -Force "$binaryRoot/plugins/platforms" | Out-Null
    $bytes = New-Object byte[] 256
    $bytes[0] = 0x4D; $bytes[1] = 0x5A; $bytes[0x3C] = 0x80
    $bytes[0x80] = 0x50; $bytes[0x81] = 0x45; $bytes[0x84] = 0x64; $bytes[0x85] = 0x86
    [IO.File]::WriteAllBytes("$binaryRoot/simulide.exe", $bytes)
    [IO.File]::WriteAllBytes("$binaryRoot/plugins/platforms/qwindows.dll", $bytes)
    $inventory = @(Get-RuntimeInventory $binaryRoot)
    Assert-Release ($inventory.Count -eq 2 -and $inventory[0].architecture -eq 'x64') 'passive inventory reads PE architecture and includes nested plugins'
    Assert-Release ($inventory[0].sha256 -eq (Get-FileHash "$binaryRoot/plugins/platforms/qwindows.dll").Hash.ToLowerInvariant()) 'inventory records exact file SHA256 without executing the fixture'
    Assert-Release ($inventory[0].path -eq 'plugins/platforms/qwindows.dll') 'inventory paths are relative and do not reveal the user profile'
    & (Join-Path $repo 'scripts/review-windows.ps1') -CurrentRoot $binaryRoot -PreviousRoot $binaryRoot -OutputRoot "$temp/review"
    $comparison = Import-Csv "$temp/review/runtime-comparison.csv"
    Assert-Release (@($comparison | Where-Object { $_.status -eq 'identical' }).Count -eq 2) 'passive comparison identifies identical EXE and DLL bytes'
    $bytes[200] = 1
    [IO.File]::WriteAllBytes("$binaryRoot/simulide.exe", $bytes)
    $modified = @(Get-RuntimeInventory $binaryRoot)
    Assert-Release (($modified | Where-Object { $_.path -eq 'simulide.exe' }).sha256 -ne ($inventory | Where-Object { $_.path -eq 'simulide.exe' }).sha256) 'a binary content change is visible in the inventory'
    $out = Join-Path $temp 'out'
    Copy-Item "$out/SimulIDE-AI-Source.zip" "$out/SimulIDE-AI-Windows.zip"
    Write-JsonFile "$out/build-info.json" @{ runtime = $inventory }
    & (Join-Path $repo 'scripts/release-checksums.ps1') -OutputRoot $out
    $sums = Get-Content "$out/SHA256SUMS.txt"
    Assert-Release ($sums.Count -eq 3 -and $sums[2] -eq ((Get-FileHash "$out/build-info.json").Hash.ToLowerInvariant() + '  build-info.json')) 'release sums cover both ZIPs and the machine-readable inventory'
    Remove-Item "$out/build-info.json"
    $failed = $false
    try { & (Join-Path $repo 'scripts/release-checksums.ps1') -OutputRoot $out } catch { $failed = $true }
    Assert-Release $failed 'incomplete release assets stop checksum generation'
    Write-Host "::notice::PASS: $checks release checks completed."
} finally { Remove-Item -LiteralPath $temp -Recurse -Force }
exit 0
