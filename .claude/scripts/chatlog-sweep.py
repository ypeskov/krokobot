#!/usr/bin/env python3
"""Reconcile the chat log against the session transcript. Runs every minute.

Why this exists, and why the UserPromptSubmit hook was not enough:

Telegram messages reach me by two different paths. Some arrive as a prompt and fire
UserPromptSubmit, which chatlog-writer.py catches. Others are injected *mid-turn*, while
I am already working, and those never fire that hook at all. On 2026-08-14 three of four
sampled mid-turn messages were missing from the log, silently, for a whole day. A busy
chat plus a busy bot means the busiest moments are exactly the ones that go unrecorded,
which is the worst possible bias for a log meant to survive compaction.

The transcript does not have that blind spot: whatever I saw is in it, by either path.
So the transcript is the source of truth and this script reconciles the log to it.

Deduplication is by *count of identical rendered lines* rather than by message id. Both
writers render a message byte-identically (see chatlog_common), so a line the hook
already wrote is simply found on disk and skipped. Counting rather than set-membership
keeps genuine repeats: two identical one-word turns in the same minute stay two lines.

Prints nothing on success. Diagnostics to stderr.
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import botconfig  # noqa: E402
import chatlog_common as C  # noqa: E402

PROJECT_DIR = botconfig.PROJECT_DIR
# A minute's worth of traffic needs a few dozen transcript lines; 4000 is slack for a
# watchdog that may have been down for hours. Pass a bigger number as argv[1] for a
# one-off deep backfill after a gap is discovered.
TAIL_LINES = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
MAX_APPEND = 500           # backstop: never rewrite history wholesale in one pass


def transcript_lines() -> list[tuple[str, "C.datetime", str]]:
    """Rendered log lines for every <channel> block in the newest transcript tail."""
    files = sorted(glob.glob(os.path.join(PROJECT_DIR, "*.jsonl")), key=os.path.getmtime)
    if not files:
        return []
    try:
        out = subprocess.run(["tail", "-n", str(TAIL_LINES), files[-1]],
                             capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return []

    found: list[tuple[str, "C.datetime", str]] = []
    for raw in out.splitlines():
        try:
            o = json.loads(raw)
        except Exception:
            continue
        m = o.get("message") or {}
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str):
            txt = c
        elif isinstance(c, list):
            txt = "".join(x.get("text", "") for x in c
                          if isinstance(x, dict) and x.get("type") == "text")
        else:
            continue
        if "<channel" not in txt:
            continue
        found.extend(C.parse_channels(txt))
    return found


def main() -> int:
    wanted = transcript_lines()
    if not wanted:
        return 0

    # Group by the file each line belongs to, so every day file is read once.
    by_path: dict[str, list[tuple[str, "C.datetime", str]]] = {}
    for chat_id, when, line in wanted:
        by_path.setdefault(C.day_path(chat_id, when), []).append((chat_id, when, line))

    appended = 0
    for path, items in by_path.items():
        have: Counter = Counter()
        if os.path.exists(path):
            with open(path, encoding="utf-8", errors="replace") as f:
                have.update(l.rstrip("\n") for l in f)

        want = Counter(line for _, _, line in items)
        missing = want - have
        if not missing:
            continue

        # Preserve transcript order among the lines actually being added.
        budget = Counter(missing)
        for chat_id, when, line in items:
            if budget[line] <= 0:
                continue
            budget[line] -= 1
            C.append(chat_id, when, line)
            appended += 1
            if appended >= MAX_APPEND:
                sys.stderr.write(f"chatlog-sweep: hit MAX_APPEND at {path}\n")
                return 0
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        sys.stderr.write(f"chatlog-sweep: {exc}\n")
        sys.exit(0)
