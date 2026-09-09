#!/bin/bash
# Bot launcher. Runs inside tmux with bypass permissions; started by claude-watchdog.sh.
#
# Portable: the repo root is derived from this script's location, and the Telegram
# plugin is pointed at a project-local state dir via TELEGRAM_STATE_DIR so the bot
# carries its own channel state and token instead of the machine-global
# ~/.claude/channels/telegram. That also lets two bots share one machine.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/bot-env.sh"

export TELEGRAM_STATE_DIR="$BOT_TELEGRAM_STATE_DIR"
cd "$BOT_REPO_ROOT" || exit 1

# --model: pinned explicitly so it beats the model stored in the session jsonl that
#   --continue would otherwise restore (a /model change does not stick across restarts).
# --continue: resume the last session so chat context survives a restart.
# --channels: enable Telegram channel notifications (requires claude.ai login).
exec claude --model "$BOT_MODEL" \
    --permission-mode bypassPermissions --dangerously-skip-permissions \
    --continue \
    --channels plugin:telegram@claude-plugins-official
