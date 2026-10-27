#!/bin/bash
# Toggle Tablet Mode on HP ENVY x360
PID=$(pgrep -f "tablet-rotation-daemon.py")
if [ -n "$PID" ]; then
    kill -USR1 "$PID"
    echo "[✓] Sent tablet mode toggle signal (SIGUSR1) to daemon (PID: $PID)"
else
    echo "[!] tablet-rotation-daemon.py is not running!"
    systemctl --user restart tablet-rotation.service
    echo "[✓] Restarted tablet-rotation.service"
fi
