#!/usr/bin/env python3
"""UserPromptSubmit hook: append inbound Telegram messages to the on-disk chat log.

Why this exists: CLAUDE.md requires chat history on disk, but the only writer
(tglog.sh) had no trigger — it depended on the model remembering to call it, and
that decayed to zero between 2026-08-03 and 2026-08-12. Behaviour that must happen
every turn belongs in a hook, not in an instruction.

Scope limit, found the hard way on 2026-08-14: this hook only sees messages that
arrive as a *prompt*. Messages injected mid-turn, while I am already working, never
fire UserPromptSubmit and are invisible here. chatlog-sweep.py reconciles the log
against the transcript every minute and catches those. This hook stays because it
makes the common case instant; the two cannot double-write because both render lines
through chatlog_common and the sweeper skips lines already present.

CRITICAL: stdout of a UserPromptSubmit hook is injected into Claude's context.
This script must print NOTHING on stdout, ever. Diagnostics go to stderr.
It must also never fail loudly: any exception exits 0 with no output.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chatlog_common as C  # noqa: E402


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0

    prompt = event.get("prompt") or ""
    if "<channel" not in prompt:
        return 0  # console-typed message, not chat traffic

    for chat_id, when, line in C.parse_channels(prompt):
        C.append(chat_id, when, line)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # never break the turn
        sys.stderr.write(f"chatlog-writer: {exc}\n")
        sys.exit(0)
