#!/usr/bin/env python3
"""Strip long base64-shaped blobs from log files.

Reads a file (or stdin), replaces any run of >=120 base64/URL-safe chars
with `[base64 blob stripped, N chars]`, prints the cleaned text to stdout.

Usage:
    ./strip_base64_logs.py path/to/file.log
    cat file.log | ./strip_base64_logs.py
"""
import re
import sys

BLOB_RE = re.compile(r'[A-Za-z0-9+/=_\-]{120,}')


def strip_blobs(text: str) -> str:
    def repl(m: re.Match) -> str:
        return f'[base64 blob stripped, {len(m.group(0))} chars]'
    return BLOB_RE.sub(repl, text)


def main() -> int:
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
    else:
        text = sys.stdin.read()
    sys.stdout.write(strip_blobs(text))
    return 0


if __name__ == '__main__':
    sys.exit(main())
