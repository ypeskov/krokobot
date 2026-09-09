#!/usr/bin/env python3
"""Shared machinery for the "big file that must actually be read" hooks.

Two things now have to be in context at the start of every session and neither fits in
a hook's ~10KB stdout budget:

* the 24h chat chronicle (~60KB) — built by chatlog-recall.py
* the memory bundle: INDEX + everything in memory/global/ (~130KB) — built by
  memory-recall.py

Both use the same three-part shape, which was arrived at the hard way (see
`memory/global/infra_chat_log_writer_dead.md`): a SessionStart hook writes the full
text to a stable path and prints only a pointer, a UserPromptSubmit nag repeats until
the file is read, and a PostToolUse hook on Read clears the nag — but only once the
*union* of read ranges covers the whole file, because the Read tool truncates around
76KB and a marker cleared on a truncated read is worse than no marker at all.

This module holds the target registry and the coverage math so the nag and the ack
cannot drift apart from each other, or from a third target added later.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import botconfig  # noqa: E402

# Calibration. The tool's real limit is a *token* budget (~25k), not bytes, and Cyrillic
# costs far more tokens per byte than ASCII — so any byte figure is an approximation and
# must be the pessimistic one.
#
# Measured twice on real files:
#   2026-08-15, chat chronicle:  cut after 76307 bytes  -> 74000 looked safe
#   2026-08-22, memory bundle:   cut after 65109 bytes  <- 74000 over-credited 117 lines
#
# The second measurement is the binding one and it was caught the first time the memory
# bundle was read for real: the ack marked 1-929 read when the tool had returned 1-812.
# That is exactly the failure this file exists to prevent, so the cap now sits below the
# worst case seen. Erring low costs one extra paginated read; erring high silently marks
# unread lines as read.
BYTE_CAP = 60_000


@dataclass(frozen=True)
class Target:
    key: str
    path: str
    pending: str
    coverage: str
    noun: str  # what the nag calls it
    why: str   # one clause on what goes wrong if it stays unread

    def exists(self) -> bool:
        return os.path.exists(self.path)


def _p(*parts: str) -> str:
    return os.path.join(botconfig.LOG_ROOT, *parts)


TARGETS: tuple[Target, ...] = (
    Target(
        key="chatlog",
        path=_p("telegram", "_recall", "latest.txt"),
        pending=_p("telegram", "_recall", "pending"),
        coverage=_p("telegram", "_recall", "coverage.json"),
        noun="chat chronicle",
        why="otherwise you answer from a fragment of the last few minutes",
    ),
    Target(
        key="memory",
        path=_p("_memory", "global-bundle.md"),
        pending=_p("_memory", "pending"),
        coverage=_p("_memory", "coverage.json"),
        noun="memory (INDEX + memory/global)",
        why="otherwise the rules are known only from the transcript, and after a clean start not at all",
    ),
)

BY_PATH = {os.path.realpath(t.path): t for t in TARGETS}


def is_headless_session() -> bool:
    """True when this hook runs inside a one-shot `claude -p` (cron digest), not the bot.

    Any cron job that launches `claude -p …` in this same project directory fires the
    SessionStart hooks too. Those runs would rebuild the bundles and re-drop the `pending`
    markers **in the live bot's shared files**, resetting its recall state mid-conversation.

    Harmless as a nag, not harmless once `recall-gate.py` is live: a cron job would lock
    the bot out of every chat until it re-read ~150 KB it had already read. A guard whose
    trigger is somebody else's cron is not a guard.

    Detection walks the process tree to the nearest `claude` ancestor and looks for `-p` /
    `--print`. Any failure returns False (treat as interactive), because the cost of a
    false positive — a real session start that silently skips recall — is the exact bug
    this whole mechanism exists to prevent.
    """
    return _walk_to_claude(os.getppid(), _proc_argv, _proc_ppid)


def _proc_argv(pid: int) -> list[str]:
    with open(f"/proc/{pid}/cmdline", "rb") as fh:
        return [a.decode("utf-8", "ignore") for a in fh.read().split(b"\x00") if a]


def _proc_ppid(pid: int) -> int:
    with open(f"/proc/{pid}/stat", "rb") as fh:
        # ppid is field 4, but comm (field 2) may itself contain spaces and parens
        return int(fh.read().rsplit(b")", 1)[1].split()[1])


def _walk_to_claude(pid: int, argv_of, ppid_of, max_depth: int = 12) -> bool:
    """Shared with the self-test; injectable lookups so it can run without /proc."""
    try:
        for _ in range(max_depth):
            if pid <= 1:
                return False
            argv = argv_of(pid)
            if argv and os.path.basename(argv[0]) == "claude":
                return any(a in ("-p", "--print") for a in argv[1:])
            pid = ppid_of(pid)
    except Exception:
        return False
    return False


def line_sizes(path: str) -> list[int]:
    with open(path, "rb") as fh:
        return [len(line) for line in fh]


def covered_range(sizes: list[int], offset: int, limit: int | None) -> tuple[int, int]:
    """Line range (1-based, inclusive) a Read with these arguments could have returned."""
    start = max(1, offset or 1)
    if start > len(sizes):
        return (0, -1)
    last = start + limit - 1 if limit else len(sizes)
    last = min(last, len(sizes))

    spent = 0
    end = start - 1
    for idx in range(start, last + 1):
        spent += sizes[idx - 1]
        if spent > BYTE_CAP:
            break
        end = idx
    return (start, end)


def merge(ranges: list[list[int]]) -> list[list[int]]:
    out: list[list[int]] = []
    for start, end in sorted(ranges):
        if out and start <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out


def signature(path: str) -> str:
    stat = os.stat(path)
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def load_ranges(target: Target, sig: str) -> list[list[int]]:
    """Ranges recorded for this exact file version; a rebuilt file invalidates them."""
    try:
        with open(target.coverage, encoding="utf-8") as fh:
            state = json.load(fh) or {}
    except Exception:
        return []
    if state.get("sig") != sig:
        return []
    return [[int(a), int(b)] for a, b in state.get("ranges", [])]


def save_ranges(target: Target, sig: str, ranges: list[list[int]]) -> None:
    os.makedirs(os.path.dirname(target.coverage), exist_ok=True)
    with open(target.coverage, "w", encoding="utf-8") as fh:
        json.dump({"sig": sig, "ranges": ranges}, fh)


def gaps(target: Target) -> str:
    """Unread line ranges, so the next Read can aim instead of repeating blindly.

    Signature-checked: a regenerated file (chatlog-recall.py rewrites the chronicle on
    every session start without touching coverage.json) must not inherit the previous
    version's read ranges, or the nag would report lines as read that nobody has seen.
    """
    try:
        total = len(line_sizes(target.path))
        ranges = load_ranges(target, signature(target.path))
    except Exception:
        return ""

    missing, cursor = [], 1
    for start, end in ranges:
        if start > cursor:
            missing.append(f"{cursor}-{start - 1}")
        cursor = max(cursor, end + 1)
    if cursor <= total:
        missing.append(f"{cursor}-{total}")
    return ", ".join(missing)


def mark_pending(target: Target, note: str) -> None:
    os.makedirs(os.path.dirname(target.pending), exist_ok=True)
    with open(target.pending, "w", encoding="utf-8") as fh:
        fh.write(note)
    for stale in (target.coverage,):
        try:
            os.remove(stale)
        except FileNotFoundError:
            pass


def clear_pending(target: Target) -> None:
    for stale in (target.pending, target.coverage):
        try:
            os.remove(stale)
        except FileNotFoundError:
            pass
