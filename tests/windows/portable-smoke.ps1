param([string] $PackageRoot)
$ErrorActionPreference = 'Stop'
if (-not $PackageRoot) { throw 'Podaj mapo razsirjenega studentskega paketa.' }
$binary = [IO.Path]::GetFullPath((Join-Path $PackageRoot 'bin/simulide.exe'))
$revision = (& git rev-parse --short=12 HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Git revizije za preverjanje paketa ni mogoce prebrati.' }
$opened = $null
Push-Location -LiteralPath $PackageRoot
try {
    # Exercise the actual CMD entrypoint; <nul makes pause nonblocking on CI failure.
    & cmd.exe /d /c 'ZAZENI.cmd <nul'
    if ($LASTEXITCODE -ne 0) {
        $details = Get-Content -LiteralPath 'setup.log' -Tail 15 -ErrorAction SilentlyContinue
        throw "ZAZENI.cmd ni odprl studentskega paketa.`n$($details -join "`n")"
    }
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        $opened = Get-Process -Name simulide -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $binary } | Select-Object -First 1
        if ($opened -and $opened.MainWindowTitle.Contains('SimulIDE AI 0.12') -and $opened.MainWindowTitle.Contains($revision)) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $opened -or -not $opened.MainWindowTitle.Contains('SimulIDE AI 0.12') -or -not $opened.MainWindowTitle.Contains($revision)) { throw 'Paket ni odprl glavnega okna z razlicico AI 0.12 in trenutno Git revizijo.' }
    Write-Host "::notice::PASS: studentski ZAZENI.cmd je odprl Windows SimulIDE AI 0.12 ($revision)."
} catch {
    $message = $_.Exception.Message.Replace('%', '%25').Replace("`r", '%0D').Replace("`n", '%0A')
    Write-Host "::error::$message"
    throw
} finally {
    if ($opened -and -not $opened.HasExited) { Stop-Process -Id $opened.Id -Force }
    Pop-Location
}
exit 0
