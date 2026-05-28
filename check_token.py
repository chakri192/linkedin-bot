#!/usr/bin/env python3
import json, time, subprocess
from pathlib import Path

tokens = json.loads(Path(".tokens.json").read_text())
issued = Path(".tokens.json").stat().st_mtime
expires_in = tokens.get("expires_in", 5183999)
expires_at = issued + expires_in
remaining_days = (expires_at - time.time()) / 86400

if remaining_days < 7:
    subprocess.run([
        "osascript", "-e",
        f'display notification "LinkedIn token expires in {remaining_days:.0f} days. Run python3 auth.py" with title "LinkedIn Bot ⚠️"'
    ])
    print(f"WARNING: Token expires in {remaining_days:.0f} days")
else:
    print(f"Token OK — {remaining_days:.0f} days remaining")
