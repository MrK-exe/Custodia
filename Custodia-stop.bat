@echo off
title Custodia - stop
echo Stopping Custodia (server + tunnel; freeing ports 3000 and 8000)...
taskkill /F /IM cloudflared.exe >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do taskkill /F /PID %%p >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /F /PID %%p >nul 2>&1
echo Done. You can also just close the "Custodia ..." windows.
timeout /t 2 >nul
