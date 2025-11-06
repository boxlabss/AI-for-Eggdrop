#!/bin/bash

# Script to start Grok Flask API via Gunicorn
# Usage: ./grok_start.sh
# Stop: kill $(cat /tmp/grok.pid) or use echoed PID

SCRIPT_DIR="$(dirname "$0")"
VENV_DIR="$SCRIPT_DIR/env"
LOG_DIR="$SCRIPT_DIR/logs"  # Persistent logs; create if needed
mkdir -p "$LOG_DIR"

# Check and activate venv
if [ ! -d "$VENV_DIR" ]; then
    echo "Error: Venv not found at $VENV_DIR. Create with: python3 -m venv $VENV_DIR"
    exit 1
fi
source "$VENV_DIR/bin/activate"

# cd to script dir
cd "$SCRIPT_DIR" || { echo "Error: Failed to cd to $SCRIPT_DIR"; exit 1; }

# Run Gunicorn in background
gunicorn -w 4 -b 127.0.0.1:5000 xaiChatApi:app \
    --log-file "$LOG_DIR/gunicorn.log" \
    --access-logfile "$LOG_DIR/gunicorn_access.log" \
    --log-level debug &

PID=$!
sleep 1  # Brief wait for startup

# Verify if running
if ! ps -p $PID > /dev/null; then
    echo "Error: Gunicorn failed to start (PID $PID not found). Check logs: $LOG_DIR/gunicorn.log"
    exit 1
fi

# Save PID
echo $PID > /tmp/grok.pid
echo "Grok started: $PID (kill with: kill $PID or kill \$(cat /tmp/grok.pid))"
echo "Logs: $LOG_DIR/gunicorn.log and $LOG_DIR/gunicorn_access.log"
