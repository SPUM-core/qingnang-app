# ═══════════════════════════════════════════════════════════════
# 青囊 qingnang-app · 一键部署脚本（PowerShell）
# ═══════════════════════════════════════════════════════════════
param(
    [switch]$SkipBuild,
    [switch]$SkipDeploy,
    [switch]$SkipSync,
    [switch]$SkipInstall,
    [switch]$SkipGit,
    [switch]$SkipVerify
)

$ErrorActionPreference = "Stop"

$envPath = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envPath)) {
    Write-Host ".env not found" -ForegroundColor Red
    exit 1
}
Get-Content $envPath | ForEach-Object {
    if ($_ -match '^([A-Z_]+)=(.*)$') {
        $key, $val = $matches[1], $matches[2].Trim().Trim('"').Trim("'")
        [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
    }
}

$root     = $env:LOCAL_ROOT
$frontend = $env:LOCAL_FRONTEND
$adb      = $env:ADB_PATH
$gradlew  = $env:ANDROID_GRADLEW
$server   = $env:SERVER_HOST

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " qingnang-app deploy" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Step 1: build
if (-not $SkipBuild) {
    Write-Host "[1/6] frontend build..." -ForegroundColor Cyan
    Push-Location $frontend
    npx vite build 2>&1 | Select-Object -Last 1
    if ($LASTEXITCODE -ne 0) { Pop-Location; exit 1 }
    Pop-Location
    Write-Host "     OK" -ForegroundColor Green
}

# Step 2: server deploy
if (-not $SkipDeploy) {
    Write-Host "[2/6] server deploy..." -ForegroundColor Cyan
    Push-Location $root
    python scripts/fix_sync.py 2>&1 | Select-Object -Last 1
    if ($LASTEXITCODE -ne 0) { Pop-Location; exit 1 }
    Pop-Location
    Write-Host "     OK" -ForegroundColor Green
}

# Step 3: cap sync
if (-not $SkipSync) {
    Write-Host "[3/6] cap sync android..." -ForegroundColor Cyan
    Push-Location $frontend
    Remove-Item -Recurse -Force "android\app\src\main\assets\public\*" -ErrorAction SilentlyContinue
    npx cap sync android 2>&1 | Select-Object -Last 1
    if ($LASTEXITCODE -ne 0) { Pop-Location; exit 1 }
    Pop-Location
    Write-Host "     OK" -ForegroundColor Green
}

# Step 4: install APK
if (-not $SkipInstall) {
    Write-Host "[4/6] installDebug..." -ForegroundColor Cyan
    Push-Location $frontend
    & $gradlew installDebug 2>&1 | Select-Object -Last 2
    if ($LASTEXITCODE -ne 0) { Pop-Location; exit 1 }
    Pop-Location
    Write-Host "     OK" -ForegroundColor Green
}

# Step 5: git push
if (-not $SkipGit) {
    Write-Host "[5/6] git push..." -ForegroundColor Cyan
    Push-Location $root
    git add -A
    git commit -m "auto-deploy $(Get-Date -Format 'yyyy-MM-dd HH:mm')" 2>$null
    git push origin main 2>&1 | Select-Object -Last 1
    git push github main 2>&1 | Select-Object -Last 1
    Pop-Location
    Write-Host "     OK" -ForegroundColor Green
}

# Step 6: verify
if (-not $SkipVerify) {
    Write-Host "[6/6] verify..." -ForegroundColor Cyan
    try {
        $resp = Invoke-WebRequest -Uri "http://$server/api/v1/health" -TimeoutSec 5 -UseBasicParsing
        Write-Host "     server: $($resp.StatusCode)" -ForegroundColor Green
    } catch {
        Write-Host "     server: unreachable or no health endpoint" -ForegroundColor Yellow
    }
    if (Test-Path $adb) {
        $devices = & $adb devices 2>&1 | Select-String -Pattern "device$"
        if ($devices) { Write-Host "     adb: $($devices.Count) device(s)" -ForegroundColor Green }
        else { Write-Host "     adb: no device" -ForegroundColor Yellow }
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " DONE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
