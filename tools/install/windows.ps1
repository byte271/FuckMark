$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$ReleaseTag = if ($env:FUCKMARK_RELEASE_TAG) { $env:FUCKMARK_RELEASE_TAG } else { "v0.3.0" }
$PackageVersion = $ReleaseTag.TrimStart("v")
$WheelName = "fuckmark-$PackageVersion-py3-none-any.whl"
$ReleaseBase = "https://github.com/byte271/FuckMark/releases/download/$ReleaseTag"
$Root = if ($env:FUCKMARK_HOME) { $env:FUCKMARK_HOME } else { Join-Path $env:LOCALAPPDATA "Q1z\FuckMark" }
$Venv = Join-Path $Root "venv"
$Bin = if ($env:FUCKMARK_BIN) { $env:FUCKMARK_BIN } else { Join-Path $env:LOCALAPPDATA "Q1z\bin" }
$Stage = Join-Path $Root "stage"
$Python = Join-Path $Venv "Scripts\python.exe"
$Launcher = Join-Path $Bin "fuckmark.cmd"

function Find-Python {
    $Candidates = @(
        [pscustomobject]@{ Exe = "py"; Args = @("-3.13") },
        [pscustomobject]@{ Exe = "py"; Args = @("-3.12") },
        [pscustomobject]@{ Exe = "py"; Args = @("-3.11") },
        [pscustomobject]@{ Exe = "py"; Args = @("-3") },
        [pscustomobject]@{ Exe = "python"; Args = @() },
        [pscustomobject]@{ Exe = "python3"; Args = @() }
    )
    foreach ($Candidate in $Candidates) {
        try {
            & $Candidate.Exe @($Candidate.Args) -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) {
                return $Candidate
            }
        }
        catch {}
    }
    return $null
}

Write-Host ""
Write-Host "FuckMark"
Write-Host "Installing tagged release $ReleaseTag with SHA-256 verification."
Write-Host ""

$Candidate = Find-Python
if (-not $Candidate) {
    throw "Python 3.11 or newer is required. Install it yourself, then rerun. This installer does not use winget or administrator rights."
}

New-Item -ItemType Directory -Force -Path $Root | Out-Null
New-Item -ItemType Directory -Force -Path $Bin | Out-Null
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

$SumsPath = Join-Path $Stage "SHA256SUMS.txt"
$WheelPath = Join-Path $Stage $WheelName
Invoke-WebRequest -Uri "$ReleaseBase/SHA256SUMS.txt" -OutFile $SumsPath
Invoke-WebRequest -Uri "$ReleaseBase/$WheelName" -OutFile $WheelPath

if (-not (Test-Path $Python)) {
    if (Test-Path $Venv) {
        Remove-Item -Recurse -Force $Venv
    }
    & $Candidate.Exe @($Candidate.Args) -m venv $Venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Python)) {
        throw "Failed to create the FuckMark environment."
    }
}

$Verify = @"
import hashlib
import pathlib
import sys
sums_path = pathlib.Path(sys.argv[1])
wheel_path = pathlib.Path(sys.argv[2])
expected = None
for line in sums_path.read_text(encoding='utf-8').splitlines():
    parts = line.split()
    if len(parts) != 2:
        raise SystemExit('SHA256SUMS.txt line must contain digest and filename')
    digest, name = parts
    if name == wheel_path.name:
        expected = digest.lower()
        break
if expected is None:
    raise SystemExit('wheel filename is missing from SHA256SUMS.txt')
actual = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
if actual != expected:
    raise SystemExit('wheel SHA-256 does not match SHA256SUMS.txt')
"@
$VerifyPy = Join-Path $Stage "verify_checksum.py"
Set-Content -Path $VerifyPy -Value $Verify -Encoding utf8
& $Python $VerifyPy $SumsPath $WheelPath
if ($LASTEXITCODE -ne 0) {
    throw "Release checksum verification failed."
}

Write-Host "Checksum matched. Installing the verified wheel..."
& $Python -m pip install --disable-pip-version-check --no-cache-dir --upgrade $WheelPath
if ($LASTEXITCODE -ne 0) {
    throw "FuckMark installation failed."
}

$LauncherBody = "@echo off`r`n`"$Python`" -m fuckmark.cli %*`r`n"
[IO.File]::WriteAllText($Launcher, $LauncherBody, [Text.Encoding]::ASCII)

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$Entries = @()
if ($UserPath) {
    $Entries = $UserPath -split ";" | Where-Object { $_ }
}
if ($Entries -notcontains $Bin) {
    [Environment]::SetEnvironmentVariable("Path", (($Entries + $Bin) -join ";"), "User")
}
if (($env:Path -split ";") -notcontains $Bin) {
    $env:Path = "$Bin;$env:Path"
}

Write-Host ""
Write-Host "FuckMark $PackageVersion installed."
Write-Host "The public CLI currently returns input text unchanged."
Write-Host "Command: fuckmark --help"
Write-Host "Open a new terminal if the command is not on PATH yet."
Write-Host ""
