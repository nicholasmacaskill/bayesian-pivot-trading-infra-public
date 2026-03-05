#!/bin/bash

# Configuration
VENV_PATH="./venv/bin/activate"
RUNNER_PATH="src/runners/local_scanner.py"

echo "🫧 Bayesian Pivot Trading Infra: Local Runner (Anti-Sleep Mode)"
echo "-----------------------------------------------"

# Check for venv
if [ -f "$VENV_PATH" ]; then
    source "$VENV_PATH"
else
    echo "⚠️  Warning: Virtual environment not found at $VENV_PATH. Using system python."
fi

# Clean up any "phantom" instances hanging around
echo "🧹 Cleaning up existing processes..."
pkill -9 -f "python src/runners/local_scanner.py" 2>/dev/null
pkill -9 -f "caffeinate -i -s python" 2>/dev/null
# DO NOT remove the lock file here; the old process holds the lock on the inode.
# Deleting it allows a new process to create a new lock on a new inode.

# Optimization flags
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
export MPLBACKEND=Agg

# Use caffeinate to prevent sleep while the script is running
# -i: prevent system idle sleep
# -s: prevent system sleep when on AC power
echo "🚀 Starting runner with anti-sleep protection..."
export PYTHONPATH=$PYTHONPATH:.
# Run in background but keep terminal output
caffeinate -i -s python "$RUNNER_PATH" &
RUNNER_PID=$!

# Wait for process
wait $RUNNER_PID

echo "🛑 Runner stopped. Anti-sleep protection disabled."
