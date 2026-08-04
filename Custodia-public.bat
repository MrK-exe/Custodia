@echo off
setlocal enabledelayedexpansion
title Custodia - PUBLIC (server + tunnel)
cd /d "%~dp0"
set "DEMO_CACHE_ONLY=1"
set "CFLOG=%~dp0tunnel.log"

echo ==========================================================
echo    Custodia - PUBLIC demo  (local engine + Cloudflare tunnel)
echo    Cache-only mode is ON: visitors cannot spend your
echo    SAHMK quota. The link is live only while this machine
echo    and these windows are running.
echo ==========================================================
echo.

if not exist "%~dp0cloudflared.exe" (
  echo ERROR: cloudflared.exe was not found next to this file.
  echo Put cloudflared.exe in:  %~dp0
  pause & exit /b 1
)

REM --- 1. build frontend once if needed --------------------------------------
if not exist "%~dp0frontend\.next\BUILD_ID" (
  echo [1/5] First run: building the frontend once ^(about a minute^)...
  pushd "%~dp0frontend" & call npm run build & popd
) else (
  echo [1/5] Frontend build found.
)

REM --- 2. backend engine (inherits DEMO_CACHE_ONLY=1 from this window) --------
echo [2/5] Starting backend engine ^(cache-only^)  -^>  http://127.0.0.1:8000
cd /d "%~dp0backend"
start "Custodia backend (engine)" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

REM --- 3. frontend page ------------------------------------------------------
echo [3/5] Starting frontend page   -^>  http://127.0.0.1:3000
cd /d "%~dp0frontend"
start "Custodia frontend (page)" cmd /k "npx next start -p 3000"
cd /d "%~dp0"

REM --- 4. wait for the local app --------------------------------------------
echo [4/5] Waiting for the local app ^(the engine loads a model on first start,
echo        so give it up to ~30 seconds^)...
powershell -NoProfile -Command "for($i=0;$i -lt 120;$i++){ try{ $h=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:8000/api/health'; $f=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:3000/ar'; if($h.StatusCode -eq 200 -and $f.StatusCode -eq 200){ exit 0 } }catch{}; Start-Sleep -Seconds 1 }; exit 1"
if %errorlevel% neq 0 ( echo The local app did not come up in time. & pause & exit /b 1 )

REM --- 5. open the public tunnel and print the URL --------------------------
echo [5/5] Opening the public tunnel...
del "%CFLOG%" 2>nul
start "Custodia tunnel" cmd /k "cloudflared.exe tunnel --url http://localhost:3000 > tunnel.log 2>&1"
powershell -NoProfile -Command "$u=$null; for($i=0;$i -lt 40;$i++){ if(Test-Path '%CFLOG%'){ $m=Select-String -Path '%CFLOG%' -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue ^| Select-Object -First 1; if($m){ $u=$m.Matches[0].Value; break } }; Start-Sleep -Seconds 1 }; if($u){ Set-Content '%~dp0public-url.txt' $u; Write-Host ''; Write-Host '  ============================================================'; Write-Host ('    PUBLIC URL:  '+$u); Write-Host '    (also saved to public-url.txt)'; Write-Host '  ============================================================'; Start-Process $u } else { Write-Host '  Could not read the tunnel URL yet - see the Custodia tunnel window.' }"

echo.
echo Share the PUBLIC URL shown above.
echo To STOP the server + tunnel: run  Custodia-stop.bat  (or close the windows).
echo (You can close THIS window.)
echo.
pause
endlocal
