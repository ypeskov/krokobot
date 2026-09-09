#!/usr/bin/env python3
"""Shared formatting for the chat-log writers.

Two things append to the chat log: the UserPromptSubmit hook (instant, but only sees
messages that arrive as prompts) and the transcript sweeper (up to a minute late, but
sees everything). They MUST format a given message identically down to the byte, because
the sweeper deduplicates by comparing rendered lines against what is already on disk.
Any divergence here turns into duplicated log lines, so the formatting lives in one
place and neither script is allowed a private copy.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import botconfig  # noqa: E402

LOCAL_TZ = botconfig.LOCAL_TZ
LOG_ROOT = botconfig.TELEGRAM_LOG_ROOT
MAX_TEXT = 400

CHANNEL_RE = re.compile(r"<channel\s+([^>]*)>(.*?)</channel>", re.DOTALL)
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


def chat_dir(chat_id: str) -> str:
    return botconfig.chat_dir(chat_id)


def squash(text: str) -> str:
    """One log line per message: collapse newlines, trim, cap length."""
    text = " / ".join(part.strip() for part in text.splitlines() if part.strip())
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT].rstrip() + " […]"
    return text


def attachment_note(attrs: dict) -> str:
    if attrs.get("image_path"):
        return "[photo]"
    kind = attrs.get("attachment_kind")
    if kind:
        name = attrs.get("attachment_name", "")
        return f"[{kind}{': ' + name if name else ''}]"
    return ""


def when_of(attrs: dict) -> datetime:
    """Telegram's own timestamp when present, arrival time otherwise."""
    ts = attrs.get("ts")
    if ts:
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(LOCAL_TZ)
        except Exception:
            pass
    return datetime.now(LOCAL_TZ)


def speaker(attrs: dict) -> str:
    """Accounts without a username arrive with user= set to the numeric id, which would
    log as "1234567890 (1234567890)". Fall back to the display name so a human reading
    the log later sees who it was. Common with throwaway spam accounts, which is exactly
    where the log has to stay readable."""
    uid = attrs.get("user_id", "")
    who = attrs.get("user") or ""
    if not who or who == uid:
        who = " ".join(filter(None, [attrs.get("first_name"), attrs.get("last_name")])) or uid
    return f"{who} ({uid})" if uid else who


def render(attrs: dict, body: str) -> str:
    text = squash(body)
    note = attachment_note(attrs)
    if note:
        text = f"{note} {text}".strip()
    return f"[{when_of(attrs):%H:%M}] {speaker(attrs)}: {text}"


def parse_channels(prompt: str) -> list[tuple[str, datetime, str]]:
    """Every <channel> block in a chunk of text as (chat_id, when, rendered line)."""
    out: list[tuple[str, datetime, str]] = []
    for raw_attrs, body in CHANNEL_RE.findall(prompt):
        attrs = dict(ATTR_RE.findall(raw_attrs))
        chat_id = attrs.get("chat_id")
        if not chat_id:
            continue
        out.append((chat_id, when_of(attrs), render(attrs, body)))
    return out


def day_path(chat_id: str, when: datetime) -> str:
    d = os.path.join(LOG_ROOT, chat_dir(chat_id), when.strftime("%Y-%m"))
    return os.path.join(d, when.strftime("%Y-%m-%d") + ".txt")


def append(chat_id: str, when: datetime, line: str) -> None:
    path = day_path(chat_id, when)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
