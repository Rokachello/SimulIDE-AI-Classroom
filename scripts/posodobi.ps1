$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot 'windows-common.ps1')
try {
    Initialize-SetupLog $root
    Invoke-RepositoryUpdate $root
    Write-SetupLog 'Posodobitev je uspela. Pripravljam novo gradnjo.'
} catch {
    Write-SetupLog "NAPAKA: $($_.Exception.Message)"
    exit 1
}
# Execute the updated launcher in a fresh process rather than old in-memory functions.
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'zazeni.ps1') -BuildOnly
exit $LASTEXITCODE
