# Official Python/PyPI/Qt sources. TLS and archive verification stay enabled.
function Find-QtBin([string] $ToolsRoot) {
    foreach ($qmake in (Get-ChildItem -LiteralPath $ToolsRoot -Filter qmake.exe -Recurse -File -ErrorAction SilentlyContinue)) {
        if ($qmake.FullName -notmatch 'mingw81_64[\\/]bin[\\/]qmake.exe$') { continue }
        $probe = Invoke-Probe $qmake.FullName @('-query', 'QT_VERSION')
        if ($probe.Code -eq 0 -and $probe.Output -eq '5.15.2' -and (Test-Path (Join-Path $qmake.DirectoryName 'lrelease.exe'))) { return $qmake.DirectoryName }
    }
    return $null
}

function Find-MingwBin([string] $ToolsRoot) {
    foreach ($gcc in (Get-ChildItem -LiteralPath $ToolsRoot -Filter g++.exe -Recurse -File -ErrorAction SilentlyContinue)) {
        $probe = Invoke-Probe $gcc.FullName @('-dumpfullversion')
        if ($probe.Code -eq 0 -and $probe.Output -eq '8.1.0' -and (Test-Path (Join-Path $gcc.DirectoryName 'mingw32-make.exe'))) { return $gcc.DirectoryName }
    }
    return $null
}

function Find-TlsBin([string] $ToolsRoot) {
    foreach ($ssl in (Get-ChildItem -LiteralPath $ToolsRoot -Filter libssl-1_1-x64.dll -Recurse -File -ErrorAction SilentlyContinue)) {
        if (Test-Path (Join-Path $ssl.DirectoryName 'libcrypto-1_1-x64.dll')) { return $ssl.DirectoryName }
    }
    return $null
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
        if (-not $qt -or -not $mingw -or -not $tls) {
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
                Invoke-Checked $python @('-m', 'aqt', 'install-tool', 'windows', 'desktop', 'tools_openssl_x64', '-O', $toolsRoot) 'Prenos OpenSSL iz Qt'
                $tls = Find-TlsBin $toolsRoot
            }
        }
        if (-not $qt -or -not $mingw -or -not $tls) { throw 'Orodja so nepopolna: potrebujem Qt 5.15.2, MinGW 8.1 in obe OpenSSL 1.1 x64 knjiznici.' }
        Write-SetupLog "Uporabljam Qt: $qt; MinGW: $mingw; TLS: $tls"
        return [PSCustomObject]@{ QtBin = $qt; MingwBin = $mingw; TlsBin = $tls }
    } finally { $lock.Dispose() }
}
