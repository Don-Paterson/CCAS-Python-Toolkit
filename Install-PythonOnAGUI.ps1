<#
.SYNOPSIS
    Installs Python 3.13 and the CCAS Python Toolkit on a Skillable A-GUI lab VM.

.DESCRIPTION
    Designed to run on the Skillable A-GUI Windows VM. Installs Python 3.13
    (if not already present), installs python-dotenv, and downloads the
    toolkit's Python files to C:\CCAS-Python.

    The toolkit shells out to mgmt_cli.exe (shipped with SmartConsole) rather
    than using an SDK, so the installer also verifies mgmt_cli.exe is locatable
    and prints its full path for reference.

    Skillable VMs are Hyper-V on Intel Xeon Gold 6330 (x86-64), so the
    installer pulls the amd64 build.

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
$ProgressPreference    = "SilentlyContinue"

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

    # Refresh PATH for the current session so py.exe is findable
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path","User")

    if (-not (Test-PythonOK)) {
        throw "Python install completed but 'py -3' still does not report a usable version."
    }
    Write-Host "Python installed: $(py -3 --version)" -ForegroundColor Green
}

function Install-PipPackages {
    Write-Section "Installing python-dotenv"

    py -3 -m pip install --upgrade pip
    py -3 -m pip install --upgrade python-dotenv
}

function Find-MgmtCli {
    Write-Section "Locating mgmt_cli.exe (ships with SmartConsole)"

    $onPath = Get-Command mgmt_cli.exe -ErrorAction SilentlyContinue
    if ($onPath) {
        Write-Host "mgmt_cli.exe found on PATH: $($onPath.Source)" -ForegroundColor Green
        return
    }

    $smartConsoleBase = "C:\Program Files (x86)\CheckPoint\SmartConsole"
    if (Test-Path $smartConsoleBase) {
        $hits = Get-ChildItem $smartConsoleBase -Filter "mgmt_cli.exe" -Recurse -ErrorAction SilentlyContinue |
                Sort-Object -Property FullName -Descending
        if ($hits) {
            $found = $hits[0]
            Write-Host "Found at:  $($found.FullName)" -ForegroundColor Green
            Write-Host ""
            Write-Host "Not on PATH. Either add this directory to PATH:" -ForegroundColor Yellow
            Write-Host "  $($found.DirectoryName)" -ForegroundColor Yellow
            Write-Host "...or set CP_MGMT_CLI to the full executable path in your .env" -ForegroundColor Yellow
            return
        }
    }

    Write-Warning "mgmt_cli.exe was not found."
    Write-Warning "Install SmartConsole (CCAS Lab 2A) before running the toolkit, or"
    Write-Warning "set CP_MGMT_CLI to the full executable path manually."
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
        "python/env.example.txt"
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
    copy env.example.txt .env
    notepad .env                  # set CP_MGMT_HOST and credentials
    py -3 lab_example.py          # run the self-contained smoke test

  Or run the smoke test in mgmt_api.py directly:

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
Find-MgmtCli
Get-ToolkitFiles
Show-NextSteps
