#!/usr/bin/env python3
"""
Scheduler — runs every 5 minutes via launchd.
Decides if it's time to post based on the randomised daily windows defined in
WINDOWS below (currently a single morning window; add more tuples to enable
afternoon/evening posts).

Each day, a random minute is picked within each window.
The chosen times are stored in .schedule.json and regenerated at midnight.
"""

import json, random, subprocess, sys
from pathlib import Path
from datetime import date, datetime

SCHEDULE_FILE = Path(".schedule.json")
BOT_DIR       = Path(__file__).parent
PYTHON        = sys.executable

WINDOWS = [
    ("morning",   8,  0,  8, 55),
]

# If the Mac was asleep at the chosen time, still post on wake -- but only up to
# this many hours after the window ends, so a missed morning post doesn't go
# out in the middle of the night.
MAX_LATE_HOURS = 3


def generate_schedule() -> dict:
    today = str(date.today())
    slots = {}
    for name, h_start, m_start, h_end, m_end in WINDOWS:
        total_start = h_start * 60 + m_start
        total_end   = h_end   * 60 + m_end
        chosen = random.randint(total_start, total_end)
        slots[name] = {"hour": chosen // 60, "minute": chosen % 60, "posted": False}
    return {"date": today, "slots": slots}


def load_schedule() -> dict:
    today = str(date.today())
    if SCHEDULE_FILE.exists():
        try:
            data = json.loads(SCHEDULE_FILE.read_text())
            if data.get("date") == today:
                return data
        except (json.JSONDecodeError, ValueError):
            pass
    # Generate fresh schedule for today
    data = generate_schedule()
    SCHEDULE_FILE.write_text(json.dumps(data, indent=2))
    print(f"New schedule for {today}:")
    for name, slot in data["slots"].items():
        print(f"  {name}: {slot['hour']:02d}:{slot['minute']:02d}")
    return data


def save_schedule(data: dict):
    SCHEDULE_FILE.write_text(json.dumps(data, indent=2))


def main():
    now   = datetime.now()
    data  = load_schedule()
    slots = data["slots"]

    ends = {name: h_end * 60 + m_end for name, _, _, h_end, m_end in WINDOWS}
    now_mins = now.hour * 60 + now.minute
    for name, slot in slots.items():
        if slot["posted"]:
            continue
        due = slot["hour"] * 60 + slot["minute"]
        latest = ends.get(name, due) + MAX_LATE_HOURS * 60
        if due <= now_mins <= latest:
            print(f"[{now:%H:%M}] Firing {name} post (scheduled {slot['hour']:02d}:{slot['minute']:02d})")
            result = subprocess.run(
                [PYTHON, str(BOT_DIR / "post.py")],
                cwd=str(BOT_DIR),
            )
            slot["posted"] = result.returncode == 0
            if not slot["posted"]:
                print(f"post.py exited with code {result.returncode} — will not retry this slot.")
            save_schedule(data)
            return  # only one post per scheduler run

    print(f"[{now:%H:%M}] No post due. Schedule: " +
          ", ".join(f"{n} {s['hour']:02d}:{s['minute']:02d}{'(done)' if s['posted'] else ''}"
                    for n, s in slots.items()))


if __name__ == "__main__":
    main()
