# ================================================================
# BEHAVE-SEC Unified Launcher v2.0
# Double-click launch.bat  OR  right-click > "Run with PowerShell"
# ================================================================

$ErrorActionPreference = "Continue"

# ── Banner ────────────────────────────────────────────────────
Clear-Host
Write-Host ""
Write-Host "  ===========================================" -ForegroundColor DarkGray
Write-Host "   ____  _____  _   _  ___  _   _ ____      " -ForegroundColor Red
Write-Host "  | __ )| ____|| | | |/   \| | / /|  __|    " -ForegroundColor Red
Write-Host "  |  _ \|  _|  | |_| || - || |/ / |  _|     " -ForegroundColor Red
Write-Host "  |_.__/|_____|_|___/ \___|_| \_/ |____|    " -ForegroundColor DarkRed
Write-Host "              S E C U R I T Y                " -ForegroundColor DarkRed
Write-Host "   Continuous Behavioral Authentication       " -ForegroundColor Cyan
Write-Host "  ===========================================" -ForegroundColor DarkGray
Write-Host ""

# ── Workspace root ────────────────────────────────────────────
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

# ── Resolve Python executable ─────────────────────────────────
$pythonExe = $null
$venvPaths = @(
    (Join-Path $root ".venv\Scripts\python.exe"),
    (Join-Path $root "venv\Scripts\python.exe")
)
foreach ($p in $venvPaths) {
    if (Test-Path $p) { $pythonExe = $p; break }
}
if (-not $pythonExe) {
    $pythonExe = "python"
    Write-Host "  [WARN] No .venv found - using system Python." -ForegroundColor Yellow
} else {
    $shortPath = $pythonExe.Replace($root, ".")
    Write-Host "  [OK] Python: $shortPath" -ForegroundColor Green
}

# ── Step 0: DB Migration ──────────────────────────────────────
Write-Host ""
Write-Host "  [0/3] Checking database schema..." -ForegroundColor White

$migrationScript = Join-Path $root "migrate_captcha_score.py"
if (Test-Path $migrationScript) {
    $migResult = & $pythonExe $migrationScript 2>&1
    foreach ($line in $migResult) {
        if ($line -match "\[OK\]") {
            Write-Host "        $line" -ForegroundColor Green
        } elseif ($line -match "\[SKIP\]") {
            Write-Host "        $line" -ForegroundColor Yellow
        } else {
            Write-Host "        $line" -ForegroundColor DarkGray
        }
    }
} else {
    Write-Host "        Migration script not found - skipping." -ForegroundColor DarkGray
}

# ── Step 1: Python FastAPI Backend (port 8000) ────────────────
Write-Host ""
Write-Host "  [1/3] Starting FastAPI backend on http://localhost:8000 ..." -ForegroundColor Green

$pyTitle  = "BEHAVE-SEC | Python Backend :8000"
$pyStart  = "Set-Location '$root'"
$pyInfo1  = "Write-Host ' BEHAVE-SEC Backend' -ForegroundColor Green"
$pyInfo2  = "Write-Host ' http://localhost:8000  (API + Frontend)' -ForegroundColor Cyan"
$pyInfo3  = "Write-Host ' http://localhost:8000/docs  (Swagger)' -ForegroundColor DarkGray"
$pyRun    = "& '$pythonExe' -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
$pyCmd    = "$pyStart; `$host.UI.RawUI.WindowTitle = '$pyTitle'; Write-Host ''; $pyInfo1; $pyInfo2; $pyInfo3; Write-Host ''; $pyRun"

$pyArgs = @{
    FilePath     = "powershell"
    ArgumentList = @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $pyCmd)
    WindowStyle  = "Normal"
}
Start-Process @pyArgs

# ── Step 2: C# ASP.NET Core API (port 5000) ──────────────────
$csApiDir = Join-Path $root "BehaveSec.API"

if (Test-Path $csApiDir) {
    Write-Host ""
    Write-Host "  [2/3] Starting C# ASP.NET Core API on http://localhost:5000 ..." -ForegroundColor Cyan

    $csTitle = "BEHAVE-SEC | C# API :5000"
    $csStart = "Set-Location '$csApiDir'"
    $csInfo1 = "Write-Host ' BEHAVE-SEC C# API' -ForegroundColor Cyan"
    $csInfo2 = "Write-Host ' http://localhost:5000' -ForegroundColor Cyan"
    $csRun   = "dotnet run --urls=http://localhost:5000"
    $csCmd   = "$csStart; `$host.UI.RawUI.WindowTitle = '$csTitle'; Write-Host ''; $csInfo1; $csInfo2; Write-Host ''; $csRun"

    $csArgs = @{
        FilePath     = "powershell"
        ArgumentList = @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $csCmd)
        WindowStyle  = "Normal"
    }
    Start-Process @csArgs
} else {
    Write-Host ""
    Write-Host "  [2/3] C# API not found - frontend served by FastAPI only." -ForegroundColor DarkGray
}

# ── Step 3: Wait + Open Browser ──────────────────────────────
Write-Host ""
Write-Host "  [3/3] Waiting for services to become ready..." -ForegroundColor White

for ($i = 5; $i -ge 1; $i--) {
    Write-Host "        Starting in ${i}s..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 1
}

if (Test-Path $csApiDir) {
    $dashUrl = "http://localhost:5000/login.html"
} else {
    $dashUrl = "http://localhost:8000/login.html"
}

Write-Host ""
Write-Host "  [+] Opening $dashUrl ..." -ForegroundColor Magenta
Start-Process $dashUrl

# ── Summary ───────────────────────────────────────────────────
Write-Host ""
Write-Host "  =============================================" -ForegroundColor DarkGray
Write-Host "         BEHAVE-SEC  IS  RUNNING               " -ForegroundColor White
Write-Host "  =============================================" -ForegroundColor DarkGray

if (Test-Path $csApiDir) {
    Write-Host "    C# API + Frontend   ->  http://localhost:5000" -ForegroundColor Cyan
    Write-Host "    Python ML Backend   ->  http://localhost:8000" -ForegroundColor Green
} else {
    Write-Host "    FastAPI + Frontend  ->  http://localhost:8000" -ForegroundColor Green
    Write-Host "    Login               ->  http://localhost:8000/login.html" -ForegroundColor Cyan
    Write-Host "    Dashboard           ->  http://localhost:8000/dashboard.html" -ForegroundColor Cyan
}

Write-Host "    Swagger UI          ->  http://localhost:8000/docs" -ForegroundColor DarkGray
Write-Host "    Challenge / Demo    ->  http://localhost:8000/challenge.html" -ForegroundColor DarkGray
Write-Host "  =============================================" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Default login:  admin@behave.sec  /  password" -ForegroundColor White
Write-Host "  Close the console windows to shut down." -ForegroundColor Yellow
Write-Host ""
