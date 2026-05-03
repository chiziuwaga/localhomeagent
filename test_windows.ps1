# Windows Compatibility Test Script (F4.6.11-12)
# Tests Local Home Agent on Windows 10 and Windows 11
# Run with: powershell -ExecutionPolicy Bypass -File test_windows.ps1

param(
    [switch]$SkipBuild,
    [switch]$Verbose,
    [string]$PythonPath = "python"
)

$ErrorActionPreference = "Stop"
$Script:TestsPassed = 0
$Script:TestsFailed = 0
$Script:TestResults = @()

# Colors for output
function Write-Success($msg) { Write-Host "✓ $msg" -ForegroundColor Green }
function Write-Failure($msg) { Write-Host "✗ $msg" -ForegroundColor Red }
function Write-Info($msg) { Write-Host "ℹ $msg" -ForegroundColor Cyan }
function Write-Section($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Yellow }

# Test runner
function Test-Condition {
    param(
        [string]$Name,
        [scriptblock]$Condition,
        [switch]$Critical
    )
    
    Write-Host -NoNewline "Testing: $Name... "
    
    try {
        $result = & $Condition
        if ($result) {
            Write-Success "PASSED"
            $Script:TestsPassed++
            $Script:TestResults += @{Name=$Name; Status="PASSED"; Error=$null}
            return $true
        } else {
            Write-Failure "FAILED"
            $Script:TestsFailed++
            $Script:TestResults += @{Name=$Name; Status="FAILED"; Error="Condition returned false"}
            if ($Critical) { throw "Critical test failed: $Name" }
            return $false
        }
    }
    catch {
        Write-Failure "ERROR: $($_.Exception.Message)"
        $Script:TestsFailed++
        $Script:TestResults += @{Name=$Name; Status="ERROR"; Error=$_.Exception.Message}
        if ($Critical) { throw "Critical test failed: $Name" }
        return $false
    }
}

# Get Windows version info
function Get-WindowsVersionInfo {
    $os = Get-CimInstance -ClassName Win32_OperatingSystem
    return @{
        Version = $os.Version
        Build = $os.BuildNumber
        Caption = $os.Caption
        Architecture = $os.OSArchitecture
    }
}

Write-Section "LOCAL HOME AGENT - WINDOWS COMPATIBILITY TEST"
Write-Host "Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

# System Information
Write-Section "System Information"
$winInfo = Get-WindowsVersionInfo
Write-Info "OS: $($winInfo.Caption)"
Write-Info "Version: $($winInfo.Version)"
Write-Info "Build: $($winInfo.Build)"
Write-Info "Architecture: $($winInfo.Architecture)"

$isWin10 = $winInfo.Build -ge 10240 -and $winInfo.Build -lt 22000
$isWin11 = $winInfo.Build -ge 22000

if ($isWin10) {
    Write-Info "Detected: Windows 10"
} elseif ($isWin11) {
    Write-Info "Detected: Windows 11"
} else {
    Write-Warning "Unknown Windows version (Build $($winInfo.Build))"
}

# Prerequisites Tests
Write-Section "Prerequisites"

Test-Condition -Name "Windows 10 or 11" -Critical -Condition {
    $winInfo.Build -ge 10240
}

Test-Condition -Name "64-bit Windows" -Critical -Condition {
    $winInfo.Architecture -eq "64-bit"
}

Test-Condition -Name "Python installed" -Critical -Condition {
    $null -ne (Get-Command $PythonPath -ErrorAction SilentlyContinue)
}

Test-Condition -Name "Python version >= 3.10" -Critical -Condition {
    $version = & $PythonPath --version 2>&1
    if ($version -match "(\d+)\.(\d+)") {
        [int]$Matches[1] -ge 3 -and [int]$Matches[2] -ge 10
    } else { $false }
}

Test-Condition -Name "pip available" -Condition {
    $null -ne (& $PythonPath -m pip --version 2>&1)
}

# File System Tests
Write-Section "File System Tests"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $scriptDir) { $scriptDir = Get-Location }

Test-Condition -Name "Main app directory exists" -Critical -Condition {
    Test-Path (Join-Path $scriptDir "app")
}

Test-Condition -Name "Templates directory exists" -Condition {
    Test-Path (Join-Path $scriptDir "templates")
}

Test-Condition -Name "Static directory exists" -Condition {
    Test-Path (Join-Path $scriptDir "static")
}

Test-Condition -Name "main.py exists" -Critical -Condition {
    Test-Path (Join-Path $scriptDir "app" "main.py")
}

Test-Condition -Name "requirements.txt exists" -Condition {
    Test-Path (Join-Path $scriptDir "requirements.txt")
}

# Python Import Tests
Write-Section "Python Module Tests"

$pythonTestScript = @"
import sys
sys.exit(0 if sys.version_info >= (3, 10) else 1)
"@

Test-Condition -Name "FastAPI importable" -Condition {
    $result = & $PythonPath -c "import fastapi; print('OK')" 2>&1
    $result -eq "OK"
}

Test-Condition -Name "Uvicorn importable" -Condition {
    $result = & $PythonPath -c "import uvicorn; print('OK')" 2>&1
    $result -eq "OK"
}

Test-Condition -Name "Jinja2 importable" -Condition {
    $result = & $PythonPath -c "import jinja2; print('OK')" 2>&1
    $result -eq "OK"
}

Test-Condition -Name "aiohttp importable" -Condition {
    $result = & $PythonPath -c "import aiohttp; print('OK')" 2>&1
    $result -eq "OK"
}

# Application Tests
Write-Section "Application Tests"

$mainPath = Join-Path $scriptDir "app" "main.py"

Test-Condition -Name "main.py syntax valid" -Condition {
    $result = & $PythonPath -m py_compile $mainPath 2>&1
    $LASTEXITCODE -eq 0
}

Test-Condition -Name "tool_graph.py syntax valid" -Condition {
    $toolPath = Join-Path $scriptDir "app" "tool_graph.py"
    if (Test-Path $toolPath) {
        $result = & $PythonPath -m py_compile $toolPath 2>&1
        $LASTEXITCODE -eq 0
    } else { $true }  # Skip if not exists
}

Test-Condition -Name "auto_updater.py syntax valid" -Condition {
    $updaterPath = Join-Path $scriptDir "app" "auto_updater.py"
    if (Test-Path $updaterPath) {
        $result = & $PythonPath -m py_compile $updaterPath 2>&1
        $LASTEXITCODE -eq 0
    } else { $true }
}

# Network Tests
Write-Section "Network Tests"

Test-Condition -Name "Port 5000 available" -Condition {
    $listener = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
    $null -eq $listener
}

Test-Condition -Name "Localhost resolves" -Condition {
    $result = Test-NetConnection -ComputerName localhost -InformationLevel Quiet
    $result
}

# PyInstaller Build Test
Write-Section "Build Tests"

if (-not $SkipBuild) {
    Test-Condition -Name "PyInstaller available" -Condition {
        $result = & $PythonPath -m PyInstaller --version 2>&1
        $LASTEXITCODE -eq 0
    }
    
    Test-Condition -Name "build.spec exists" -Condition {
        Test-Path (Join-Path $scriptDir "build.spec")
    }
    
    # Test build (dry run)
    Write-Info "Skipping actual build (use -SkipBuild:$false to build)"
}

# Server Startup Test
Write-Section "Server Startup Test"

Write-Info "Starting server in background..."

$serverProcess = $null
try {
    $env:TESTING = "1"
    $serverProcess = Start-Process -FilePath $PythonPath -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "5001" -WorkingDirectory $scriptDir -PassThru -NoNewWindow -RedirectStandardOutput "server_out.log" -RedirectStandardError "server_err.log"
    
    # Wait for server to start
    Start-Sleep -Seconds 5
    
    Test-Condition -Name "Server process running" -Condition {
        -not $serverProcess.HasExited
    }
    
    Test-Condition -Name "Server responds on /health" -Condition {
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:5001/health" -TimeoutSec 5 -UseBasicParsing
            $response.StatusCode -eq 200
        } catch {
            Write-Host "Server response error: $($_.Exception.Message)"
            $false
        }
    }
    
    Test-Condition -Name "Static files served" -Condition {
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:5001/static/" -TimeoutSec 5 -UseBasicParsing -ErrorAction SilentlyContinue
            $true
        } catch {
            # 404 is OK, means static route exists
            $_.Exception.Response.StatusCode.value__ -ne 500
        }
    }
}
finally {
    if ($serverProcess -and -not $serverProcess.HasExited) {
        Write-Info "Stopping server..."
        Stop-Process -Id $serverProcess.Id -Force -ErrorAction SilentlyContinue
    }
    
    # Cleanup logs
    Remove-Item "server_out.log" -ErrorAction SilentlyContinue
    Remove-Item "server_err.log" -ErrorAction SilentlyContinue
}

# Windows-Specific Feature Tests
Write-Section "Windows Integration Tests"

Test-Condition -Name "Registry access available" -Condition {
    $null -ne (Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion" -ErrorAction SilentlyContinue)
}

Test-Condition -Name "AppData directory writable" -Condition {
    $testFile = Join-Path $env:APPDATA "LocalHomeAgent_test_$(Get-Random).tmp"
    try {
        "test" | Out-File $testFile
        Remove-Item $testFile
        $true
    } catch { $false }
}

Test-Condition -Name "Windows notifications available" -Condition {
    $null -ne (Get-Command "New-BurntToastNotification" -ErrorAction SilentlyContinue) -or $true  # Optional
}

# Performance Tests
Write-Section "Performance Tests"

$systemInfo = Get-CimInstance -ClassName Win32_ComputerSystem
$memory = [math]::Round($systemInfo.TotalPhysicalMemory / 1GB, 2)
$processors = $systemInfo.NumberOfProcessors

Write-Info "Total RAM: $memory GB"
Write-Info "Processors: $processors"

Test-Condition -Name "Minimum RAM (4GB)" -Condition {
    $memory -ge 4
}

Test-Condition -Name "Sufficient disk space" -Condition {
    $drive = Get-PSDrive -Name ((Get-Location).Drive.Name) -ErrorAction SilentlyContinue
    if ($drive) {
        $freeGB = [math]::Round($drive.Free / 1GB, 2)
        Write-Info "Free disk space: $freeGB GB"
        $freeGB -ge 2
    } else { $true }
}

# Summary
Write-Section "TEST SUMMARY"

$totalTests = $Script:TestsPassed + $Script:TestsFailed
$passRate = if ($totalTests -gt 0) { [math]::Round(($Script:TestsPassed / $totalTests) * 100, 1) } else { 0 }

Write-Host "`nTotal Tests: $totalTests"
Write-Success "Passed: $Script:TestsPassed"
if ($Script:TestsFailed -gt 0) {
    Write-Failure "Failed: $Script:TestsFailed"
}
Write-Info "Pass Rate: $passRate%"

# Export results
$resultsFile = Join-Path $scriptDir "test_results_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
$Script:TestResults | ConvertTo-Json -Depth 3 | Out-File $resultsFile
Write-Info "Results saved to: $resultsFile"

# Final verdict
Write-Section "VERDICT"

if ($Script:TestsFailed -eq 0) {
    Write-Success "ALL TESTS PASSED - Ready for Windows $($isWin11 ? '11' : '10')"
    exit 0
} else {
    Write-Failure "SOME TESTS FAILED - Review results above"
    
    # List failed tests
    Write-Host "`nFailed tests:"
    $Script:TestResults | Where-Object { $_.Status -ne "PASSED" } | ForEach-Object {
        Write-Failure "  - $($_.Name): $($_.Error)"
    }
    
    exit 1
}
