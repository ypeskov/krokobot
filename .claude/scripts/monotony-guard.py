#!/usr/bin/env python3
"""Break up a long run of short, tool-less turns before it starts writing other people.

Observed once: 34 `<channel>` blocks in one session turned out to be the model's own
writing. It finished a short line, generation did not stop at the turn boundary, and it
composed the next speaker's message itself (see `phantom-guard.py`). The soil for it was
a chain of hundreds of near-identical "staying silent" turns: in a busy chat where the
reply rule says stay silent, every inbound message still costs one turn, and the harness
will not accept an empty one. So the chain is structural, not a habit the model can
decide away.

Varying the wording does not help; eight different sentences that all mean "not for me"
are the same shape.

This is the court/count lesson one level up (see court-guard.py): the failure is
self-imitation, and the cure is not discipline but deleting the examples being copied.
`court-guard.py` already does exactly that for the stray-token case, so this guard is
deliberately the same machine with a different detector.

Called once a minute from claude-watchdog.sh. Exits silently when there is nothing to do.
"""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import botconfig  # noqa: E402

PROJECT_DIR = botconfig.PROJECT_DIR
STATE = os.path.join(botconfig.STATE_DIR, "monotony-guard-state")
LOG = os.path.join(botconfig.LOG_ROOT, "scripts", "monotony-guard.log")
TMUX_SESSION = botconfig.TMUX_SESSION

THRESHOLD = 15         # consecutive short tool-less turns that trip the guard
MAX_WORDS = 20         # above this a turn is real work, not a placeholder
COOLDOWN_MIN = 60      # don't compact again within this many minutes
# Measured in court-guard's dataset: zero degeneration below 100K of context across 4556
# turns. Below that the examples exist but the failure does not fire, and a compact would
# throw away a fresh session to fix nothing.
MIN_CONTEXT = 100_000
TAIL_LINES = 1200      # ~1 turn per line; must comfortably exceed THRESHOLD

WORD = re.compile(r"\w+", re.UNICODE)


def log(msg: str) -> None:
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as fh:
        fh.write("%s — %s\n" % (datetime.now(timezone.utc).isoformat(timespec="seconds"), msg))


def newest_transcript() -> str | None:
    files = glob.glob(os.path.join(PROJECT_DIR, "*.jsonl"))
    return max(files, key=os.path.getmtime) if files else None


def classify(rec: dict) -> str:
    """One of: 'short' (a placeholder turn), 'work' (resets the run), '' (ignored).

    A turn that calls a tool is work by definition — that is the shape of actually
    answering somebody, and it is what the chain never contains.
    """
    if rec.get("type") != "assistant" or rec.get("isSidechain"):
        return ""
    # Harness-authored error turns («Login expired · Please run /login», API failures) are
    # short, tool-less and can repeat for hours while the session is down. They are not my
    # output and there is nothing in them for me to imitate. Found on the first backtest:
    # they made the longest apparent run in the whole transcript, 44 turns of somebody
    # else's error message.
    if rec.get("isApiErrorMessage"):
        return ""
    msg = rec.get("message") or {}
    blocks = msg.get("content") or []
    if isinstance(blocks, str):
        blocks = [{"type": "text", "text": blocks}]

    text_parts = []
    for blk in blocks:
        if not isinstance(blk, dict):
            continue
        if blk.get("type") == "tool_use":
            return "work"
        if blk.get("type") == "text":
            text_parts.append(blk.get("text") or "")

    text = " ".join(text_parts).strip()
    if not text:
        # Pure thinking, or a continuation fragment. Neither a placeholder nor work.
        return ""
    return "short" if len(WORD.findall(text)) <= MAX_WORDS else "work"


def scan(path: str) -> tuple[int, int, str]:
    """Return (length of the run ending at the tail, latest context tokens, sample).

    Counting forward and resetting is equivalent to counting back from the end, and it
    handles the compact boundary for free: a compaction record clears the run, because
    after a compact the examples being imitated are gone.
    """
    try:
        out = subprocess.run(["tail", "-n", str(TAIL_LINES), path],
                             capture_output=True, text=True, timeout=20).stdout
    except Exception as exc:
        log("tail failed: %s" % exc)
        return 0, 0, ""

    run, ctx, sample = 0, 0, ""
    for line in out.splitlines():
        try:
            rec = json.loads(line)
        except Exception:
            continue

        if rec.get("isCompactSummary") or rec.get("subtype") == "compact_boundary":
            run, sample = 0, ""
            continue

        usage = ((rec.get("message") or {}).get("usage")) or {}
        total = (usage.get("input_tokens", 0)
                 + usage.get("cache_read_input_tokens", 0)
                 + usage.get("cache_creation_input_tokens", 0))
        if total:
            ctx = total

        kind = classify(rec)
        if kind == "short":
            run += 1
            for blk in (rec.get("message") or {}).get("content") or []:
                if isinstance(blk, dict) and blk.get("type") == "text" and (blk.get("text") or "").strip():
                    sample = (blk["text"].strip().splitlines() or [""])[0][:60]
                    break
        elif kind == "work":
            run, sample = 0, ""
    return run, ctx, sample


def in_cooldown() -> bool:
    if not os.path.exists(STATE):
        return False
    return (time.time() - os.path.getmtime(STATE)) < COOLDOWN_MIN * 60


def notify(text: str) -> None:
    """Best-effort ping to the operator so an auto-compact is never silent."""
    try:
        botconfig.notify_owner(text)
    except Exception:
        pass


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    path = newest_transcript()
    if not path:
        return 0

    run, ctx, sample = scan(path)
    if dry:
        print("run=%d context=%d threshold=%d sample=%r transcript=%s"
              % (run, ctx, THRESHOLD, sample, os.path.basename(path)))
        return 0

    if run < THRESHOLD:
        return 0
    if ctx < MIN_CONTEXT:
        log("run of %d but context only %d, skipping" % (run, ctx))
        return 0
    if in_cooldown():
        log("run of %d but within cooldown, skipping" % run)
        return 0
    if subprocess.run(["tmux", "has-session", "-t", TMUX_SESSION],
                      capture_output=True).returncode != 0:
        log("run of %d but tmux session missing" % run)
        return 0

    subprocess.run(["tmux", "send-keys", "-t", TMUX_SESSION, "/compact", "Enter"],
                   capture_output=True)
    open(STATE, "w").write(datetime.now(timezone.utc).isoformat(timespec="seconds"))
    log("AUTO-COMPACT sent: run=%d, context=%d, sample=%r, transcript=%s"
        % (run, ctx, sample, os.path.basename(path)))
    notify("[bot] auto-/compact: %d short turns in a row, context %dK. "
           "Self-imitation chain compacted away." % (run, ctx // 1000))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # never let the guard break the watchdog
        log("guard crashed: %s" % exc)
        sys.exit(0)
