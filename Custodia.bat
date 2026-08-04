@echo off
setlocal enabledelayedexpansion
title Custodia - KSA Market Intelligence
cd /d "%~dp0"

echo ==================================================
echo    Custodia - KSA Market Intelligence
echo    One-click local demo (backend engine + page)
echo ==================================================
echo.

REM --- 0. If it's already running, just open the browser and exit -------------
powershell -NoProfile -Command "try{ $null=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:3000/ar'; exit 0 }catch{ exit 1 }"
if %errorlevel%==0 (
  echo Already running - opening the page...
  start "" "http://127.0.0.1:3000/"
  goto :done
)

REM --- 1. Build the frontend once if there is no build yet --------------------
if not exist "%~dp0frontend\.next\BUILD_ID" (
  echo [1/4] First run: building the frontend once ^(about a minute^)...
  cd /d "%~dp0frontend"
  call npm run build
  cd /d "%~dp0"
) else (
  echo [1/4] Frontend build found.
)

REM --- 2. Start the backend engine in its own window --------------------------
echo [2/4] Starting backend engine  -^>  http://127.0.0.1:8000
cd /d "%~dp0backend"
start "Custodia backend (engine)" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

REM --- 3. Start the frontend page in its own window ---------------------------
echo [3/4] Starting frontend page   -^>  http://127.0.0.1:3000
cd /d "%~dp0frontend"
start "Custodia frontend (page)" cmd /k "npx next start -p 3000"
cd /d "%~dp0"

REM --- 4. Wait until BOTH answer, then open the browser ----------------------
echo [4/4] Waiting for the app to come up ^(the engine loads a language model on
echo        first start, so give it up to ~30 seconds^)...
powershell -NoProfile -Command "for($i=0;$i -lt 120;$i++){ try{ $h=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:8000/api/health'; $f=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:3000/ar'; if($h.StatusCode -eq 200 -and $f.StatusCode -eq 200){ Start-Process 'http://127.0.0.1:3000/'; exit 0 } }catch{}; Start-Sleep -Seconds 1 }; exit 1"
if %errorlevel% neq 0 (
  echo.
  echo Could not confirm startup automatically.
  echo Open this in your browser manually:  http://127.0.0.1:3000/
)

:done
echo.
echo Custodia is running. Two windows opened: "Custodia backend" and "Custodia frontend".
echo To STOP it: close those two windows, or run  Custodia-stop.bat
echo.
echo (You can close THIS window.)
pause
endlocal
