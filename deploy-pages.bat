@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo   Custodia - rebuild + redeploy the LIVE GitHub Pages demo
echo   https://mrk-exe.github.io/Custodia/
echo   (Touches only the gh-pages branch. Never main.)
echo ============================================================
echo.

REM The engine must be running on :8000 so the data can be re-baked from it.
powershell -NoProfile -Command "try{$null=Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 'http://127.0.0.1:8000/api/health';exit 0}catch{exit 1}"
if errorlevel 1 (
  echo The engine is not running on http://127.0.0.1:8000
  echo Start it first ^(double-click Custodia.bat^), then re-run this.
  pause & exit /b 1
)

echo [1/5] Baking fresh data from the local engine...
backend\.venv\Scripts\python.exe backend\scripts\bake_static.py || (echo bake failed & pause & exit /b 1)

echo [2/5] Building the static export...
cd frontend
set STATIC_EXPORT=1
set NEXT_PUBLIC_STATIC=1
set NEXT_PUBLIC_BASE_PATH=/Custodia
call npm run build || (echo build failed & cd .. & pause & exit /b 1)
set STATIC_EXPORT=
set NEXT_PUBLIC_STATIC=
set NEXT_PUBLIC_BASE_PATH=
cd ..

echo [3/5] Staging the site...
set "D=%TEMP%\custodia-ghpages"
if exist "%D%" rmdir /s /q "%D%"
xcopy /e /i /q frontend\out "%D%" >nul
type nul > "%D%\.nojekyll"
if exist "%D%\design-tests" rmdir /s /q "%D%\design-tests"

echo [4/5] Publishing to the gh-pages branch...
pushd "%D%"
git init -q
git checkout -q -b gh-pages
git add -A
git -c user.email="adoocre@gmail.com" -c user.name="MrK-exe" commit -qm "Update Custodia static demo"
git remote add origin https://github.com/MrK-exe/Custodia.git
git push -f origin gh-pages
popd

echo [5/5] Restoring the local (non-static) build so the launchers keep working...
cd frontend & call npm run build & cd ..

echo.
echo Done. GitHub rebuilds Pages in ~1 minute:
echo   https://mrk-exe.github.io/Custodia/
pause
endlocal
