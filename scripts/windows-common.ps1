# Shared by the source launchers and the portable student package. PowerShell 5.1.
function Write-SetupLog([string] $Message) {
    Write-Host $Message
    if ($script:SetupLog) { Add-Content -LiteralPath $script:SetupLog -Value $Message -Encoding UTF8 }
}

function Initialize-SetupLog([string] $Root) {
    $script:SetupLog = Join-Path $Root 'setup.log'
    Write-SetupLog ("`r`n[{0}] SimulIDE AI 0.12; mapa: {1}" -f (Get-Date -Format s), $Root)
}

function Invoke-Checked([string] $Program, [string[]] $Arguments, [string] $Description) {
    if (-not (Get-Command $Program -ErrorAction SilentlyContinue)) { throw "${Description}: manjka ukaz $Program." }
    # PS 5.1 turns native stderr into ErrorRecords, even for compiler warnings.
    $previous = $ErrorActionPreference
    $messages = New-Object 'System.Collections.Generic.List[string]'
    try {
        $ErrorActionPreference = 'Continue'
        & $Program @Arguments 2>&1 | ForEach-Object {
            Write-SetupLog ([string] $_)
            $messages.Add([string] $_)
            if ($messages.Count -gt 12) { $messages.RemoveAt(0) }
        }
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previous }
    if ($code -ne 0) { throw "$Description ni uspelo (izhodna koda $code). Podrobnosti so v setup.log.`n$($messages -join "`n")" }
}

function Invoke-Probe([string] $Program, [string[]] $Arguments) {
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = @(& $Program @Arguments 2>$null)
        return [PSCustomObject]@{ Code = $LASTEXITCODE; Output = ($output -join "`n") }
    } finally { $ErrorActionPreference = $previous }
}

function Get-SourceRevision([string] $Root) {
    if (Get-Command git -ErrorAction SilentlyContinue) {
        $location = Invoke-Probe 'git' @('-C', $Root, 'rev-parse', '--show-toplevel')
        if ($location.Code -ne 0 -or [IO.Path]::GetFullPath($location.Output) -ne [IO.Path]::GetFullPath($Root)) { return 'unknown' }
        $probe = Invoke-Probe 'git' @('-C', $Root, 'rev-parse', '--short=12', 'HEAD')
        $revision = $probe.Output
        if ($probe.Code -eq 0 -and $revision -match '^[0-9a-f]{7,40}$') {
            $dirty = & git -C $Root status --porcelain --untracked-files=no
            if ($LASTEXITCODE -ne 0) { throw 'Preverjanje Git sprememb ni uspelo.' }
            if ($dirty) { return "$revision-dirty" }
            return $revision
        }
    }
    # GitHub's source ZIP does not contain .git; never invent a commit identity.
    return 'unknown'
}

function Get-DesktopFingerprint([string] $Root, [string] $Revision, [string] $ToolIdentity) {
    $entries = New-Object 'System.Collections.Generic.List[string]'
    $entries.Add("$Root|$Revision|$ToolIdentity")
    $files = @()
    foreach ($folder in @('src', 'resources', 'scripts', 'third_party')) {
        $files += Get-ChildItem -LiteralPath (Join-Path $Root $folder) -Recurse -File |
            Where-Object { $_.FullName -notmatch '[\\/]resources[\\/]qm[\\/]' }
    }
    $files += Get-Item -LiteralPath (Join-Path $Root 'AI.pro'), (Join-Path $Root 'SimulIDE.pri')
    foreach ($file in ($files | Sort-Object FullName)) {
        $relative = $file.FullName.Substring($Root.Length).Replace('\', '/')
        $entries.Add("$relative|$((Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash)")
    }
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes(($entries -join "`n"))))).Replace('-', '') }
    finally { $sha.Dispose() }
}

function Invoke-DesktopCompile([string] $Root, $Tools) {
    $env:PATH = "$($Tools.QtBin);$($Tools.MingwBin);$env:PATH"
    & (Join-Path $Root 'scripts/build-windows.ps1') -QtBin $Tools.QtBin -MingwBin $Tools.MingwBin -TlsBin $Tools.TlsBin -CrtBin $Tools.CrtBin
}

function Test-DesktopRuntime([string] $Binary) {
    Write-SetupLog "TLS pregled: zacenjam $Binary -ai-check-tls (lokalno nalaganje knjiznic; brez povezave s streznikom)."
    Invoke-Checked $Binary @('-ai-check-tls') 'Preverjanje TLS knjiznic'
    Write-SetupLog 'TLS pregled: koncano, izhodna koda 0.'
}

function Invoke-DesktopBuild([string] $Root, $Tools, [switch] $Force) {
    $binary = Join-Path $Root 'build_AI/executables/SimulIDE_2.0.0-/simulide.exe'
    $marker = Join-Path $Root 'build_AI/source-ready.sha256'
    $revision = Get-SourceRevision $Root
    $fingerprint = Get-DesktopFingerprint $Root $revision "$($Tools.QtBin)|$($Tools.MingwBin)|$($Tools.TlsBin)|$($Tools.CrtBin)|Qt5.15.2-Mingw8.1"
    $ready = (Test-Path -LiteralPath $marker) -and (Test-Path -LiteralPath $binary)
    if ($ready) { $ready = (Get-Content -LiteralPath $marker -Raw).Trim() -eq $fingerprint }
    # Restore an incomplete deployment instead of skipping it because sources are unchanged.
    foreach ($file in @('Qt5Core.dll', 'Qt5Widgets.dll', 'Qt5Network.dll', 'libstdc++-6.dll', 'libgcc_s_seh-1.dll', 'libwinpthread-1.dll', 'plugins/platforms/qwindows.dll', 'libssl-1_1-x64.dll', 'libcrypto-1_1-x64.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'qt.conf')) {
        if (-not (Test-Path -LiteralPath (Join-Path (Split-Path $binary -Parent) $file))) { $ready = $false }
    }
    $env:SIMULIDE_GIT_COMMIT = $revision
    if ($Force -or -not $ready) {
        Write-SetupLog "Prevajam trenutno izvorno kodo ($revision): $Root"
        Remove-Item -LiteralPath $marker -ErrorAction SilentlyContinue
        Invoke-DesktopCompile $Root $Tools
        if (-not (Test-Path -LiteralPath $binary)) { throw 'Gradnja ni ustvarila programa v tem repozitoriju.' }
        try { Test-DesktopRuntime $binary }
        catch { Remove-Item -LiteralPath $marker -ErrorAction SilentlyContinue; throw }
        # A failed build/TLS check never leaves a ready marker.
        Set-Content -LiteralPath $marker -Value $fingerprint -Encoding ASCII
    } else {
        Write-SetupLog "Koda je nespremenjena ($revision); hiter zagon."
        try { Test-DesktopRuntime $binary }
        catch { Remove-Item -LiteralPath $marker -ErrorAction SilentlyContinue; throw }
    }
    return $binary
}

function Get-ClassroomDataPath([string] $ServerRoot, [string] $LocalAppData, [string] $ExplicitPath) {
    $legacy = Join-Path $LocalAppData 'SimulIDE-AI-V0.2/classroom-data'
    $candidates = @(@($legacy, (Join-Path $ServerRoot 'data')) | Where-Object {
        Test-Path -LiteralPath (Join-Path $_ 'classroom.sqlite3')
    })
    if ($ExplicitPath) {
        $selected = [IO.Path]::GetFullPath($ExplicitPath)
        if (Test-Path -LiteralPath (Join-Path $selected 'classroom.sqlite3')) { return $selected }
        if ($candidates.Count -gt 0) {
            throw "SIMULIDE_DATA kaze na $selected brez baze, obstojeca baza pa je v: $($candidates -join ', '). Preveri nastavitev; nove prazne baze nisem ustvaril."
        }
        if ((Test-Path -LiteralPath $selected) -and (Get-ChildItem -LiteralPath $selected -Force | Select-Object -First 1)) {
            throw "SIMULIDE_DATA kaze na $selected s podatki, vendar manjka classroom.sqlite3. Preveri uporabljeno mapo ali varnostno kopijo."
        }
        return $selected
    }
    if ($candidates.Count -gt 1) {
        throw "Najdenih je vec baz: $($candidates -join ', '). Nastavi SIMULIDE_DATA na uporabljeno mapo; nobene baze nisem zamenjal."
    }
    if ($candidates.Count -eq 1) { return $candidates[0] }
    # Do not silently create an empty DB alongside unexplained existing data.
    foreach ($folder in @($legacy, (Join-Path $ServerRoot 'data'))) {
        if ((Test-Path -LiteralPath $folder) -and (Get-ChildItem -LiteralPath $folder -Force | Select-Object -First 1)) {
            throw "Mapa $folder vsebuje podatke, vendar manjka classroom.sqlite3. Preveri varnostno kopijo ali nastavi SIMULIDE_DATA."
        }
    }
    return $legacy
}

function Invoke-RepositoryUpdate([string] $Root) {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git ni namescen. Namesti Git for Windows; za projekt iz ZIP prenesi novo izvorno kopijo.' }
    $probe = Invoke-Probe 'git' @('-C', $Root, 'rev-parse', '--show-toplevel')
    $inside = $probe.Output
    if ($probe.Code -ne 0 -or [IO.Path]::GetFullPath($inside) -ne [IO.Path]::GetFullPath($Root)) {
        throw 'Ta mapa ni Git repozitorij. POSODOBI.cmd uporabi v klonirani izvorni kodi, ne v prevedenem paketu ali ZIP kopiji.'
    }
    $changes = & git -C $Root status --porcelain --untracked-files=all
    if ($LASTEXITCODE -ne 0) { throw 'Preverjanje lokalnih sprememb ni uspelo.' }
    if ($changes) { throw 'Prisotne so lokalne spremembe ali nove datoteke. Najprej jih shrani z Git oziroma prestavi svoje datoteke; posodobitev jih ni spreminjala.' }
    Invoke-Checked 'git' @('-C', $Root, 'pull', '--ff-only') 'Posodobitev Git (preveri omrezje, dostop in zgodovino veje)'
}
