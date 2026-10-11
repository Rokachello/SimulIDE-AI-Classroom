param([string] $CurrentRoot, [string] $PreviousRoot, [string] $OutputRoot)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot 'windows-common.ps1')
. (Join-Path $PSScriptRoot 'runtime-inventory.ps1')
try {
    Initialize-SetupLog $root
    if (-not $CurrentRoot) { $CurrentRoot = Read-Host 'Pot do mape novega programa (bin ali mapa s simulide.exe)' }
    if (-not $PreviousRoot) { $PreviousRoot = Read-Host 'Pot do mape prejsnjega delujocega programa (Enter preskoci primerjavo)' }
    $output = if ($OutputRoot) { $OutputRoot } else { Join-Path $root 'dist/withsecure-review' }
    New-Item -ItemType Directory -Force $output | Out-Null
    $current = @(Get-RuntimeInventory $CurrentRoot)
    if (-not ($current | Where-Object { $_.path -eq 'simulide.exe' })) { throw 'Izbrana nova mapa ne vsebuje simulide.exe.' }
    Write-JsonFile (Join-Path $output 'current-runtime.json') $current
    if ($PreviousRoot) {
        $previous = @(Get-RuntimeInventory $PreviousRoot)
        if (-not ($previous | Where-Object { $_.path -eq 'simulide.exe' })) { throw 'Izbrana prejsnja mapa ne vsebuje simulide.exe.' }
        Write-JsonFile (Join-Path $output 'previous-runtime.json') $previous
        $comparison = foreach ($name in (@($current.path) + @($previous.path) | Sort-Object -Unique)) {
            $new = $current | Where-Object { $_.path -eq $name }
            $old = $previous | Where-Object { $_.path -eq $name }
            $status = if (-not $old) { 'added' } elseif (-not $new) { 'removed' } elseif ($old.sha256 -eq $new.sha256) { 'identical' } else { 'changed' }
            [PSCustomObject]@{ path = $name; status = $status; previous_sha256 = $old.sha256; current_sha256 = $new.sha256 }
        }
        $comparison | Export-Csv -LiteralPath (Join-Path $output 'runtime-comparison.csv') -NoTypeInformation -Encoding UTF8
    } else {
        # Do not leave a comparison from an earlier invocation attached to this report.
        Remove-Item -LiteralPath (Join-Path $output 'previous-runtime.json'), (Join-Path $output 'runtime-comparison.csv') -ErrorAction SilentlyContinue
    }
    Write-SetupLog "Pasivni pregled je shranjen v $output. Nobenega pregledanega programa ali DLL nisem zagnal."
    Write-SetupLog 'Za WithSecure dodaj tocno zaznavo, cas, blokirano datoteko in korak zagona. Ne prilagaj zasebnih podatkov ali API kljucev.'
} catch { Write-SetupLog "NAPAKA: $($_.Exception.Message)"; exit 1 }
