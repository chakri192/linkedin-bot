#!/usr/bin/env zsh
# Sets up cron jobs for 8:00 AM IST and 1:00 PM IST (= 2:30 UTC and 7:30 UTC)
# Run once: chmod +x cron_setup.sh && ./cron_setup.sh

BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$(which python3)"
LOG_DIR="$BOT_DIR/logs"
mkdir -p "$LOG_DIR"

# IST = UTC+5:30
# 08:00 IST = 02:30 UTC
# 13:00 IST = 07:30 UTC

CRON_MORNING="30 2 * * * cd $BOT_DIR && $PYTHON $BOT_DIR/post.py >> $LOG_DIR/cron.log 2>&1"
CRON_AFTERNOON="30 7 * * * cd $BOT_DIR && $PYTHON $BOT_DIR/post.py >> $LOG_DIR/cron.log 2>&1"

(crontab -l 2>/dev/null | grep -v "linkedin-bot"; echo "$CRON_MORNING"; echo "$CRON_AFTERNOON") | crontab -

echo "✓ Cron jobs installed:"
echo "  08:00 IST → $PYTHON $BOT_DIR/post.py"
echo "  13:00 IST → $PYTHON $BOT_DIR/post.py"
echo ""
echo "Verify with: crontab -l"
echo "Live logs:   tail -f $LOG_DIR/cron.log"

 
