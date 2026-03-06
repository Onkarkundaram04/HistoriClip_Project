#!/bin/bash

echo ""
echo "          HistoriClip - Starting...         "
echo "            [Linux/macOS Launcher]          "
echo ""

# Get absolute path of the directory containing this script
ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Start Node.js Backend
echo "[1/3] Starting Backend (Node.js)..."
cd "$ROOT_DIR/backend" || exit
npm start > backend.log 2>&1 &

# Start Python AI Service
echo "[2/3] Starting AI Service (Python)..."
cd "$ROOT_DIR/python-ai-service" || exit
# Using conda run to execute within the environment
conda run -n historiclip python app.py > ai_service.log 2>&1 &

# Start Frontend React
echo "[3/3] Starting Frontend (React + Vite)..."
cd "$ROOT_DIR/frontend-react" || exit
npm run dev -- --host 0.0.0.0 --port 5173 --strictPort > frontend.log 2>&1 &

echo ""
echo "   All 3 services started in the background!"
echo ""
echo "   Backend:   http://localhost:5000"
echo "   AI:        http://localhost:5001"
echo "   Frontend:  http://localhost:5173"
echo ""
echo "   Logs are being written to:"
echo "     - backend/backend.log"
echo "     - python-ai-service/ai_service.log"
echo "     - frontend-react/frontend.log"
echo ""
echo "   To stop all services, run: ./stop.sh"
echo ""

# Attempt to open browser automatically
sleep 4
if command -v xdg-open > /dev/null; then
    xdg-open "http://localhost:5173" > /dev/null 2>&1 &
elif command -v open > /dev/null; then
    open "http://localhost:5173" > /dev/null 2>&1 &
fi
