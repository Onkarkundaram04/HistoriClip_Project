#!/bin/bash

echo ""
echo "          HistoriClip - Stopping...         "
echo "            [Linux/macOS Stopper]           "
echo ""

echo "[1/3] Identifying processes on HistoriClip ports..."

# Find pids
PIDS=""

# Use lsof (standard on macOS, common on Linux)
if command -v lsof > /dev/null; then
    for port in 5000 5001 5173; do
        PID=$(lsof -ti:$port)
        if [ ! -z "$PID" ]; then
            PIDS="$PIDS $PID"
        fi
    done
# Fallback to fuser (standard footprint on Linux)
elif command -v fuser > /dev/null; then
    for port in 5000 5001 5173; do
        PID=$(fuser $port/tcp 2>/dev/null)
        if [ ! -z "$PID" ]; then
            PIDS="$PIDS $PID"
        fi
    done
else
    echo "Error: Neither 'lsof' nor 'fuser' command found. Cannot automatically detect ports."
    echo "You may need to manually kill processes on ports 5000, 5001, and 5173."
    exit 1
fi

echo "[2/3] Killing services..."
if [ ! -z "$PIDS" ]; then
    # remove duplicate pids if any
    PIDS=$(echo "$PIDS" | xargs -n1 | sort -u | xargs)
    kill -9 $PIDS 2>/dev/null
    echo "      Killed processes: $PIDS"
else
    echo "      No services found running on ports 5000, 5001, 5173."
fi

echo "[3/3] Cleanup complete."
echo ""
echo "   All services stopped."
echo ""
echo "Closing terminal in 3 seconds..."
sleep 3

# Attempt to close the terminal window
# For GNOME/KDE/XFCE/macOS standard terminals
kill -9 $PPID 2>/dev/null
exit 0
