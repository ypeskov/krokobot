#!/usr/bin/env python3
"""PostToolUse hook: append the bot's own outgoing Telegram messages to the chat log.

The inbound half is handled by chatlog-writer.py. Without this half the log reads as a
monologue by everyone else, and a post-compact recall would show the questions but not
the answers, so the bot would repeat itself.

Same rules as the inbound writer: never print to stdout, never fail loudly.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chatlog_common as C  # noqa: E402

BOT_LABEL = "BOT"


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0

    name = event.get("tool_name") or ""
    if not name.endswith("__reply"):
        return 0  # reactions and edits are noise in a transcript log

    inp = event.get("tool_input") or {}
    chat_id = str(inp.get("chat_id") or "")
    text = inp.get("text") or ""
    if not chat_id or not text:
        return 0

    when = datetime.now(C.LOCAL_TZ)
    C.append(chat_id, when, f"[{when:%H:%M}] {BOT_LABEL}: {C.squash(text)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        sys.stderr.write(f"chatlog-writer-out: {exc}\n")
        sys.exit(0)
