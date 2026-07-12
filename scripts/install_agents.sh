#!/bin/bash

# Configuration
PROJECT_DIR="/Users/nicholasmacaskill/sovereignSMC/bayesian-pivot-trading-infra"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python"
LOG_DIR="$HOME/Library/Logs/SovereignSMC"
PLIST_DIR="$HOME/Library/LaunchAgents"

mkdir -p "$LOG_DIR"
mkdir -p "$PLIST_DIR"

echo "Installing Sovereign SMC Launch Agents..."

# 1. Scanner Agent
cat << EOF > "$PLIST_DIR/com.sovereign.scanner.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sovereign.scanner</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_BIN</string>
        <string>src/runners/local_scanner.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/scanner.out.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/scanner.err.log</string>
</dict>
</plist>
EOF

# 2. Watchdog Agent
cat << EOF > "$PLIST_DIR/com.sovereign.watchdog.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sovereign.watchdog</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_BIN</string>
        <string>scripts/scanner_watchdog.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/watchdog.out.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/watchdog.err.log</string>
</dict>
</plist>
EOF

# 3. Sweep Watcher Agent
cat << EOF > "$PLIST_DIR/com.sovereign.sweepwatcher.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sovereign.sweepwatcher</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_BIN</string>
        <string>scripts/dynamic_sweep_watcher.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/sweepwatcher.out.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/sweepwatcher.err.log</string>
</dict>
</plist>
EOF

echo "Created plist files in $PLIST_DIR"

# Unload existing (if they exist) to allow reloading
echo "Unloading existing agents (if any)..."
launchctl unload "$PLIST_DIR/com.sovereign.scanner.plist" 2>/dev/null
launchctl unload "$PLIST_DIR/com.sovereign.watchdog.plist" 2>/dev/null
launchctl unload "$PLIST_DIR/com.sovereign.sweepwatcher.plist" 2>/dev/null

# Load agents
echo "Loading agents..."
launchctl load "$PLIST_DIR/com.sovereign.scanner.plist"
launchctl load "$PLIST_DIR/com.sovereign.watchdog.plist"
launchctl load "$PLIST_DIR/com.sovereign.sweepwatcher.plist"

echo "✅ All agents installed and started!"
echo "You can view logs in $LOG_DIR"
