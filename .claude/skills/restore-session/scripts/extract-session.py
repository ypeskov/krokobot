#!/usr/bin/env python3
"""Extract user/assistant messages from the latest Claude session JSONL.

Usage:
  python3 extract-session.py [--last N] [--max-chars M]

  --last N       Only last N messages (default: 200)
  --max-chars M  Max chars per message content (default: 500)

Output: clean text log of the conversation, suitable for context loading.
"""

import json
import glob
import os
import sys
import argparse
import ast

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--last", type=int, default=200)
    parser.add_argument("--max-chars", type=int, default=500)
    parser.add_argument("--file", type=str, default=None, help="Specific JSONL file (path or UUID prefix)")
    args = parser.parse_args()

    scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts")
    sys.path.insert(0, os.path.abspath(scripts_dir))
    import botconfig
    session_dir = botconfig.PROJECT_DIR
    files = glob.glob(os.path.join(session_dir, "*.jsonl"))
    if not files:
        print("No session files found", file=sys.stderr)
        sys.exit(1)

    if args.file:
        # Match by full path or UUID prefix
        matches = [f for f in files if args.file in f]
        if not matches:
            print(f"No session matching '{args.file}'", file=sys.stderr)
            sys.exit(1)
        latest = matches[0]
    else:
        latest = max(files, key=os.path.getmtime)

    messages = []
    with open(latest, "r") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = obj.get("type")
            if msg_type not in ("user", "assistant"):
                continue

            msg = obj.get("message", {})
            if isinstance(msg, str):
                try:
                    msg = ast.literal_eval(msg)
                except:
                    continue

            role = msg.get("role", msg_type)
            content = msg.get("content", "")

            if isinstance(content, list):
                # Extract text blocks only
                texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                content = "\n".join(texts)

            if not content or len(content.strip()) == 0:
                continue

            # Skip meta/system messages
            if obj.get("isMeta"):
                continue

            content = content.strip()[:args.max_chars]
            messages.append(f"[{role}] {content}")

    # Take last N
    messages = messages[-args.last:]

    print(f"# Session history ({len(messages)} messages)")
    print(f"# Source: {os.path.basename(latest)}")
    print()
    for m in messages:
        print(m)
        print()

if __name__ == "__main__":
    main()
