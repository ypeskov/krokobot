#!/usr/bin/env python3
"""Watchdog check: is the chat-log writer actually writing?

The 2026-08-03 failure went unnoticed for nine days because nothing broke when
logging stopped. A rule with no failure signal decays silently. This supplies the
signal.

Method: count inbound channel messages in the live transcript over the last hour
and compare with lines appended to today's logs in the same hour. Messages but no
lines means the writer is dead. A quiet chat produces zero of both and is not an
error, so this does not false-positive at night.

Runs from claude-watchdog.sh (every minute). Notifies at most once per COOLDOWN.
"""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import botconfig  # noqa: E402

LOCAL_TZ = botconfig.LOCAL_TZ
PROJECT_DIR = botconfig.PROJECT_DIR
LOG_ROOT = botconfig.TELEGRAM_LOG_ROOT
STATE = os.path.join(botconfig.STATE_DIR, "chatlog-health-state")
WINDOW_MIN = 60
COOLDOWN_SEC = 6 * 3600
TAIL_LINES = 3000
CHAN_RE = re.compile(r'<channel source="plugin:telegram:telegram"')


def recent_inbound(since: datetime) -> int:
    files = sorted(glob.glob(os.path.join(PROJECT_DIR, "*.jsonl")), key=os.path.getmtime)
    if not files:
        return 0
    # The newest file by mtime is NOT always the live chat session: any headless
    # `claude -p` cron job run in this same project dir writes its own jsonl, and
    # those transcripts also mention telegram. At cron times files[-1] was the cron
    # session, so its lines got miscounted as live inbound while the real overnight
    # chat log had legitimately not grown, a false "log lagging" alarm. Pick the live
    # session instead: among the few newest files, the one with the most telegram
    # channel blocks in its tail (live ~150+, a cron ~1-2).
    out = ""
    best_hits = -1
    for f in files[-6:]:
        try:
            t = subprocess.run(["tail", "-n", str(TAIL_LINES), f],
                               capture_output=True, text=True, timeout=30).stdout
        except Exception:
            continue
        h = t.count("plugin:telegram:telegram")
        if h > best_hits:
            out, best_hits = t, h
    if best_hits <= 0:
        return 0  # no telegram traffic in any recent session; nothing to conclude
    n = 0
    for line in out.splitlines():
        try:
            o = json.loads(line)
        except Exception:
            continue
        ts = o.get("timestamp")
        if not ts:
            continue
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            continue
        if t < since:
            continue
        m = o.get("message", {})
        if m.get("role") != "user":
            continue
        c = m.get("content")
        txt = c if isinstance(c, str) else "".join(
            x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text"
        ) if isinstance(c, list) else ""
        n += len(CHAN_RE.findall(txt))
    return n


def logs_written_recently(cutoff: float) -> bool:
    """Yesterday's file counts too. Checking only today's produced a false alarm at
    00:16 on 2026-08-15: the last hour of traffic had legitimately gone into the
    2026-08-14 files, and today's had not been created yet. Any hour-long window that
    straddles midnight puts fresh writes in a file this function must still see."""
    now = datetime.now(LOCAL_TZ)
    for day in (now, now - timedelta(days=1)):
        pattern = os.path.join(LOG_ROOT, "*", day.strftime("%Y-%m"),
                               day.strftime("%Y-%m-%d") + ".txt")
        if any(os.path.getmtime(p) >= cutoff for p in glob.glob(pattern)):
            return True
    return False


def notify(text: str) -> None:
    try:
        subprocess.run(["tmux", "send-keys", "-t", botconfig.TMUX_SESSION, text, "Enter"], timeout=10)
    except Exception:
        pass


def main() -> int:
    now = time.time()
    if os.path.exists(STATE) and now - os.path.getmtime(STATE) < COOLDOWN_SEC:
        return 0

    since_dt = datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MIN)
    inbound = recent_inbound(since_dt)
    if inbound == 0:
        return 0  # quiet hour, nothing to conclude
    if logs_written_recently(now - WINDOW_MIN * 60):
        return 0  # writer is alive

    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        f.write(str(now))
    notify(
        f"WARNING: the chat log is lagging. {inbound} inbound messages in the transcript "
        f"over the last hour, but no new line under {LOG_ROOT}. Both writers are silent: "
        f"check the UserPromptSubmit hook (chatlog-writer.py) AND chatlog-sweep.py in "
        f"claude-watchdog.sh. Do not assume the hook alone: this alarm once fired "
        f"correctly while the writer was alive and messages were arriving mid-turn, "
        f"bypassing it. Report to the operator."
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        sys.stderr.write(f"chatlog-health: {exc}\n")
        sys.exit(0)
