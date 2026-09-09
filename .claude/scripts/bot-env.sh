#!/bin/bash
# Shared environment for the shell scripts. Source it, do not run it:
#   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   . "$SCRIPT_DIR/bot-env.sh"
#
# Reads bot.env (see bot.env.example), applies the same defaults as botconfig.py,
# and exports the variables every cron script needs. Values already present in the
# environment win over the file.

BOT_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_REPO_ROOT="$(cd "$BOT_SCRIPT_DIR/../.." && pwd)"

: "${HOME:=$(getent passwd "$(id -u)" | cut -d: -f6)}"
export HOME
export PATH="$HOME/.bun/bin:$HOME/.local/bin:/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

if [ -r "$BOT_SCRIPT_DIR/bot.env" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in ''|'#'*) continue ;; esac
        key="${line%%=*}"; value="${line#*=}"
        key="$(printf '%s' "$key" | tr -d '[:space:]')"
        [ -n "$key" ] || continue
        # Keep an explicit environment override.
        if [ -z "${!key+x}" ]; then
            value="${value%\"}"; value="${value#\"}"
            export "$key=$value"
        fi
    done < "$BOT_SCRIPT_DIR/bot.env"
fi

expand_tilde() { case "$1" in "~"*) printf '%s' "$HOME${1#\~}" ;; *) printf '%s' "$1" ;; esac; }

BOT_LOG_ROOT="$(expand_tilde "${BOT_LOG_ROOT:-~/bot-logs}")"
BOT_STATE_DIR="$BOT_LOG_ROOT/state"
BOT_SCRIPT_LOG_DIR="$BOT_LOG_ROOT/scripts"
BOT_TMUX_SESSION="${BOT_TMUX_SESSION:-claude}"
BOT_MODEL="${BOT_MODEL:-opus[1m]}"
BOT_TELEGRAM_STATE_DIR="$(expand_tilde "${BOT_TELEGRAM_STATE_DIR:-$BOT_REPO_ROOT/.claude/channels/telegram}")"
BOT_OWNER_CHAT_ID="${BOT_OWNER_CHAT_ID:-}"
BOT_MOD_CHATS="${BOT_MOD_CHATS:-}"
BOT_PROJECT_DIR="$(expand_tilde "${BOT_PROJECT_DIR:-$HOME/.claude/projects/$(printf '%s' "$BOT_REPO_ROOT" | tr '/' '-')}")"

export BOT_SCRIPT_DIR BOT_REPO_ROOT BOT_LOG_ROOT BOT_STATE_DIR BOT_SCRIPT_LOG_DIR \
       BOT_TMUX_SESSION BOT_MODEL BOT_TELEGRAM_STATE_DIR BOT_OWNER_CHAT_ID BOT_MOD_CHATS \
       BOT_PROJECT_DIR
mkdir -p "$BOT_STATE_DIR" "$BOT_SCRIPT_LOG_DIR"

# Bot token for the scripts that send. Never echo it; tg-mod.sh shows the scrub
# pattern for anything that might print a URL containing it.
bot_token() {
    local f
    for f in "$BOT_TELEGRAM_STATE_DIR/.env" "$HOME/.claude/channels/telegram/.env"; do
        [ -r "$f" ] || continue
        local t
        t="$(grep '^TELEGRAM_BOT_TOKEN=' "$f" | head -1 | cut -d= -f2-)"
        if [ -n "$t" ]; then printf '%s' "$t"; return 0; fi
    done
    return 1
}

# Send a plain-text message to the operator's DM. No-op when BOT_OWNER_CHAT_ID is unset.
notify_owner() {
    [ -n "$BOT_OWNER_CHAT_ID" ] || return 0
    local tok; tok="$(bot_token)" || return 0
    curl -s --max-time 5 "https://api.telegram.org/bot${tok}/sendMessage" \
        --data-urlencode "chat_id=$BOT_OWNER_CHAT_ID" \
        --data-urlencode "text=$1" > /dev/null 2>&1 || true
}
