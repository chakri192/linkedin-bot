#!/usr/bin/env zsh
# Sets up a single launchd agent that runs scheduler.py every 5 minutes.
# scheduler.py picks 3 random times per day across morning/afternoon/evening windows.
# Fires missed runs on Mac wake — no missed posts from sleep.
# Run once: chmod +x setup_launchd.sh && ./setup_launchd.sh

BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$(which python3)"
PLIST_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$PLIST_DIR"
mkdir -p "$BOT_DIR/logs"

# ── Remove old individual agents if present ───────────────────────────────────
for old in morning afternoon tokencheck; do
    plist="$PLIST_DIR/com.linkedinbot.$old.plist"
    if [[ -f "$plist" ]]; then
        launchctl unload "$plist" 2>/dev/null
        rm "$plist"
        echo "Removed old agent: com.linkedinbot.$old"
    fi
done

# ── Scheduler: every 5 minutes ────────────────────────────────────────────────
cat > "$PLIST_DIR/com.linkedinbot.scheduler.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.linkedinbot.scheduler</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$BOT_DIR/scheduler.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$BOT_DIR</string>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>StandardOutPath</key>
    <string>$BOT_DIR/logs/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$BOT_DIR/logs/launchd.log</string>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
PLIST

# ── Token check: once daily at 8:05 AM ───────────────────────────────────────
cat > "$PLIST_DIR/com.linkedinbot.tokencheck.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.linkedinbot.tokencheck</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$BOT_DIR/check_token.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$BOT_DIR</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>5</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$BOT_DIR/logs/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$BOT_DIR/logs/launchd.log</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST

# ── Load agents ───────────────────────────────────────────────────────────────
for plist in scheduler tokencheck; do
    launchctl unload "$PLIST_DIR/com.linkedinbot.$plist.plist" 2>/dev/null
    launchctl load "$PLIST_DIR/com.linkedinbot.$plist.plist"
    echo "Loaded: com.linkedinbot.$plist"
done

echo ""
echo "Done. Scheduler runs every 5 minutes."
echo "Post time is randomised daily between 08:00 – 08:55"
echo ""
echo "Verify:  launchctl list | grep linkedinbot"
echo "Preview: python3 scheduler.py"
echo "Logs:    tail -f $BOT_DIR/logs/launchd.log"
