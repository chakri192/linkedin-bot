#!/usr/bin/env python3
import json, time, subprocess
from pathlib import Path

tokens = json.loads(Path(".tokens.json").read_text())
issued = Path(".tokens.json").stat().st_mtime
expires_in = tokens.get("expires_in", 5183999)
expires_at = issued + expires_in
remaining_days = (expires_at - time.time()) / 86400

def notify(title, message):
    subprocess.run([
        "osascript", "-e",
        f'display notification "{message}" with title "{title}" sound name "Basso"'
    ])

if remaining_days <= 0:
    notify("LinkedIn Bot 🔴 EXPIRED", "Token expired! Run python3 auth.py NOW or posts will fail.")
    print("ERROR: Token has expired. Run python3 auth.py immediately.")
elif remaining_days <= 1:
    notify("LinkedIn Bot 🔴 EXPIRES TODAY", "Run python3 auth.py NOW before posts fail tonight.")
    print(f"URGENT: Token expires in {remaining_days:.1f} days.")
elif remaining_days <= 7:
    notify("LinkedIn Bot ⚠️ Token Expiring Soon", f"Token expires in {remaining_days:.0f} days. Run python3 auth.py now.")
    print(f"WARNING: Token expires in {remaining_days:.0f} days. Run python3 auth.py now.")
else:
    print(f"Token OK — {remaining_days:.0f} days remaining")
