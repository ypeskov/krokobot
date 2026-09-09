#!/usr/bin/env python3
"""Single place where the Python hooks and guards learn where things are.

Reads `bot.env` next to this file (see `bot.env.example`), applies defaults, and
exposes plain module-level constants. Environment variables already set win over the
file, so a cron line can override one value without editing anything.

Nothing here touches the Telegram token. The token stays in the plugin's state dir
and is read only by the scripts that send (tg_send.py, tg-mod.sh, the guards'
notify()), never surfaced.
"""

from __future__ import annotations

import os
from datetime import timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - python < 3.9
    ZoneInfo = None  # type: ignore[assignment]

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
ENV_FILE = os.path.join(HERE, "bot.env")


def _load_env_file(path: str) -> None:
    """KEY=VALUE lines into os.environ, without overriding what is already set."""
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except FileNotFoundError:
        pass


_load_env_file(ENV_FILE)


def _path(value: str) -> str:
    return os.path.abspath(os.path.expanduser(value))


def _default_project_dir() -> str:
    # Claude Code names the project dir after the cwd with every "/" turned into "-".
    return os.path.join(os.path.expanduser("~/.claude/projects"), REPO_ROOT.replace("/", "-"))


def _parse_chats(spec: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in spec.split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue
        chat_id, name = item.split("=", 1)
        if chat_id.strip() and name.strip():
            out[chat_id.strip()] = name.strip()
    return out


LOG_ROOT = _path(os.environ.get("BOT_LOG_ROOT") or "~/bot-logs")
TELEGRAM_LOG_ROOT = os.path.join(LOG_ROOT, "telegram")
STATE_DIR = os.path.join(LOG_ROOT, "state")
OWNER_CHAT_ID = (os.environ.get("BOT_OWNER_CHAT_ID") or "").strip()
CHAT_DIRS = _parse_chats(os.environ.get("BOT_CHATS") or "")
MOD_CHATS = [c.strip() for c in (os.environ.get("BOT_MOD_CHATS") or "").split(";") if c.strip()]
TMUX_SESSION = (os.environ.get("BOT_TMUX_SESSION") or "claude").strip()
PROJECT_DIR = _path(os.environ.get("BOT_PROJECT_DIR") or _default_project_dir())
TELEGRAM_STATE_DIR = _path(
    os.environ.get("BOT_TELEGRAM_STATE_DIR")
    or os.path.join(REPO_ROOT, ".claude", "channels", "telegram")
)

_tz_name = (os.environ.get("BOT_TZ") or "UTC").strip()
try:
    LOCAL_TZ = ZoneInfo(_tz_name) if ZoneInfo else timezone.utc
except Exception:
    LOCAL_TZ = timezone.utc
LOCAL_TZ_NAME = _tz_name


def chat_dir(chat_id: str) -> str:
    return CHAT_DIRS.get(str(chat_id), f"chat_{chat_id}")


def token_candidates() -> list[str]:
    """Files that may hold TELEGRAM_BOT_TOKEN=, project-local first."""
    return [
        os.path.join(TELEGRAM_STATE_DIR, ".env"),
        os.path.expanduser("~/.claude/channels/telegram/.env"),
    ]


def read_token() -> str | None:
    for path in token_candidates():
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("TELEGRAM_BOT_TOKEN="):
                        tok = line.split("=", 1)[1].strip()
                        if tok:
                            return tok
        except OSError:
            continue
    return None


def notify_owner(text: str) -> None:
    """Best-effort message to the operator's DM. Silent no-op without an owner id."""
    if not OWNER_CHAT_ID:
        return
    token = read_token()
    if not token:
        return
    import subprocess

    subprocess.run(
        [
            "curl", "-s", "--max-time", "5",
            f"https://api.telegram.org/bot{token}/sendMessage",
            "--data-urlencode", f"chat_id={OWNER_CHAT_ID}",
            "--data-urlencode", f"text={text}",
        ],
        capture_output=True,
        timeout=10,
    )


if __name__ == "__main__":
    for name in ("REPO_ROOT", "LOG_ROOT", "STATE_DIR", "PROJECT_DIR", "TELEGRAM_STATE_DIR",
                 "OWNER_CHAT_ID", "TMUX_SESSION", "LOCAL_TZ_NAME"):
        print(f"{name}={globals()[name]}")
    print(f"CHAT_DIRS={CHAT_DIRS}")
    print(f"MOD_CHATS={MOD_CHATS}")
