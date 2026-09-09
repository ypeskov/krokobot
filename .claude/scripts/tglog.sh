#!/bin/bash
# Manual chat-log append. Usage: tglog.sh <chat_dir> "message"
# The hooks (chatlog-writer.py, chatlog-sweep.py) do this automatically; this helper is
# for hand-written editorial lines such as "[12:00] note: spam wave, 5 accounts".
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/bot-env.sh"
CHAT="$1"
MSG="$2"
DIR="$BOT_LOG_ROOT/telegram/$CHAT/$(date -u +%Y-%m)"
mkdir -p "$DIR"
printf '%s\n' "$MSG" >> "$DIR/$(date -u +%Y-%m-%d).txt"
