#!/usr/bin/env python3
"""Catch `<channel>` blocks that I wrote myself and warn before I answer them.

Observed once: 34 inbound Telegram messages in one session never existed. They sat
inside the model's own assistant turns, glued on with a `user<channel ...>` seam: it
finished a short line, generation did not stop at the turn boundary, and it wrote the
next speaker's message itself, with plausible text, a nearby message_id and a timestamp
a few minutes ahead. On the following turn that text is in context and is
indistinguishable from a real message, so the model answers it. Twice it made the bot
contradict a real person who correctly said "I never wrote that", and once it put an
uninvited message in a group chat.

The trigger is a long run of near-identical short turns, the shape "not for me, staying
silent" reporting produces. Same family as the court/count artifact handled by
court-guard.py: junk at the seam between blocks, amplified by self-imitation.

Run from claude-watchdog.sh every minute. Writes a marker naming the fake message_ids;
the UserPromptSubmit nag prints it so the warning lands *before* the reply, not after.
Prints nothing itself.
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import botconfig  # noqa: E402

PROJECT_DIR = botconfig.PROJECT_DIR
MARKER = os.path.join(botconfig.LOG_ROOT, "_phantom", "latest")
STATE = os.path.join(botconfig.LOG_ROOT, "_phantom", "seen.json")

SEAM = re.compile(r"(?:^|\n)\s*user<channel")
MID = re.compile(r'message_id="(\d+)"')
TAIL_LINES = 400          # enough for a few turns, cheap to scan every minute
FRESH_SEC = 45 * 60       # how long a sighting stays worth warning about


def newest_transcript() -> str | None:
    files = glob.glob(os.path.join(PROJECT_DIR, "*.jsonl"))
    return max(files, key=os.path.getmtime) if files else None


def scan(path: str) -> list[str]:
    """message_ids of self-authored channel blocks in the tail of the transcript."""
    with open(path, "rb") as fh:
        try:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - 3_000_000))
            tail = fh.read().decode("utf-8", "ignore").splitlines()[-TAIL_LINES:]
        except Exception:
            return []

    found: list[str] = []
    for line in tail:
        if "<channel" not in line:
            continue
        try:
            data = json.loads(line)
        except Exception:
            continue
        if data.get("type") != "assistant":
            continue
        for block in data.get("message", {}).get("content", []) or []:
            text = block.get("text") or ""
            if block.get("type") == "text" and SEAM.search(text):
                m = MID.search(text)
                found.append(m.group(1) if m else "?")
    return found


def main() -> int:
    path = newest_transcript()
    if not path:
        return 0

    found = scan(path)
    os.makedirs(os.path.dirname(MARKER), exist_ok=True)

    # Only warn about sightings that are new since the last run: an old one stays in the
    # transcript forever and a permanent warning is a warning nobody reads.
    seen: set[str] = set()
    try:
        with open(STATE, encoding="utf-8") as fh:
            state = json.load(fh) or {}
        if state.get("path") == path:
            seen = set(state.get("ids", []))
    except Exception:
        pass

    fresh = [i for i in found if i not in seen]
    with open(STATE, "w", encoding="utf-8") as fh:
        json.dump({"path": path, "ids": sorted(set(found) | seen)}, fh)

    if fresh:
        with open(MARKER, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.time(), "ids": fresh}, ensure_ascii=False))
    elif os.path.exists(MARKER):
        try:
            age = time.time() - json.load(open(MARKER, encoding="utf-8"))["ts"]
            if age > FRESH_SEC:
                os.remove(MARKER)
        except Exception:
            os.remove(MARKER)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        sys.stderr.write(f"phantom-guard: {exc}\n")
        sys.exit(0)
