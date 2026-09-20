# PANO GOZ - tek komutla yerel demo (Windows PowerShell)
#
#   .\baslat.ps1                     varsayilan: 112 pano, 75 gun gecmis, port 8080
#   .\baslat.ps1 -Panels 24 -Port 8099
#   .\baslat.ps1 -Reset              veritabanini silerek bastan basla
#   .\baslat.ps1 -Telefon            saha uygulamasi telefondan da acilsin (0.0.0.0'a baglanir)
#
# Bu betik AG'A CIKMAZ. Paket kurmaz, indirmez, guncellemez. Demo makinesinde
# Docker calismiyor ve internet yok; bu yol tam olarak bunun icin var.
# (Telegram ancak notify.local.json'da bir bot anahtari varsa, o zaman da yalniz
# api.telegram.org'a cikis yonlu HTTPS ile ulasir; bkz. docs/12-BILDIRIM-KANALLARI.md.)

# CmdletBinding is deliberately NOT used: it injects the common parameters, and
# -Db then collides with the -Debug alias 'db'. A one-command launcher wants
# short, obvious switches more than it wants -Verbose.
param(
    [int]    $Panels       = 112,
    [int]    $Port         = 8080,
    [int]    $ScadaPort    = 5020,
    [int]    $Seed         = 42,
    [int]    $BackfillDays = 75,
    [string] $Db           = "",
    [switch] $Reset,
    [switch] $NoBackfill,
    [switch] $NoBrowser,
    [switch] $Telefon
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

# Turkce cikti ve kaynak dosyalar UTF-8; Windows konsolu varsayilan cp1254.
$env:PYTHONIOENCODING = "utf-8"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

Write-Host ""
Write-Host "PANO GOZ - yerel demo baslatiliyor" -ForegroundColor Cyan
Write-Host "----------------------------------"

# ---------------------------------------------------------------- python ---

function Find-Python {
    foreach ($cand in @("$Root\.venv\Scripts\python.exe", "python", "py")) {
        try {
            if ($cand -eq "py") {
                $v = & py -3 -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null
                if ($LASTEXITCODE -eq 0 -and $v) { return @{ Exe = "py"; Pre = @("-3"); Ver = $v } }
            } else {
                $v = & $cand -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null
                if ($LASTEXITCODE -eq 0 -and $v) { return @{ Exe = $cand; Pre = @(); Ver = $v } }
            }
        } catch {}
    }
    return $null
}

$py = Find-Python
if ($null -eq $py) {
    Write-Host "Python bulunamadi. Python 3.11+ kurulu olmali." -ForegroundColor Red
    exit 1
}

$parts = $py.Ver.Split(".")
if ([int]$parts[0] -lt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -lt 11)) {
    Write-Host "Python $($py.Ver) bulundu; 3.11 veya ustu gerekiyor." -ForegroundColor Red
    exit 1
}
Write-Host ("  python       . {0} (Python {1})" -f $py.Exe, $py.Ver)

# ------------------------------------------------------------------ venv ---
# Var olan bir .venv, bagimliliklari tamsa tercih edilir. YOKSA bos bir .venv
# olusturmanin bu makinede faydasi yoktur: ag yok, icine paket kurulamaz. Bos
# bir sanal ortam, calisan sistem Python'unu golgeleyen kullanilamaz bir dizin
# birakmaktan baska bir sey yapmaz. Bu yuzden .venv yalnizca bagimliliklar
# eksikse olusturulur - o durumda zaten elle kurulum gerekir.

$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    $probe = & $venvPy -c "import fastapi, uvicorn, numpy, pymodbus; print('ok')" 2>$null
    if ($probe -eq "ok") {
        $py = @{ Exe = $venvPy; Pre = @(); Ver = $py.Ver }
        Write-Host "  sanal ortam  . .venv (bagimliliklar hazir)"
    } else {
        Write-Host "  sanal ortam  . .venv var ama bagimliliklar eksik; sistem Python'u kullanilacak" -ForegroundColor Yellow
    }
}

# --------------------------------------------------------- bagimliliklar ---

$check = & $py.Exe @($py.Pre + @("-c", "import fastapi, uvicorn, numpy, scipy, pandas, sklearn, pymodbus, paho.mqtt, openpyxl; print('ok')")) 2>&1
if ($check -notmatch "ok") {
    Write-Host ""
    Write-Host "Eksik bagimlilik var:" -ForegroundColor Red
    Write-Host $check
    Write-Host ""
    Write-Host "Bu betik kurulum YAPMAZ (ag yok)." -ForegroundColor Yellow
    if (-not (Test-Path (Join-Path $Root ".venv"))) {
        Write-Host "  .venv olusturuluyor (bos; paketleri siz kuracaksiniz)"
        & $py.Exe @($py.Pre + @("-m", "venv", (Join-Path $Root ".venv"))) | Out-Null
    }
    Write-Host "Elle kurmak icin:"
    Write-Host "  $venvPy -m pip install -r requirements.txt"
    exit 1
}
Write-Host "  bagimliliklar. tamam (fastapi, uvicorn, numpy, scipy, pandas, sklearn, pymodbus, paho-mqtt)"

# ------------------------------------------------------------------ port ---

function Test-PortFree([int]$p) {
    try { return -not (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) }
    catch { return $true }
}
if (-not (Test-PortFree $Port)) {
    Write-Host "  UYARI        . $Port portu kullanimda; --port ile baska bir port verin" -ForegroundColor Yellow
}
if (-not (Test-PortFree $ScadaPort)) {
    Write-Host "  UYARI        . $ScadaPort portu kullanimda; -ScadaPort ile degistirin" -ForegroundColor Yellow
}

# --------------------------------------------------------------- calistir ---

$argv = @("-m", "panogoz.run_local",
          "--panels", $Panels, "--port", $Port, "--scada-port", $ScadaPort,
          "--seed", $Seed, "--backfill-days", $BackfillDays)
if ($Db)              { $argv += @("--db", $Db) }
if ($Reset)           { $argv += "--reset" }
if ($NoBackfill)      { $argv += "--no-backfill" }
if (-not $NoBrowser)  { $argv += "--open" }
if ($Telefon)         { $argv += @("--host", "0.0.0.0") }

Write-Host "  arayuz       . http://127.0.0.1:$Port"
Write-Host "  scada        . Modbus TCP 0.0.0.0:$ScadaPort (salt okunur)"
Write-Host ""

& $py.Exe @($py.Pre + $argv)
exit $LASTEXITCODE
