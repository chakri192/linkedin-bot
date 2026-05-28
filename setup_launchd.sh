#!/usr/bin/env zsh
# Replaces cron with launchd agents — fires even after Mac wakes from sleep
# Run once: chmod +x setup_launchd.sh && ./setup_launchd.sh

BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$(which python3)"
PLIST_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$PLIST_DIR"

# ── Morning: 8:00 AM IST ──────────────────────────────────────────────────────
cat > "$PLIST_DIR/com.linkedinbot.morning.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.linkedinbot.morning</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$BOT_DIR/post.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$BOT_DIR</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
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

# ── Afternoon: 1:00 PM IST ────────────────────────────────────────────────────
cat > "$PLIST_DIR/com.linkedinbot.afternoon.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.linkedinbot.afternoon</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$BOT_DIR/post.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$BOT_DIR</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>13</integer>
        <key>Minute</key>
        <integer>0</integer>
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

# ── Token check: 8:05 AM IST ──────────────────────────────────────────────────
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

# ── Load all agents ───────────────────────────────────────────────────────────
for plist in morning afternoon tokencheck; do
    launchctl unload "$PLIST_DIR/com.linkedinbot.$plist.plist" 2>/dev/null
    launchctl load "$PLIST_DIR/com.linkedinbot.$plist.plist"
    echo "Loaded: com.linkedinbot.$plist"
done

echo ""
echo "Done. Jobs scheduled:"
echo "  08:00 IST — post.py"
echo "  08:05 IST — check_token.py"
echo "  13:00 IST — post.py"
echo ""
echo "Verify: launchctl list | grep linkedinbot"
echo "Logs:   tail -f $BOT_DIR/logs/launchd.log"
echo ""
echo "NOTE: launchd fires the missed job as soon as Mac wakes up if it was asleep at the scheduled time."
