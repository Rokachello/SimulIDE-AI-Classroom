# Official Python/PyPI/Qt sources. TLS and archive verification stay enabled.
function Test-X64Library([string] $Path) {
    $reader = $null
    try {
        $reader = New-Object IO.BinaryReader ([IO.File]::OpenRead($Path))
        if ($reader.ReadUInt16() -ne 0x5A4D) { return $false }
        $null = $reader.BaseStream.Seek(0x3C, [IO.SeekOrigin]::Begin)
        $offset = $reader.ReadInt32()
        $null = $reader.BaseStream.Seek($offset, [IO.SeekOrigin]::Begin)
        return $reader.ReadUInt32() -eq 0x4550 -and $reader.ReadUInt16() -eq 0x8664
    } catch { return $false }
    finally { if ($null -ne $reader) { $reader.Dispose() } }
}

function Find-QtBin([string] $ToolsRoot) {
    foreach ($qmake in (Get-ChildItem -LiteralPath $ToolsRoot -Filter qmake.exe -Recurse -File -ErrorAction SilentlyContinue)) {
        if ($qmake.FullName -notmatch 'mingw81_64[\\/]bin[\\/]qmake.exe$') { continue }
        $probe = Invoke-Probe $qmake.FullName @('-query', 'QT_VERSION')
        if ($probe.Code -eq 0 -and $probe.Output -eq '5.15.2') {
            $complete = $true
            foreach ($file in @('lrelease.exe', 'Qt5Core.dll', 'Qt5Gui.dll', 'Qt5Widgets.dll', 'Qt5Network.dll', 'Qt5Svg.dll', 'Qt5Xml.dll', 'Qt5Concurrent.dll', 'Qt5SerialPort.dll', 'Qt5Multimedia.dll')) {
                if (-not (Test-Path (Join-Path $qmake.DirectoryName $file))) { $complete = $false }
            }
            if ($complete) { return $qmake.DirectoryName }
        }
    }
    return $null
}

function Find-CrtBin([string] $ToolsRoot) {
    foreach ($crt in (Get-ChildItem -LiteralPath $ToolsRoot -Filter vcruntime140.dll -Recurse -File -ErrorAction SilentlyContinue)) {
        $other = Join-Path $crt.DirectoryName 'vcruntime140_1.dll'
        if ((Test-Path $other) -and (Test-X64Library $crt.FullName) -and (Test-X64Library $other)) { return $crt.DirectoryName }
    }
    return $null
}

function Find-MingwBin([string] $ToolsRoot) {
    foreach ($gcc in (Get-ChildItem -LiteralPath $ToolsRoot -Filter g++.exe -Recurse -File -ErrorAction SilentlyContinue)) {
        $probe = Invoke-Probe $gcc.FullName @('-dumpfullversion')
        if ($probe.Code -eq 0 -and $probe.Output -eq '8.1.0' -and (Test-Path (Join-Path $gcc.DirectoryName 'mingw32-make.exe'))) {
            $arch = Invoke-Probe $gcc.FullName @('-dumpmachine')
            if ($arch.Code -eq 0 -and $arch.Output -eq 'x86_64-w64-mingw32') { return $gcc.DirectoryName }
        }
    }
    return $null
}

function Find-TlsBin([string] $ToolsRoot) {
    foreach ($ssl in (Get-ChildItem -LiteralPath $ToolsRoot -Filter libssl-1_1-x64.dll -Recurse -File -ErrorAction SilentlyContinue)) {
        if ($ssl.FullName -match '[\\/]tls-source-build[\\/]') { continue }
        if (Test-Path (Join-Path $ssl.DirectoryName 'libcrypto-1_1-x64.dll')) { return $ssl.DirectoryName }
    }
    return $null
}

function Get-VerifiedArchive([string] $Uri, [string] $Destination, [string] $Sha256) {
    if (-not (Test-Path -LiteralPath $Destination)) {
        Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $Destination -TimeoutSec 600
    }
    if ((Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash -ne $Sha256) {
        throw "Prenos $Destination ni prestal preverjanja SHA256. Datoteko odstrani in poskusi znova."
    }
}

function Build-LegacyTls([string] $ToolsRoot, [string] $MingwBin, [string] $Python) {
    # Qt 5.15.2 needs OpenSSL 1.1. Qt's current catalog only ships OpenSSL 3.
    # Build the last upstream 1.1.1 release rather than rename incompatible v3 DLLs.
    $work = Join-Path $ToolsRoot 'tls-source-build'
    $perlRoot = Join-Path $ToolsRoot 'strawberry-perl54231'
    $prefix = Join-Path $ToolsRoot 'OpenSSL111w'
    New-Item -ItemType Directory -Force $work, $perlRoot, $prefix | Out-Null
    $perl = Join-Path $perlRoot 'perl/bin/perl.exe'
    if (-not (Test-Path -LiteralPath $perl)) {
        Write-SetupLog 'Pripravljam prenosni Perl za gradnjo TLS (uradna izdaja Strawberry Perl) ...'
        $archive = Join-Path $work 'strawberry-perl.zip'
        Get-VerifiedArchive 'https://github.com/StrawberryPerl/Perl-Dist-Strawberry/releases/download/SP_54231_64bit/strawberry-perl-5.42.3.1-64bit-portable.zip' $archive '6a081a811781c30aca51dbc036afd93092af91e3297901f02c17043795a10690'
        Expand-Archive -LiteralPath $archive -DestinationPath $perlRoot -Force
    }
    $archive = Join-Path $work 'openssl-1.1.1w.tar.gz'
    Get-VerifiedArchive 'https://github.com/openssl/openssl/releases/download/OpenSSL_1_1_1w/openssl-1.1.1w.tar.gz' $archive 'cf3098950cb4d853ad95c0841f1f9c6d3dc102dccfcacd521d93925208b76ac8'
    Invoke-Checked $Python @('-c', 'import tarfile,sys; tarfile.open(sys.argv[1]).extractall(sys.argv[2],filter="data")', $archive, $work) 'Razsirjanje preverjenih TLS virov'
    $source = Join-Path $work 'openssl-1.1.1w'
    $previousPath = $env:PATH
    try {
        $env:PATH = "$MingwBin;$(Join-Path $perlRoot 'perl/bin');$(Join-Path $perlRoot 'c/bin');$env:PATH"
        Push-Location -LiteralPath $source
        Write-SetupLog 'Gradim OpenSSL 1.1.1w za Qt 5.15.2; ob naslednjem zagonu se knjiznice ponovno uporabijo.'
        $forwardPrefix = $prefix.Replace('\', '/')
        Invoke-Checked $perl @('Configure', 'mingw64', 'shared', 'no-asm', 'no-tests', "--prefix=$forwardPrefix", "--openssldir=$forwardPrefix/ssl") 'Priprava gradnje TLS'
        Invoke-Checked (Join-Path $MingwBin 'mingw32-make.exe') @('-j4') 'Gradnja TLS'
        Invoke-Checked (Join-Path $MingwBin 'mingw32-make.exe') @('install_sw') 'Namestitev lokalnih TLS knjiznic'
        Copy-Item -LiteralPath (Join-Path $source 'LICENSE') -Destination (Join-Path $prefix 'LICENSE.txt') -Force
    } finally { Pop-Location; $env:PATH = $previousPath }
    return Join-Path $prefix 'bin'
}

function Get-WindowsTools([string] $Root) {
    if (-not $env:LOCALAPPDATA) { throw 'Windows ni dolocil mape LOCALAPPDATA.' }
    $toolsRoot = Join-Path $env:LOCALAPPDATA 'SimulIDE-AI-V0.2/tools'
    New-Item -ItemType Directory -Force $toolsRoot | Out-Null
    $lock = [IO.File]::Open((Join-Path $toolsRoot 'setup.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    try {
        $qt = Find-QtBin $toolsRoot
        $mingw = Find-MingwBin $toolsRoot
        $tls = Find-TlsBin $toolsRoot
        $crt = Find-CrtBin $toolsRoot
        if (-not $qt -or -not $mingw -or -not $tls -or -not $crt) {
            $runtime = Join-Path $toolsRoot 'bootstrap-python312'
            $python = Join-Path $runtime 'python.exe'
            New-Item -ItemType Directory -Force $runtime | Out-Null
            if (-not (Test-Path -LiteralPath $python)) {
                Write-SetupLog 'Prenasam Python za pripravo orodij iz python.org ...'
                $zip = Join-Path $runtime 'python.zip'
                Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip' -OutFile $zip -TimeoutSec 300
                if ((Get-FileHash $zip -Algorithm SHA256).Hash -ne '4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3') { throw 'Prenos Python ni prestal preverjanja SHA256.' }
                Expand-Archive -LiteralPath $zip -DestinationPath $runtime -Force
            }
            $crt = Find-CrtBin $toolsRoot
            $wheel = Join-Path $Root 'server/bootstrap/pip-24.2-py3-none-any.whl'
            if (-not (Test-Path -LiteralPath $wheel)) { throw 'Manjka server/bootstrap/pip wheel. Razsiri celotno izvorno kopijo.' }
            $pth = "python312.zip`r`n.`r`nLib/site-packages`r`n$wheel`r`nimport site`r`n"
            [IO.File]::WriteAllText((Join-Path $runtime 'python312._pth'), $pth, (New-Object Text.UTF8Encoding $false))
            $probe = Invoke-Probe $python @('-c', "import aqt,importlib.metadata; assert importlib.metadata.version('aqtinstall') == '3.3.0'")
            if ($probe.Code -ne 0) { Invoke-Checked $python @('-m', 'pip', 'install', '--no-user', '--index-url', 'https://pypi.org/simple', 'aqtinstall==3.3.0') 'Namestitev aqtinstall' }
            # Explicit config prevents a user's aqt ignore_hash option from bypassing verification.
            $config = Join-Path $Root 'scripts/aqt.ini'
            $env:AQT_CONFIG = $config
            $env:AQT_REQUESTS_INSECURE_NOT_FOR_PRODUCTION_IGNORE_HASH = 'False'
            $env:AQT_REQUESTS_HASH_ALGORITHM = 'sha256'
            $env:AQT_MIRRORS_TRUSTED_MIRRORS = 'https://download.qt.io'
            if (-not $qt) {
                Write-SetupLog 'Pripravljam Qt 5.15.2 (preverjeni arhivi Qt) ...'
                Invoke-Checked $python @('-m', 'aqt', 'install-qt', 'windows', 'desktop', '5.15.2', 'win64_mingw81', '-O', $toolsRoot) 'Prenos Qt'
                $qt = Find-QtBin $toolsRoot
            }
            if (-not $mingw) {
                Invoke-Checked $python @('-m', 'aqt', 'install-tool', 'windows', 'desktop', 'tools_mingw', 'qt.tools.win64_mingw810', '-O', $toolsRoot) 'Prenos MinGW'
                $mingw = Find-MingwBin $toolsRoot
            }
            if (-not $tls) {
                $null = Build-LegacyTls $toolsRoot $mingw $python
                $tls = Find-TlsBin $toolsRoot
            }
        }
        if (-not $qt -or -not $mingw -or -not $tls -or -not $crt) { throw 'Orodja so nepopolna: potrebujem Qt 5.15.2, MinGW 8.1, OpenSSL 1.1 x64 in Visual C++ runtime knjiznici.' }
        Write-SetupLog "Uporabljam Qt: $qt; MinGW: $mingw; TLS: $tls"
        return [PSCustomObject]@{ QtBin = $qt; MingwBin = $mingw; TlsBin = $tls; CrtBin = $crt }
    } finally { $lock.Dispose() }
}
