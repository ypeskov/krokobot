#!/usr/bin/env python3
"""Detect the stray 'court'/'count' filler-token degeneration and auto-/compact the session.

Background: the assistant intermittently emits a stray English token
("court" or "count") glued to the seam between a preamble text block and a tool call.
Measured over ~2400 turns: the failure is self-reinforcing — each instance left in the
transcript raises the odds of the next one (0.1% with no prior examples, 17% once 16+
are in context). Compaction removes the examples and resets the rate.

This guard tails the live session transcript, and when the pattern crosses a threshold
it injects `/compact` into the bot's tmux session, exactly as the developer would type it.

Called once a minute from claude-watchdog.sh. Exits silently when there is nothing to do.
"""
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

PROJECT_DIR = botconfig.PROJECT_DIR
STATE = os.path.join(botconfig.STATE_DIR, "court-guard-state")
LOG = os.path.join(botconfig.LOG_ROOT, "scripts", "court-guard.log")
TMUX_SESSION = botconfig.TMUX_SESSION

WINDOW_MIN = 30        # look back this far
THRESHOLD = 3          # this many hits in the window trips the guard
COOLDOWN_MIN = 90      # don't compact again within this many minutes
MIN_CONTEXT = 120_000  # below this a compact costs more than it saves
TAIL_LINES = 400       # transcript lines to scan

TOKEN = re.compile(r"\b(court|count)\b", re.I)
TRAILING = re.compile(r"\b(court|count)\b[\s]*$", re.I)


def log(msg):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as fh:
        fh.write("%s — %s\n" % (datetime.now(timezone.utc).isoformat(timespec="seconds"), msg))


def newest_transcript():
    files = glob.glob(os.path.join(PROJECT_DIR, "*.jsonl"))
    return max(files, key=os.path.getmtime) if files else None


def is_degenerate(text):
    """True if this text block carries the stray token rather than discussing it."""
    t = text.strip()
    if not t or not TOKEN.search(t):
        return False
    words = t.split()
    hits = len(TOKEN.findall(t))
    # Long prose that merely mentions the word (e.g. me reporting on this very bug).
    if len(words) > 80 and hits / len(words) < 0.05:
        return False
    return bool(TRAILING.search(t)) or len(words) <= 8 or hits >= 3


def scan(path, since):
    """Return (hits_in_window, latest_context_tokens).

    Hits older than the most recent compaction don't count: compaction is the cure,
    so anything before it has already been dealt with and must not re-trigger.
    """
    try:
        out = subprocess.run(["tail", "-n", str(TAIL_LINES), path],
                             capture_output=True, text=True, timeout=20).stdout
    except Exception as exc:
        log("tail failed: %s" % exc)
        return 0, 0
    lines = out.splitlines()
    for line in lines:
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("isCompactSummary") or rec.get("subtype") == "compact_boundary":
            ts = rec.get("timestamp") or ""
            if ts > since:
                since = ts
    hits, ctx = 0, 0
    for line in lines:
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("type") != "assistant":
            continue
        ts = rec.get("timestamp") or ""
        msg = rec.get("message") or {}
        usage = msg.get("usage") or {}
        total = (usage.get("input_tokens", 0)
                 + usage.get("cache_read_input_tokens", 0)
                 + usage.get("cache_creation_input_tokens", 0))
        if total:
            ctx = total
        if ts < since:
            continue
        for blk in msg.get("content") or []:
            if isinstance(blk, dict) and blk.get("type") == "text" and is_degenerate(blk.get("text") or ""):
                hits += 1
                break
    return hits, ctx


def in_cooldown():
    if not os.path.exists(STATE):
        return False
    return (time.time() - os.path.getmtime(STATE)) < COOLDOWN_MIN * 60


def notify(text):
    """Best-effort ping to the operator so an auto-compact is never silent."""
    try:
        botconfig.notify_owner(text)
    except Exception:
        pass


def main():
    path = newest_transcript()
    if not path:
        return
    since = (datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MIN)).isoformat(timespec="seconds").replace("+00:00", "Z")
    hits, ctx = scan(path, since)
    if hits < THRESHOLD:
        return
    if ctx < MIN_CONTEXT:
        log("threshold hit (%d) but context only %d, skipping" % (hits, ctx))
        return
    if in_cooldown():
        log("threshold hit (%d) but within cooldown, skipping" % hits)
        return
    if subprocess.run(["tmux", "has-session", "-t", TMUX_SESSION],
                      capture_output=True).returncode != 0:
        log("threshold hit (%d) but tmux session missing" % hits)
        return

    subprocess.run(["tmux", "send-keys", "-t", TMUX_SESSION, "/compact", "Enter"],
                   capture_output=True)
    open(STATE, "w").write(datetime.now(timezone.utc).isoformat(timespec="seconds"))
    log("AUTO-COMPACT sent: %d hits in last %dm, context=%d, transcript=%s"
        % (hits, WINDOW_MIN, ctx, os.path.basename(path)))
    notify("[bot] auto-/compact: %d stray tokens in %d min, context %dK. "
           "Session compacted automatically." % (hits, WINDOW_MIN, ctx // 1000))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # never let the guard break the watchdog
        log("guard crashed: %s" % exc)
        sys.exit(0)
