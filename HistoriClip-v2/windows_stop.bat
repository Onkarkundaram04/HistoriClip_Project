@echo off
title HistoriClip - Stopping
echo.
echo  
echo          HistoriClip - Stopping...         
echo              [Windows Stopper]             
echo  
echo.

:: ──────────────────────────────────────────────────────────
:: STEP 1: Kill the 3 service terminal windows by title
::         This completely closes the CMD windows themselves
:: ──────────────────────────────────────────────────────────
echo  [1/3] Killing HistoriClip terminal windows...

:: Kill by window title (matches the titles set in windows_start.bat)
taskkill /FI "WINDOWTITLE eq HistoriClip-Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq HistoriClip-AI*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq HistoriClip-Frontend*" /T /F >nul 2>&1

:: Also kill the launcher window if it's still open
taskkill /FI "WINDOWTITLE eq HistoriClip - Launcher*" /T /F >nul 2>&1

echo  Done.

:: ──────────────────────────────────────────────────────────
:: STEP 2: Kill any node/python processes on our specific ports
::         This catches orphaned processes that survived Step 1
:: ──────────────────────────────────────────────────────────
echo  [2/3] Releasing service ports (5000, 5001, 5173)...

for %%P in (5000 5001 5173) do (
    for /f "tokens=5" %%I in ('netstat -ano 2^>nul ^| findstr "LISTENING" ^| findstr ":%%P "') do (
        if not "%%I"=="0" (
            taskkill /PID %%I /T /F >nul 2>&1
        )
    )
)

echo  Done.

:: ──────────────────────────────────────────────────────────
:: STEP 3: Kill any remaining node.exe and python.exe
::         that were started by HistoriClip (safety net)
:: ──────────────────────────────────────────────────────────
echo  [3/3] Cleaning up remaining processes...

:: Kill node processes (backend + frontend)
taskkill /IM "node.exe" /F >nul 2>&1

echo  Done.

echo.
echo  
echo    All services stopped and windows closed
echo  
echo.

:: Brief pause so user can read the message, then self-destruct
timeout /t 2 /nobreak >nul

:: Self-close this stop window
exit
