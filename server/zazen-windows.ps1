# Windows PowerShell 5.1. No administrator rights or installed Python needed.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Set-Location -LiteralPath $PSScriptRoot
$runtime = Join-Path $env:LOCALAPPDATA 'SimulIDE-AI-V0.2/server-runtime312'
$python = Join-Path $runtime 'python.exe'
$lock = $null
try {
    Write-Host 'SIMULIDE AI UCILNICA V0.12'
    Write-Host "Zaganjam streznik iz: $PSScriptRoot"
    $existing = $null
    try { $existing = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 2 } catch { }
    if ($null -ne $existing) {
        throw "Na naslovu 127.0.0.1:8765 ze tece streznik (razlicica $($existing.version), izdaja $($existing.release)). Zapri njegovo okno in znova zazeni ta ZAZENI-STREZNIK.cmd."
    }
    New-Item -ItemType Directory -Force $runtime | Out-Null
    $lock = [IO.File]::Open((Join-Path $runtime 'server.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    if (-not (Test-Path -LiteralPath $python)) {
        Write-Host 'Prenasam Python za lokalni streznik ...'
        $zip = Join-Path $runtime 'python.zip'
        Invoke-WebRequest -UseBasicParsing 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip' -OutFile $zip -TimeoutSec 300
        if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ne '4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3') { throw 'Prenos Python ni prestal preverjanja SHA256.' }
        Expand-Archive -LiteralPath $zip -DestinationPath $runtime -Force
    }
    $wheel = Join-Path $PSScriptRoot 'bootstrap/pip-24.2-py3-none-any.whl'
    if (-not (Test-Path -LiteralPath $wheel)) { throw 'Najprej razsiri celoten ZIP. Manjka pip wheel.' }
    $pth = "python312.zip`r`n.`r`nLib/site-packages`r`n$PSScriptRoot`r`n$wheel`r`nimport site`r`n"
    [IO.File]::WriteAllText((Join-Path $runtime 'python312._pth'), $pth, (New-Object Text.UTF8Encoding $false))
    $requirements = Join-Path $PSScriptRoot 'requirements.txt'
    $hash = (Get-FileHash -LiteralPath $requirements -Algorithm SHA256).Hash
    $marker = Join-Path $runtime 'packages-ready.txt'
    if (-not (Test-Path -LiteralPath $marker) -or (Get-Content -LiteralPath $marker -Raw).Trim() -ne $hash) {
        Write-Host 'Pripravljam knjiznice streznika ...'
        & $python -m pip install --no-user --no-cache-dir --upgrade --target (Join-Path $runtime 'Lib/site-packages') -r $requirements
        if ($LASTEXITCODE -ne 0) { throw 'Namestitev knjiznic ni uspela.' }
        Set-Content -LiteralPath $marker -Value $hash -Encoding ASCII
    }
    $env:SIMULIDE_DATA = Join-Path $env:LOCALAPPDATA 'SimulIDE-AI-V0.2/classroom-data'
    & $python -c "import app; assert app.app.test_client().get('/health').json.get('release') == '0.12', 'Nalozena je napacna razlicica streznika'; print('Ucilnica V0.12 pripravljena'); print('Izvor:', app.__file__)"
    if ($LASTEXITCODE -ne 0) { throw 'Preverjanje streznika ni uspelo.' }
    & $python -c "from app import db; c=db(); raise SystemExit(0 if c.execute('SELECT 1 FROM users WHERE role=?', ('teacher',)).fetchone() else 3)"
    if ($LASTEXITCODE -eq 3) {
        & $python app.py init
        if ($LASTEXITCODE -ne 0) { throw 'Ustvarjanje ucitelja ni uspelo.' }
    } elseif ($LASTEXITCODE -ne 0) { throw 'Preverjanje racuna ni uspelo.' }
    $mode = Read-Host 'Demo brez AI klicev? [d/N]'
    if ($mode -eq 'd') { $env:SIMULIDE_DEMO = '1' }
    else {
        Remove-Item Env:SIMULIDE_DEMO -ErrorAction SilentlyContinue
        if (-not $env:OPENAI_API_KEY) {
            $secret = Read-Host 'OpenAI API kljuc (samo v pomnilniku streznika)' -AsSecureString
            $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
            try { $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
            finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
        }
    }
    if ($env:SIMULIDE_DEMO -ne '1') {
        & $python -c "import vector_rag; raise SystemExit(0 if vector_rag.overview()['state']=='ready' else 3)"
        if ($LASTEXITCODE -eq 3) {
            $ragChoice = Read-Host 'Pripravim iskanje po dokumentaciji SimulIDE v tvojem OpenAI racunu? [D/n]'
            if ($ragChoice -ne 'n') {
                & $python setup_vector_rag.py
                if ($LASTEXITCODE -ne 0) { Write-Host 'Vektorsko iskanje se ni pripravilo. Ucilnica bo uporabljala lokalne vire; pripravo lahko ponovis ob naslednjem zagonu.' -ForegroundColor Yellow }
            }
        } elseif ($LASTEXITCODE -ne 0) { throw 'Preverjanje priprave dokumentacije ni uspelo.' }
    }
    Write-Host 'V brskalniku odpri http://127.0.0.1:8765 in ustvari studenta ter uro.'
    Write-Host 'Pusti to okno odprto. V SimulIDE uporabi Prijava / ura.'
    & $python app.py serve
    if ($LASTEXITCODE -ne 0) { throw 'Streznik se je ustavil z napako.' }
} finally {
    Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
    if ($null -ne $lock) { $lock.Dispose() }
}
