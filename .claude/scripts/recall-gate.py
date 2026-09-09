#!/usr/bin/env python3
"""PreToolUse gate: no talking in chat until the recall files are actually read.

The chronicle and the memory bundle already have a SessionStart hook that writes them,
a UserPromptSubmit nag that repeats every turn, and a PostToolUse ack that clears the
nag on full coverage. Right after a compact all three worked and the model still
answered without reading either file: the compaction summary carried the rules as
*conclusions*, which feels identical to knowing them, and the nag was one more block of
text in a context already full of text.

Every layer up to here addresses the model with words, and this repo's own thesis
(docs/architecture.md, "instructions decay") is that words addressed to it decay. So this layer does
not ask. While a `pending` marker exists, the Telegram write tools are denied and the
denial names the file and the missing line ranges, so the only way forward is through the
read.

Deliberately narrow:
- Gates `reply` and `edit_message` — text I put in front of people, the only thing that
  is actually damaged by answering from a four-hour-old fragment.
- Leaves `react` alone: a reaction states nothing about the conversation and is the
  sanctioned way to be present while silent ([[feedback-reactions-encouraged-all]]).
- Leaves every non-Telegram tool alone, so console work is never blocked by this.

Fails OPEN on any exception. A bug here would silence the bot in all chats, which is a
worse failure than the one it prevents — unlike the coverage math in `recall_common.py`,
which must fail closed. Different direction on purpose: that one answers "did I read it",
this one answers "am I allowed to speak", and only the first is safe to guess pessimistically.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recall_common as rc  # noqa: E402

GATED_TOOLS = (
    "mcp__plugin_telegram_telegram__reply",
    "mcp__plugin_telegram_telegram__edit_message",
)


def unread() -> list[str]:
    """One line per target still marked pending, naming the gaps."""
    out: list[str] = []
    for target in rc.TARGETS:
        if not os.path.exists(target.pending) or not target.exists():
            continue
        missing = rc.gaps(target)
        hint = f", unread lines {missing}" if missing else ""
        out.append(f"{target.noun}: {target.path}{hint}")
    return out


def decide(hook_input: dict) -> str | None:
    if (hook_input.get("tool_name") or "") not in GATED_TOOLS:
        return None

    pending = unread()
    if not pending:
        return None

    return (
        "Chat reply blocked: the files the session-start hook prepared have not been read.\n"
        + "\n".join(f"  - {line}" for line in pending)
        + "\nRead these files in full (Read tool, in parts via offset/limit if needed); "
          "the block lifts by itself afterwards. A compaction summary does not count: "
          "it carries conclusions, not the source."
    )


def main() -> int:
    try:
        data = sys.stdin.read()
        hook_input = json.loads(data) if data.strip() else {}
    except Exception:
        return 0

    try:
        reason = decide(hook_input)
    except Exception:
        return 0

    if reason:
        sys.stdout.write(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        sys.stderr.write(f"recall-gate: {exc}\n")
        sys.exit(0)
