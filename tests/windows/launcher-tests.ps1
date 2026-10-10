# Windows-independent control-flow tests; no downloads, compiler or classroom credentials.
$ErrorActionPreference = 'Stop'
$repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
. (Join-Path $repo 'scripts/windows-common.ps1')
$temp = Join-Path ([IO.Path]::GetTempPath()) ('simulide-launcher-' + [Guid]::NewGuid())
New-Item -ItemType Directory -Force $temp | Out-Null
$script:checks = 0
function Assert-True($Condition, [string] $Message) {
    if (-not $Condition) { throw "FAIL: $Message" }
    $script:checks++
    Write-Host "PASS: $Message"
}
function Assert-Throws([scriptblock] $Action, [string] $Message) {
    $failed = $false
    try { & $Action } catch { $failed = $true }
    Assert-True $failed $Message
}
function Invoke-FixtureGit([string[]] $Arguments) {
    # Empty-repository clone warnings are stderr; PS 5.1 must not treat them as failure.
    Invoke-Checked 'git' $Arguments 'Priprava testnega Git repozitorija'
}
try {
    $source = Join-Path $temp 'source with spaces'
    New-Item -ItemType Directory -Force "$source/src", "$source/resources", "$source/scripts" | Out-Null
    Set-Content "$source/src/main.cpp" 'original'
    Set-Content "$source/AI.pro" 'project'
    Set-Content "$source/SimulIDE.pri" 'include'
    Initialize-SetupLog $source
    $script:builds = 0
    $script:failBuild = $false
    $script:failTls = $false
    function Invoke-DesktopCompile([string] $Root, $Tools) {
        $script:builds++
        if ($script:failBuild) { throw 'Compiler fixture failure' }
        New-Item -ItemType Directory -Force "$Root/build_AI/executables/SimulIDE_2.0.0-" | Out-Null
        Set-Content "$Root/build_AI/executables/SimulIDE_2.0.0-/simulide.exe" 'fixture'
        $out = "$Root/build_AI/executables/SimulIDE_2.0.0-"
        New-Item -ItemType Directory -Force "$out/plugins/platforms" | Out-Null
        foreach ($file in @('Qt5Core.dll', 'Qt5Widgets.dll', 'Qt5Network.dll', 'libstdc++-6.dll', 'libgcc_s_seh-1.dll', 'libwinpthread-1.dll', 'plugins/platforms/qwindows.dll', 'libssl-1_1-x64.dll', 'libcrypto-1_1-x64.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'qt.conf')) {
            Set-Content (Join-Path $out $file) 'fixture'
        }
    }
    function Test-DesktopRuntime([string] $Binary) { if ($script:failTls) { throw 'TLS fixture failure' } }
    $tools = [PSCustomObject]@{ QtBin = 'qt'; MingwBin = 'gcc'; TlsBin = 'tls' }
    Set-Content "$source/ready-v012.txt" 'obsolete'
    $binary = Invoke-DesktopBuild $source $tools
    Assert-True ($script:builds -eq 1 -and $binary.StartsWith($source)) 'first build uses this checkout and ignores ready-v012.txt'
    $null = Invoke-DesktopBuild $source $tools
    Assert-True ($script:builds -eq 1) 'unchanged inputs skip compilation'
    $mtime = (Get-Item "$source/src/main.cpp").LastWriteTimeUtc
    Set-Content "$source/src/main.cpp" 'changed '
    (Get-Item "$source/src/main.cpp").LastWriteTimeUtc = $mtime
    $null = Invoke-DesktopBuild $source $tools
    Assert-True ($script:builds -eq 2) 'content change rebuilds even with unchanged timestamp'
    Remove-Item -LiteralPath $binary
    $null = Invoke-DesktopBuild $source $tools
    Assert-True ($script:builds -eq 3) 'missing local binary forces compilation'
    Set-Content "$source/resources/new.xml" '<data/>'
    $script:failBuild = $true
    Assert-Throws { Invoke-DesktopBuild $source $tools } 'compiler failure stops launch'
    Assert-True (-not (Test-Path "$source/build_AI/source-ready.sha256")) 'failed build invalidates readiness'
    $script:failBuild = $false
    $null = Invoke-DesktopBuild $source $tools
    Assert-True ($script:builds -eq 5) 'retry after failure recompiles'
    Remove-Item "$source/resources/new.xml"
    $null = Invoke-DesktopBuild $source $tools
    Assert-True ($script:builds -eq 6) 'removed input forces compilation'
    $script:failTls = $true
    Assert-Throws { Invoke-DesktopBuild $source $tools } 'TLS failure stops unchanged launch'
    Assert-True (-not (Test-Path "$source/build_AI/source-ready.sha256")) 'TLS failure invalidates readiness'
    $script:failTls = $false
    $null = Invoke-DesktopBuild $source $tools
    Assert-True ($script:builds -eq 7) 'deployment is rebuilt after a TLS failure'
    Remove-Item "$source/build_AI/executables/SimulIDE_2.0.0-/plugins/platforms/qwindows.dll"
    $null = Invoke-DesktopBuild $source $tools
    Assert-True ($script:builds -eq 8) 'missing Qt platform plugin forces deployment repair'
    New-Item -ItemType Directory -Force "$source/resources/qm" | Out-Null
    Set-Content "$source/resources/qm/generated.qm" 'generated'
    $null = Invoke-DesktopBuild $source $tools
    Assert-True ($script:builds -eq 8) 'generated translations do not invalidate the no-change launch'
    # Check the real native command exit-status handling (not the compiler mock).
    $shell = (Get-Process -Id $PID).Path
    Assert-Throws { Invoke-Checked $shell @('-NoProfile', '-Command', 'exit 7') 'Testni ukaz' } 'nonzero native exit is propagated'
    Assert-Throws { Invoke-Checked 'nonexistent-simulide-command' @() 'Testni ukaz' } 'missing external command fails instead of inheriting a stale exit code'

    . (Join-Path $repo 'scripts/windows-tools.ps1')
    $cachedArchive = Join-Path $temp 'cached-archive.zip'
    Set-Content $cachedArchive 'verified fixture'
    $cachedHash = (Get-FileHash -LiteralPath $cachedArchive -Algorithm SHA256).Hash
    Get-VerifiedArchive 'https://example.invalid/never-requested.zip' $cachedArchive $cachedHash
    Assert-True (Test-Path $cachedArchive) 'verified cached downloads are reused without a network request'
    Assert-Throws { Get-VerifiedArchive 'https://example.invalid/never-requested.zip' $cachedArchive ('0' * 64) } 'a mismatched archive hash stops setup before extraction'
    $crtFixture = Join-Path $temp 'crt'
    New-Item -ItemType Directory -Force $crtFixture | Out-Null
    $bytes = New-Object byte[] 256
    $bytes[0] = 0x4D; $bytes[1] = 0x5A; $bytes[0x3C] = 0x80
    $bytes[0x80] = 0x50; $bytes[0x81] = 0x45
    $bytes[0x84] = 0x4C; $bytes[0x85] = 0x01
    foreach ($file in @('vcruntime140.dll', 'vcruntime140_1.dll')) { [IO.File]::WriteAllBytes((Join-Path $crtFixture $file), $bytes) }
    Assert-True (-not (Find-CrtBin $crtFixture)) '32-bit CRT cache is not reused by the x64 desktop'
    $bytes[0x84] = 0x64; $bytes[0x85] = 0x86
    foreach ($file in @('vcruntime140.dll', 'vcruntime140_1.dll')) { [IO.File]::WriteAllBytes((Join-Path $crtFixture $file), $bytes) }
    Assert-True ((Find-CrtBin $crtFixture) -eq $crtFixture) 'x64 CRT pair is reused from the existing cache'

    $local = Join-Path $temp 'local'
    $server = Join-Path $temp 'server'
    $legacy = Join-Path $local 'SimulIDE-AI-V0.2/classroom-data'
    New-Item -ItemType Directory -Force $legacy, "$server/data" | Out-Null
    Set-Content "$legacy/classroom.sqlite3" 'existing database'
    Assert-True ((Get-ClassroomDataPath $server $local '') -eq $legacy) 'legacy classroom database is reused'
    Set-Content "$server/data/classroom.sqlite3" 'second database'
    Assert-Throws { Get-ClassroomDataPath $server $local '' } 'ambiguous databases stop rather than create or replace data'
    Assert-True ((Get-ClassroomDataPath $server $local "$server/data") -eq [IO.Path]::GetFullPath("$server/data")) 'explicit data selection is preserved'
    Assert-True ((Get-Content "$legacy/classroom.sqlite3") -eq 'existing database') 'data selection leaves the original database unchanged'

    # Exercise ff-only with actual disposable Git repositories, including divergence.
    $remote = Join-Path $temp 'remote.git'
    $author = Join-Path $temp 'author'
    $checkout = Join-Path $temp 'checkout'
    Invoke-FixtureGit @('init', '--bare', $remote)
    Invoke-FixtureGit @('clone', $remote, $author)
    Invoke-FixtureGit @('-C', $author, 'config', 'user.name', 'Test')
    Invoke-FixtureGit @('-C', $author, 'config', 'user.email', 'test@example.invalid')
    Set-Content "$author/file.txt" 'first'
    Invoke-FixtureGit @('-C', $author, 'add', '.')
    Invoke-FixtureGit @('-C', $author, 'commit', '-m', 'first')
    Invoke-FixtureGit @('-C', $author, 'push', 'origin', 'HEAD')
    Invoke-FixtureGit @('clone', $remote, $checkout)
    Invoke-FixtureGit @('-C', $checkout, 'config', 'user.name', 'Test')
    Invoke-FixtureGit @('-C', $checkout, 'config', 'user.email', 'test@example.invalid')
    Set-Content "$author/file.txt" 'second'
    Invoke-FixtureGit @('-C', $author, 'commit', '-am', 'second')
    Invoke-FixtureGit @('-C', $author, 'push')
    Invoke-RepositoryUpdate $checkout
    Assert-True ((Get-Content "$checkout/file.txt") -eq 'second') 'clean checkout updates via fast-forward'
    Set-Content "$checkout/file.txt" 'local edit'
    Assert-Throws { Invoke-RepositoryUpdate $checkout } 'local edits stop update'
    Assert-True ((Get-Content "$checkout/file.txt") -eq 'local edit') 'update preserves local edits'
    # Restore only our disposable fixture edit, never user files.
    Invoke-FixtureGit @('-C', $checkout, 'restore', 'file.txt')
    Set-Content "$checkout/new.txt" 'untracked'
    Assert-Throws { Invoke-RepositoryUpdate $checkout } 'untracked files stop update'
    Remove-Item "$checkout/new.txt"
    Set-Content "$checkout/file.txt" 'local commit'
    Invoke-FixtureGit @('-C', $checkout, 'commit', '-am', 'local')
    Set-Content "$author/file.txt" 'remote commit'
    Invoke-FixtureGit @('-C', $author, 'commit', '-am', 'remote')
    Invoke-FixtureGit @('-C', $author, 'push')
    $before = & git -C $checkout rev-parse HEAD
    Assert-Throws { Invoke-RepositoryUpdate $checkout } 'divergent history stops ff-only update'
    Assert-True ((& git -C $checkout rev-parse HEAD) -eq $before) 'failed ff-only update preserves local HEAD'
    Invoke-FixtureGit @('-C', $checkout, 'remote', 'set-url', 'origin', (Join-Path $temp 'nonexistent.git'))
    Assert-Throws { Invoke-RepositoryUpdate $checkout } 'unavailable remote stops update'
    Assert-Throws { Invoke-RepositoryUpdate $source } 'source ZIP without Git metadata cannot be updated'
    $nestedSource = Join-Path $author 'nested-source-zip'
    New-Item -ItemType Directory -Force $nestedSource | Out-Null
    Assert-True ((Get-SourceRevision $nestedSource) -eq 'unknown') 'source ZIP inside another repository does not inherit its Git commit'

    # Packaging must select public desktop files despite private data in the fixture.
    $built = "$source/build_AI/executables/SimulIDE_2.0.0-"
    New-Item -ItemType Directory -Force "$built/plugins/platforms", "$source/third_party/windows-notices", "$source/server" | Out-Null
    Set-Content "$built/qt.conf" '[Paths]'
    Set-Content "$built/Qt5Core.dll" 'fixture'
    Set-Content "$built/plugins/platforms/qwindows.dll" 'fixture'
    Set-Content "$source/server/classroom.sqlite3" 'private'
    Set-Content "$source/.env" 'OPENAI_API_KEY=private-fixture'
    foreach ($file in @('ZAZENI.cmd', 'LICENSE-GPL-3.0.txt', 'LICENSE-AGPL-3.0.txt', 'COPYING', 'copyright.txt')) { Copy-Item "$repo/$file" $source }
    foreach ($file in @('zazeni.ps1', 'windows-common.ps1')) { Copy-Item "$repo/scripts/$file" "$source/scripts" }
    New-Item -ItemType Directory -Force "$source/resources/data" | Out-Null
    Set-Content "$source/resources/data/public.xml" '<public/>'
    Set-Content "$source/third_party/windows-notices/LICENSE.txt" 'fixture license'
    & "$repo/scripts/package-windows.ps1" -SourceRoot $source -OutputRoot "$temp/package"
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead("$temp/package/SimulIDE-AI-Windows.zip")
    try {
        $entries = @($zip.Entries.FullName | ForEach-Object { $_.Replace('\', '/') })
        Assert-True ($entries -contains 'ZAZENI.cmd' -and $entries -contains 'bin/simulide.exe') 'portable package includes the launcher and desktop binary'
        Assert-True (-not ($entries | Where-Object { $_ -match 'server|\.sqlite|\.env|classroom-data|STREZNIK|POSODOBI' })) 'student ZIP excludes server, credentials, databases and update launcher'
        Assert-True ($entries -contains 'LICENSE-GPL-3.0.txt' -and $entries -contains 'LICENSE-AGPL-3.0.txt') 'portable package retains project license notices'
    } finally { $zip.Dispose() }
    Write-Host "PASS: $script:checks checks; Windows runtime/download/build still requires the Windows CI job."
    Write-Host "::notice::PASS: $script:checks launcher checks completed."
} catch {
    # Publish the actual failure as a CI annotation, as well as preserving the console error.
    $message = $_.Exception.Message.Replace('%', '%25').Replace("`r", '%0D').Replace("`n", '%0A')
    Write-Host "::error::$message"
    throw
} finally { Remove-Item -LiteralPath $temp -Recurse -Force }
# GitHub's shell wrapper propagates LASTEXITCODE, including deliberately failed
# native commands asserted above. Reaching here means every assertion succeeded.
exit 0
