# Passive inspection: never execute the EXE/DLL being inspected. PowerShell 5.1.
function Get-RuntimeInventory([string] $BinaryRoot) {
    $base = [IO.Path]::GetFullPath($BinaryRoot).TrimEnd('\', '/')
    if (-not (Test-Path -LiteralPath $base -PathType Container)) { throw "Mapa programa ne obstaja: $base" }
    $signatureCommand = Get-Command Get-AuthenticodeSignature -ErrorAction SilentlyContinue
    foreach ($file in (Get-ChildItem -LiteralPath $base -Recurse -File -Force | Where-Object { $_.Extension -in @('.exe', '.dll') } | Sort-Object FullName)) {
        $architecture = 'unknown'
        $reader = $null
        try {
            $reader = New-Object IO.BinaryReader ([IO.File]::OpenRead($file.FullName))
            if ($reader.ReadUInt16() -eq 0x5A4D) {
                $null = $reader.BaseStream.Seek(0x3C, 'Begin')
                $offset = $reader.ReadInt32()
                $null = $reader.BaseStream.Seek($offset, 'Begin')
                if ($reader.ReadUInt32() -eq 0x4550) {
                    switch ($reader.ReadUInt16()) { 0x8664 { $architecture = 'x64' }; 0x014C { $architecture = 'x86' }; 0xAA64 { $architecture = 'arm64' } }
                }
            }
        } catch { $architecture = 'unreadable-PE' }
        finally { if ($reader) { $reader.Dispose() } }
        $signature = 'not-checked-on-this-platform'
        $signer = $null
        $thumbprint = $null
        if ($signatureCommand) {
            try {
                $signed = Get-AuthenticodeSignature -LiteralPath $file.FullName
                $signature = [string] $signed.Status
                if ($signed.SignerCertificate) {
                    $signer = $signed.SignerCertificate.Subject
                    $thumbprint = $signed.SignerCertificate.Thumbprint
                }
            } catch { $signature = 'inspection-error' }
        }
        [PSCustomObject][ordered]@{
            path = $file.FullName.Substring($base.Length + 1).Replace('\', '/')
            sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            bytes = $file.Length
            architecture = $architecture
            file_version = $file.VersionInfo.FileVersion
            product_version = $file.VersionInfo.ProductVersion
            signature_status = $signature
            signer = $signer
            signer_thumbprint = $thumbprint
        }
    }
}

function Write-JsonFile([string] $Path, $Value) {
    [IO.File]::WriteAllText($Path, (ConvertTo-Json -InputObject $Value -Depth 10), (New-Object Text.UTF8Encoding $false))
}

function Write-FileChecksums([string] $Root, [string] $Destination) {
    $base = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $target = [IO.Path]::GetFullPath($Destination)
    $lines = @(Get-ChildItem -LiteralPath $base -Recurse -File -Force | Where-Object { $_.FullName -ne $target } | Sort-Object FullName | ForEach-Object {
        '{0}  {1}' -f (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant(), $_.FullName.Substring($base.Length + 1).Replace('\', '/')
    })
    [IO.File]::WriteAllLines($target, [string[]] $lines, (New-Object Text.UTF8Encoding $false))
}
