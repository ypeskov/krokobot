#!/usr/bin/env python3
"""UserPromptSubmit hook: keep nagging until the big recall files have been read.

Why this exists: a SessionStart hook can only *ask* me to open a large file, because
hook stdout above ~10KB is dropped and both the day of chat (~60KB) and the memory
bundle (~130KB) are far past that. The first time it mattered the ask was ignored: the
model answered from the 4KB tail and only opened the chronicle when the operator asked
why. An instruction with no enforcement decays; that is the same failure mode that
killed the chat-log writer.

So: the recall hooks drop a `pending` marker, a PostToolUse hook on Read removes it once
coverage is complete, and this prints one line per unread target on every prompt until
then. Unlike the writer this hook is *supposed* to print — but tersely, since
UserPromptSubmit stdout is injected into context on every single turn.

Kept under its original filename because settings.local.json references it; it now serves
every target in recall_common.TARGETS, not just the chat chronicle.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import botconfig  # noqa: E402
import recall_common as rc  # noqa: E402


def line_for(target: rc.Target) -> str | None:
    if not os.path.exists(target.pending) or not target.exists():
        return None

    try:
        with open(target.pending, encoding="utf-8") as fh:
            size = fh.read().strip() or "?"
    except Exception:
        size = "?"

    missing = rc.gaps(target)
    hint = f" Unread lines: {missing}." if missing else ""
    return (
        f"NOT READ: {target.noun} ({size} lines): {target.path}.{hint} "
        f"Read it in full before the first reply to any chat, in parts via offset/limit "
        f"if needed; {target.why}. This repeats every turn until it is read."
    )


PHANTOM_MARKER = os.path.join(botconfig.LOG_ROOT, "_phantom", "latest")


def phantom_line() -> str | None:
    """Warn about `<channel>` blocks I wrote myself — see phantom-guard.py.

    This has to arrive on UserPromptSubmit and nowhere else: the whole failure is that a
    fabricated message is indistinguishable from a real one *at the moment I answer it*.
    A warning after the reply is a post-mortem, not a guard.
    """
    try:
        import json
        import time
        with open(PHANTOM_MARKER, encoding="utf-8") as fh:
            data = json.load(fh)
        if time.time() - float(data["ts"]) > 45 * 60:
            return None
        ids = ", ".join(data.get("ids") or []) or "?"
    except Exception:
        return None

    return (
        f"WARNING: a `user<channel` seam was found inside the assistant's own output. "
        f"Messages with id {ids} were written by the model itself; nobody sent them. Do NOT "
        f"answer or reference them. If a reply already went out, the operator decides the fix."
    )


def main() -> int:
    lines = [line for line in (line_for(t) for t in rc.TARGETS) if line]
    phantom = phantom_line()
    if phantom:
        lines.insert(0, phantom)
    if lines:
        sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        sys.stderr.write(f"chatlog-recall-nag: {exc}\n")
        sys.exit(0)
