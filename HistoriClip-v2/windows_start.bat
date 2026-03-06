@echo off
title HistoriClip - Launcher
echo.
echo          HistoriClip - Starting...         
echo              [Windows Launcher]            
echo  
echo.

:: All paths relative to this script's location (works on any machine)
set "ROOT=%~dp0"

:: ── 1. Node.js Backend ──────────────────────────────────
echo  [1/3] Starting Backend (Node.js)...
start "HistoriClip-Backend" cmd /c "title HistoriClip-Backend && cd /d "%ROOT%backend" && npm start"

:: ── 2. Python AI Service (conda) ────────────────────────
echo  [2/3] Starting AI Service (Python)...
start "HistoriClip-AI" cmd /c "title HistoriClip-AI && cd /d "%ROOT%python-ai-service" && call conda activate historiclip && python app.py"

:: ── 3. Frontend React (Vite) ────────────────────────────
echo  [3/3] Starting Frontend (React + Vite)...
start "HistoriClip-Frontend" cmd /c "title HistoriClip-Frontend && cd /d "%ROOT%frontend-react" && npm run dev -- --host 0.0.0.0 --port 5173 --strictPort"

echo.
echo  
echo    All 3 services started!                 
echo                                            
echo    Backend:   http://localhost:5000         
echo    AI:        http://localhost:5001         
echo    Frontend:  http://localhost:5173         
echo                                            
echo    To stop: run windows_stop.bat           
echo  
echo.
echo  Opening browser in 5 seconds...

timeout /t 5 /nobreak >nul
start "" "http://localhost:5173"

:: Self-close this launcher window
exit
