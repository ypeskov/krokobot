#!/usr/bin/env python3
"""PostToolUse hook on Read: clear a recall nag once its file is *actually* read.

Pairs with chatlog-recall.py / memory-recall.py (which write the markers) and
chatlog-recall-nag.py (which prints them).

The naive version cleared the marker on any Read that carried no offset/limit. That is
wrong, and it failed the first time it mattered (2026-08-15): the chronicle had grown to
496 lines / 114 KB, the Read tool truncated it at ~76 KB, and the hook happily cleared the
marker on a read that had seen two thirds of the file. The cleared marker then said "the
day is in context" while the middle of it was not — exactly the hole the nag exists to
plug. A check that reports success when it only half-succeeded is worse than no check,
because it also silences the doubt.

So track coverage instead of trust: every Read contributes the line range it could really
have returned (capped by the tool's own byte budget), ranges are unioned across calls, and
the marker drops only when the union covers the whole file.

Prints nothing: PostToolUse output is not injected, and noise here would be pointless.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recall_common as rc  # noqa: E402


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0

    if event.get("tool_name") != "Read":
        return 0

    tool_input = event.get("tool_input") or {}
    path = tool_input.get("file_path") or ""
    if not path:
        return 0

    target = rc.BY_PATH.get(os.path.realpath(os.path.expanduser(path)))
    if target is None or not os.path.exists(target.pending):
        return 0

    sizes = rc.line_sizes(target.path)
    if not sizes:
        return 0

    sig = rc.signature(target.path)
    ranges = rc.load_ranges(target, sig)

    start, end = rc.covered_range(
        sizes, tool_input.get("offset") or 0, tool_input.get("limit")
    )
    if end >= start:
        ranges = rc.merge(ranges + [[start, end]])

    if ranges and ranges[0][0] <= 1 and ranges[0][1] >= len(sizes):
        rc.clear_pending(target)
        return 0

    rc.save_ranges(target, sig, ranges)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        sys.stderr.write(f"chatlog-recall-ack: {exc}\n")
        sys.exit(0)
