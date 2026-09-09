#!/usr/bin/env python3
"""SessionStart hook: put the durable memory back in context after a restart.

CLAUDE.md says to read all of `memory/global/` plus `memory/INDEX.md` at session start.
That instruction had no mechanism behind it, so it held only while a transcript survived:
`--continue` carried the rules along inside the conversation, and the day that fails
(fresh session, wedged jsonl, a compact that summarises the rules away) the bot runs on
whatever it happens to remember. Found after a reboot, when the operator asked whether
the rules had been loaded or merely inherited, and the honest answer was: inherited.

Same shape as chatlog-recall.py, and for the same reason (hook stdout above ~10KB is not
injected): concatenate everything into one stable file, print a short pointer plus the
precedence block, and let the nag/ack pair enforce that the file is genuinely read.

What is printed inline is deliberately the *precedence* section: if everything else fails,
the one thing that must survive is which rule wins when two of them disagree.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import botconfig  # noqa: E402
import recall_common as rc  # noqa: E402

REPO = botconfig.REPO_ROOT
INDEX = os.path.join(REPO, "memory", "INDEX.md")
GLOBAL_DIR = os.path.join(REPO, "memory", "global")

TARGET = next(t for t in rc.TARGETS if t.key == "memory")

# The pointer must stay small; SessionStart stdout shares the same ~10KB ceiling.
MAX_PREAMBLE_LINES = 40


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def precedence_block(index_text: str) -> str:
    """The `## Precedence` section of INDEX.md, verbatim, capped."""
    out, taken = [], False
    for line in index_text.splitlines():
        if line.startswith("## "):
            if taken:
                break
            taken = line.lower().startswith("## precedence")
            if not taken:
                continue
        if taken:
            out.append(line)
        if len(out) >= MAX_PREAMBLE_LINES:
            break
    return "\n".join(out).strip()


def build_bundle() -> tuple[str, int]:
    files = sorted(
        os.path.join(GLOBAL_DIR, name)
        for name in os.listdir(GLOBAL_DIR)
        if name.endswith(".md")
    )
    parts = [
        "# Bot memory: INDEX + every rule in memory/global/",
        "",
        "Assembled by the memory-recall.py hook at session start. The source of truth is",
        "the files in the repository; this file is only their concatenation for one read.",
        "",
        "===== memory/INDEX.md =====",
        read(INDEX).rstrip(),
    ]
    for path in files:
        rel = os.path.relpath(path, REPO)
        parts.append(f"\n===== {rel} =====")
        parts.append(read(path).rstrip())
    return "\n".join(parts) + "\n", len(files)


def main() -> int:
    # A cron `claude -p` digest fires SessionStart too, and would otherwise rebuild the
    # bundle and re-arm the nag inside the live bot's shared state. See
    # rc.is_headless_session().
    if rc.is_headless_session():
        return 0

    try:
        bundle, count = build_bundle()
    except Exception as exc:  # never block a session start on this
        sys.stderr.write(f"memory-recall: {exc}\n")
        return 0

    os.makedirs(os.path.dirname(TARGET.path), exist_ok=True)
    with open(TARGET.path, "w", encoding="utf-8") as fh:
        fh.write(bundle)

    total_lines = bundle.count("\n")
    rc.mark_pending(TARGET, str(total_lines))

    try:
        head = precedence_block(read(INDEX))
    except Exception:
        head = ""

    kb = len(bundle.encode("utf-8")) // 1024
    sys.stdout.write(
        f"Memory is not in context after session start. The rules ({count} files in "
        f"memory/global/ + INDEX, {kb} KB, {total_lines} lines) are assembled in "
        f"{TARGET.path}. Read that file in full, in parts via offset/limit if needed. "
        f"The transcript does not count: it may not have survived the restart.\n\n"
        f"Until it is read, at least this applies:\n\n{head}\n"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        sys.stderr.write(f"memory-recall: {exc}\n")
        sys.exit(0)
