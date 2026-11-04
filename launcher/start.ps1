# Starts Tape on Windows. The first run sets up a private copy of Python and Tape's
# libraries in the data folder, so nothing else on the computer is touched and no
# admin rights are needed. Every download is pinned and checked against a checksum.

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$UvVersion = '0.13.4'
$UvSha256 = 'ccec7508a07d9933d7cb1261880633efcf1f30d6e6eddab21823f1dae6f23225'
$PythonVersion = '3.13'

$AppDir = Split-Path -Parent $PSScriptRoot
$DataDir = if ($env:TAPE_DATA_DIR) { $env:TAPE_DATA_DIR } else { Join-Path $env:LOCALAPPDATA 'tape' }
$Runtime = Join-Path $DataDir 'runtime'
$Venv = Join-Path $Runtime 'venv'
$Python = Join-Path $Venv 'Scripts\python.exe'
$Uv = Join-Path $Runtime 'uv\uv.exe'
$Lock = Join-Path $PSScriptRoot 'requirements.lock'
$Stamp = Join-Path $Runtime 'installed.txt'

function Stop-WithHelp($message) {
    Write-Host ''
    Write-Host "  Tape couldn't start: $message" -ForegroundColor Red
    Write-Host '  Check your internet connection and double-click Start Tape again.'
    Write-Host '  START-HERE.html has more help.'
    Write-Host ''
    exit 1
}

function Install-Uv {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Uv) | Out-Null
    $zip = Join-Path $Runtime 'uv.zip'
    $url = "https://github.com/astral-sh/uv/releases/download/$UvVersion/uv-x86_64-pc-windows-msvc.zip"
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $zip
    if ((Get-FileHash $zip -Algorithm SHA256).Hash.ToLower() -ne $UvSha256) {
        Remove-Item $zip -Force
        throw 'The setup tool failed its checksum, so it was not used.'
    }
    Expand-Archive -Force -Path $zip -DestinationPath (Split-Path -Parent $Uv)
    Remove-Item $zip -Force
}

$wanted = "$((Get-FileHash $Lock -Algorithm SHA256).Hash) python-$PythonVersion uv-$UvVersion"
$have = if (Test-Path $Stamp) { (Get-Content $Stamp -Raw).Trim() } else { '' }

if ($have -ne $wanted -or -not (Test-Path $Python)) {
    Write-Host ''
    Write-Host '  Setting up Tape. This only happens once and takes a couple of minutes.'
    Write-Host ''
    try {
        New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
        if (-not (Test-Path $Uv)) { Install-Uv }
        $env:UV_PYTHON_INSTALL_DIR = Join-Path $Runtime 'python'
        $env:UV_CACHE_DIR = Join-Path $Runtime 'cache'
        $env:UV_PYTHON_INSTALL_REGISTRY = '0'

        Write-Host '  Getting Python...'
        & $Uv venv --quiet --no-config --clear --python $PythonVersion --python-preference only-managed $Venv
        if ($LASTEXITCODE -ne 0) { throw 'Python could not be set up.' }

        Write-Host '  Getting the libraries Tape uses...'
        & $Uv pip sync --quiet --no-config --require-hashes --only-binary ':all:' --python $Python $Lock
        if ($LASTEXITCODE -ne 0) { throw 'The libraries could not be installed.' }

        # Prove it loads before calling it done. On Windows this also catches a data
        # folder path long enough to put the deepest library files over the 260-character limit.
        Write-Host '  Checking that everything loads...'
        $env:TAPE_DATA_DIR = $DataDir
        Push-Location -LiteralPath $AppDir
        & $Python -c 'import tape.server; from tape.ai import claude, chatgpt'
        $loaded = $LASTEXITCODE
        Pop-Location
        if ($loaded -ne 0) { throw "The libraries installed but won't load. If your Windows user folder has a very long name, that's the likely cause." }

        Set-Content -Path $Stamp -Value $wanted -Encoding ascii
    } catch {
        Stop-WithHelp $_.Exception.Message
    }
    Write-Host '  Setup finished.'
}

$env:TAPE_DATA_DIR = $DataDir
$env:PYTHONUTF8 = '1'
Remove-Item Env:PYTHONHOME, Env:PYTHONPATH -ErrorAction SilentlyContinue

Set-Location -LiteralPath $AppDir
Write-Host ''
Write-Host '  Tape is starting. Your browser will open in a moment.'
Write-Host '  Keep this window open while you use Tape. Close it to quit.'
Write-Host ''
& $Python -m tape serve --open
exit $LASTEXITCODE
