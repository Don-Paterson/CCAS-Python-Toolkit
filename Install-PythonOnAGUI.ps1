<#
.SYNOPSIS
    Installs Python 3.13 and the CCAS Python Toolkit on a Skillable A-GUI lab VM.

.DESCRIPTION
    Designed to run on the Skillable A-GUI Windows VM. Installs Python 3.13 (if
    not already present), pins required pip packages including the Check Point
    Management API Python SDK (cpapi), and downloads the toolkit's Python files
    to C:\CCAS-Python.

    Skillable VMs are Hyper-V on Intel Xeon Gold 6330 (x86-64), so the installer
    pulls the amd64 build.

    Intended to be invoked via:
        irm https://raw.githubusercontent.com/Don-Paterson/CCAS-Python-Toolkit/main/Install-PythonOnAGUI.ps1 | iex

.NOTES
    Author:  Don Paterson
    Lab:     CCAS (Check Point Certified Automation Specialist)
    Target:  Skillable A-GUI VM (Windows, x86-64)
#>

[CmdletBinding()]
param(
    [string]$PythonVersion = "3.13.1",
    [string]$WorkDir       = "C:\CCAS-Python",
    [string]$RepoRawBase   = "https://raw.githubusercontent.com/Don-Paterson/CCAS-Python-Toolkit/main"
)

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"   # makes Invoke-WebRequest noticeably faster

function Write-Section($msg) {
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host $msg            -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor Cyan
}

function Test-PythonOK {
    try {
        $v = & py -3 --version 2>$null
        if ($LASTEXITCODE -eq 0 -and $v -match "Python (\d+)\.(\d+)") {
            $maj = [int]$Matches[1]; $min = [int]$Matches[2]
            return ($maj -gt 3 -or ($maj -eq 3 -and $min -ge 11))
        }
    } catch { }
    return $false
}

function Install-Python {
    Write-Section "Installing Python $PythonVersion (amd64)"

    $arch = "amd64"
    $url  = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-$arch.exe"
    $tmp  = Join-Path $env:TEMP "python-$PythonVersion-$arch.exe"

    Write-Host "Downloading $url"
    Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing

    Write-Host "Running silent installer (~60s)"
    $silentArgs = @(
        "/quiet",
        "InstallAllUsers=1",
        "PrependPath=1",
        "Include_pip=1",
        "Include_test=0",
        "Include_launcher=1"
    )
    Start-Process -FilePath $tmp -ArgumentList $silentArgs -Wait -NoNewWindow

    Remove-Item $tmp -Force -ErrorAction SilentlyContinue

    # Refresh PATH in the current PS session (so py.exe is found below)
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path","User")

    if (-not (Test-PythonOK)) {
        throw "Python install completed but 'py -3' still does not report a usable version."
    }
    Write-Host "Python installed: $(py -3 --version)" -ForegroundColor Green
}

function Install-PipPackages {
    Write-Section "Installing Python packages (Check Point SDK + helpers)"

    py -3 -m pip install --upgrade pip
    py -3 -m pip install --upgrade `
        cpapi `
        requests `
        urllib3 `
        python-dotenv `
        tabulate `
        colorama
}

function Get-ToolkitFiles {
    Write-Section "Downloading CCAS Python Toolkit to $WorkDir"

    if (-not (Test-Path $WorkDir)) {
        New-Item -ItemType Directory -Path $WorkDir | Out-Null
    }

    $files = @(
        "python/mgmt_api.py",
        "python/lab_example.py",
        "python/requirements.txt",
        "python/.env.example"
    )
    foreach ($f in $files) {
        $url  = "$RepoRawBase/$f"
        $dest = Join-Path $WorkDir (Split-Path $f -Leaf)
        Write-Host "  $f -> $dest"
        try {
            Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
        } catch {
            Write-Warning "Failed to download $f : $_"
        }
    }
}

function Show-NextSteps {
    Write-Section "Done. Next steps"
    Write-Host @"

    cd $WorkDir
    copy .env.example .env
    notepad .env                  # set CP_MGMT_HOST and credentials
    py -3 lab_example.py          # run the Lab 3A-3 equivalent

  Or run the smoke-test in mgmt_api.py directly:

    py -3 mgmt_api.py --host 10.1.1.101

"@ -ForegroundColor Yellow
}

# ----- main -----
Write-Section "CCAS Python Toolkit - A-GUI installer"

if (Test-PythonOK) {
    Write-Host "Python already present: $(py -3 --version)" -ForegroundColor Green
} else {
    Install-Python
}

Install-PipPackages
Get-ToolkitFiles
Show-NextSteps
