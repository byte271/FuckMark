$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$ReleaseTag = if ($env:FUCKMARK_RELEASE_TAG) { $env:FUCKMARK_RELEASE_TAG } else { "v0.4.1" }
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

$ModuleInvoke = "-m fuckmark.cli"
$Ascii = New-Object System.Text.ASCIIEncoding
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Test-AsciiText([string]$Value) {
    return [regex]::IsMatch($Value, '^[\x20-\x7E\\]+$')
}

function Get-RelativeLauncherPath([string]$FromDir, [string]$ToFile) {
    $fromFull = (Resolve-Path -LiteralPath $FromDir).Path
    if (-not $fromFull.EndsWith([IO.Path]::DirectorySeparatorChar)) {
        $fromFull += [IO.Path]::DirectorySeparatorChar
    }
    $fromUri = New-Object System.Uri $fromFull
    $toUri = New-Object System.Uri ((Resolve-Path -LiteralPath $ToFile).Path)
    $relative = [Uri]::UnescapeDataString($fromUri.MakeRelativeUri($toUri).ToString())
    return $relative -replace '/', '\'
}

$RelativePython = $null
try {
    $RelativePython = Get-RelativeLauncherPath $Bin $Python
}
catch {}

if ($RelativePython -and -not [IO.Path]::IsPathRooted($RelativePython) -and (Test-AsciiText $RelativePython)) {
    $LauncherBody = "@echo off`r`n`"%~dp0$RelativePython`" $ModuleInvoke %*`r`n"
    [IO.File]::WriteAllBytes($Launcher, $Ascii.GetBytes($LauncherBody))
}
elseif (Test-AsciiText $Python) {
    $LauncherBody = "@echo off`r`n`"$Python`" $ModuleInvoke %*`r`n"
    [IO.File]::WriteAllBytes($Launcher, $Ascii.GetBytes($LauncherBody))
}
else {
    $Ps1Path = Join-Path $Bin "fuckmark.ps1"
    $EscapedPython = $Python.Replace("'", "''")
    $Ps1Body = "& '$EscapedPython' $ModuleInvoke @args`r`n"
    [IO.File]::WriteAllBytes($Ps1Path, $Utf8NoBom.GetBytes($Ps1Body))
    $LauncherBody = "@echo off`r`npowershell.exe -NoProfile -ExecutionPolicy Bypass -File `"%~dp0fuckmark.ps1`" %*`r`n"
    [IO.File]::WriteAllBytes($Launcher, $Ascii.GetBytes($LauncherBody))
}

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
Write-Host "The public CLI inserts hidden Unicode into ordinary English ASCII text."
Write-Host "Installation success is not watermark removal. Check --status for the outcome."
Write-Host "Command: fuckmark --help"
Write-Host "Open a new terminal if the command is not on PATH yet."
Write-Host ""
