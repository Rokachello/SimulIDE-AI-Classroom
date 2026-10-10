param([switch] $BuildOnly, [switch] $Force)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot 'windows-common.ps1')
$lock = $null
try {
    Initialize-SetupLog $root
    Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
    Set-Location -LiteralPath $root
    if (Test-Path -LiteralPath (Join-Path $root 'AI.pro')) {
        . (Join-Path $PSScriptRoot 'windows-tools.ps1')
        New-Item -ItemType Directory -Force (Join-Path $root 'build_AI') | Out-Null
        $lock = [IO.File]::Open((Join-Path $root 'build_AI/launch.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
        $tools = Get-WindowsTools $root
        $binary = Invoke-DesktopBuild $root $tools -Force:$Force
    } else {
        if ($BuildOnly) { throw 'Prevedeni paket nima izvorne kode za gradnjo. Prenesi izvorni repozitorij.' }
        $binary = Join-Path $root 'bin/simulide.exe'
        if (-not (Test-Path -LiteralPath $binary)) { throw 'Manjka program. Razsiri celoten paket, ne samo ZAZENI.cmd.' }
        Test-DesktopRuntime $binary
    }
    if (-not $BuildOnly) {
        # A student desktop never inherits the teacher's API key.
        Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
        Write-SetupLog "Odpiram SimulIDE iz: $binary"
        Start-Process -FilePath $binary -WorkingDirectory (Split-Path $binary -Parent) | Out-Null
    }
} catch {
    Write-SetupLog "NAPAKA: $($_.Exception.Message)"
    exit 1
} finally { if ($null -ne $lock) { $lock.Dispose() } }
