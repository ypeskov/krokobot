#!/usr/bin/env python3
"""Send a text file to one or more Telegram chats via the Bot API sendMessage.

Plain text (no parse_mode — robust; avoids MarkdownV2 escaping failures). Splits at
<=4000 chars on line boundaries. Reads the bot token from the project-local telegram
state dir first, then the global one (see botconfig.token_candidates).

Deliberately does NOT use the Telegram MCP plugin: loading that plugin in a cron
`claude -p` starts a second getUpdates poller and knocks the main bot offline.

Usage:
    tg_send.py <textfile> <chat_id> [<chat_id> ...]
Exit 0 if every send returned HTTP 200, else 1.
"""
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import botconfig  # noqa: E402

MAX = 4000  # Telegram hard cap is 4096; leave headroom


def find_token() -> str | None:
    return botconfig.read_token()


def chunks(text: str, n: int = MAX):
    out, cur = [], ""
    for line in text.split("\n"):
        while len(line) > n:  # a single line longer than the cap
            if cur:
                out.append(cur)
                cur = ""
            out.append(line[:n])
            line = line[n:]
        if not cur:
            cur = line
        elif len(cur) + 1 + len(line) <= n:
            cur = cur + "\n" + line
        else:
            out.append(cur)
            cur = line
    if cur:
        out.append(cur)
    return out or [""]


def send(token: str, chat_id: str, text: str) -> int:
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=data
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"tg_send: HTTP {e.code} for chat {chat_id}: {e.read()[:200]!r}\n")
        return e.code
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"tg_send: error for chat {chat_id}: {e}\n")
        return 0


def main() -> int:
    if len(sys.argv) < 3:
        sys.stderr.write("usage: tg_send.py <textfile> <chat_id> [<chat_id> ...]\n")
        return 2
    path, chat_ids = sys.argv[1], sys.argv[2:]
    token = find_token()
    if not token:
        sys.stderr.write("tg_send: no bot token found\n")
        return 1
    with open(path, encoding="utf-8") as fh:
        text = fh.read().strip()
    if not text:
        sys.stderr.write("tg_send: empty text, nothing to send\n")
        return 1
    ok = True
    for cid in chat_ids:
        for part in chunks(text):
            code = send(token, cid, part)
            print(f"sent chat={cid} http={code} len={len(part)}")
            ok = ok and code == 200
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
