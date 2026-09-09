#!/usr/bin/env python3
"""SessionStart hook: after a compact/restart, put the last 24h of chat back in context.

SessionStart is one of the few hooks whose stdout Claude actually sees, which is
what makes this possible at all. PreCompact runs too early and PostCompact output
is not injected.

Cost, measured on 2026-08-12 (a heavy day: ~400 messages across the day):
~41k characters ≈ 16-20k tokens ≈ 3% of a 600k window. Cheap enough to do every
time; the cap below exists for the day that is three times heavier.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import botconfig  # noqa: E402
import recall_common as rc  # noqa: E402

LOCAL_TZ = botconfig.LOCAL_TZ
LOG_ROOT = botconfig.TELEGRAM_LOG_ROOT
TARGET = next(t for t in rc.TARGETS if t.key == "chatlog")
WINDOW_HOURS = 24
# Hard-won on 2026-08-13: hook stdout above ~10KB is NOT injected into context —
# the harness persists it and shows only a head preview, so the OLDEST lines
# survive and the recent hours, the ones that matter, are lost. Note the units:
# the threshold is bytes, and Cyrillic costs two bytes per character.
#
# Truncating a day down to whatever fits would throw away the substance to satisfy
# the format. So don't truncate: write the full chronicle to a file with a stable
# name and print a short pointer plus the freshest lines. One deliberate Read then
# brings back the whole day at full fidelity.
#
# 7500 bytes measured against the cap on 2026-08-13: header runs ~350 bytes, so the
# whole payload lands near 8KB and stays inline with room to spare. Do not push this
# to 9000 "because it fits" — one long spam message in the tail and the entire recall
# silently stops arriving, which is the exact failure this design exists to avoid.
INLINE_BYTES = 7_500
RECALL_FILE = TARGET.path
# Reading the full chronicle is voluntary, and voluntary is how the chat-log writer
# died. This marker makes it enforceable: written here, cleared by a PostToolUse hook
# when the file is actually Read, and nagged about on every prompt until then.
PENDING_FILE = TARGET.pending

# ...but only when context was actually lost. A `resume` or `startup` replays the
# transcript, so the day is already in the window and the nag would demand a 50KB read
# for nothing. `compact` and `clear` are the events that genuinely drop it. Learned
# 2026-08-13, within an hour of shipping the marker: it fired on a restart while the
# whole conversation was still in context.
NAG_SOURCES = {"compact", "clear"}


def day_file(chat: str, day: datetime) -> str:
    return os.path.join(LOG_ROOT, chat, day.strftime("%Y-%m"), day.strftime("%Y-%m-%d") + ".txt")


def read_window(chat: str, now: datetime) -> list[str]:
    """Lines from the last WINDOW_HOURS. Files are per-day with [HH:MM] prefixes,
    so yesterday's file is filtered by clock time and today's is taken whole."""
    out: list[str] = []
    cutoff = (now - timedelta(hours=WINDOW_HOURS)).strftime("%H:%M")

    yday = day_file(chat, now - timedelta(days=1))
    if os.path.exists(yday):
        with open(yday, encoding="utf-8", errors="replace") as f:
            for line in f:
                stamp = line[1:6]
                if len(line) > 6 and line[0] == "[" and stamp >= cutoff:
                    out.append(line.rstrip("\n"))

    today = day_file(chat, now)
    if os.path.exists(today):
        with open(today, encoding="utf-8", errors="replace") as f:
            out.extend(l.rstrip("\n") for l in f)
    return out


def start_source() -> str:
    """Why the session started, per the SessionStart payload. Unreadable stdin means
    the hook was run by hand, and a manual run should not arm the nag."""
    try:
        return (json.load(sys.stdin) or {}).get("source") or ""
    except Exception:
        return ""


def main() -> int:
    # Cron digests run `claude -p` in this project and fire SessionStart as well; they
    # must not rewrite the chronicle or re-arm the nag for the live bot.
    if rc.is_headless_session():
        return 0

    source = start_source()
    now = datetime.now(LOCAL_TZ)
    blocks: list[tuple[str, list[str]]] = []

    if not os.path.isdir(LOG_ROOT):
        return 0
    for chat in sorted(os.listdir(LOG_ROOT)):
        if not os.path.isdir(os.path.join(LOG_ROOT, chat)):
            continue
        lines = read_window(chat, now)
        if lines:
            blocks.append((chat, lines))

    if not blocks:
        return 0

    header = (
        f"Chat chronicle for the last {WINDOW_HOURS} h "
        f"(up to {now:%Y-%m-%d %H:%M} {botconfig.LOCAL_TZ_NAME}). "
        f"These are facts from disk, not the model's recollection."
    )
    full = [header]
    for chat, lines in blocks:
        full.append(f"\n### {chat}\n" + "\n".join(lines))
    body = "\n".join(full) + "\n"

    os.makedirs(os.path.dirname(RECALL_FILE), exist_ok=True)
    with open(RECALL_FILE, "w", encoding="utf-8") as f:
        f.write(body)

    total_lines = sum(len(ls) for _, ls in blocks)
    if source in NAG_SOURCES:
        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            f.write(f"{total_lines}\n")
    else:
        # A stale marker from an earlier compact would keep nagging about a chronicle
        # that this session can already see, so clear it.
        try:
            os.remove(PENDING_FILE)
        except FileNotFoundError:
            pass

    # Freshest lines first in importance: fill the inline budget from the end.
    flat = [l for _, ls in blocks for l in ls]
    tail: list[str] = []
    used = 0
    for line in reversed(flat):
        cost = len(line.encode()) + 1
        if used + cost > INLINE_BYTES:
            break
        tail.insert(0, line)
        used += cost

    out = [
        header,
        f"{total_lines} lines across {len(blocks)} chat(s). Written in full to "
        f"{RECALL_FILE}. Read that file completely before answering in any chat, "
        f"otherwise you only know the last few minutes.",
        f"\nThe last {len(tail)} lines, for orientation:",
        *tail,
    ]
    sys.stdout.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        sys.stderr.write(f"chatlog-recall: {exc}\n")
        sys.exit(0)  # a broken recall must never block session start
