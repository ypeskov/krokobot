#!/bin/bash
# Watchdog. Keeps the bot's tmux session alive, reaps orphaned plugin processes,
# restarts the session when the Telegram plugin is dead, and runs the per-minute
# guards that keep the transcript healthy.
# Cron: * * * * * (every minute)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/bot-env.sh"

LOG="$BOT_SCRIPT_LOG_DIR/watchdog.log"
DIAG_LOG="$BOT_SCRIPT_LOG_DIR/watchdog-diag.log"
MCP_STATE="$BOT_STATE_DIR/mcp-fail-state"
SESSION="$BOT_TMUX_SESSION"

# 0. Reap orphan bun processes of the Telegram plugin.
# When a claude session is killed via tmux kill-session, its bun children can be
# reparented to init (PPID=1) and busy-loop at 100% CPU: they read EOF from the dead
# stdio pipe without yielding, so SIGTERM is never serviced. Only SIGKILL works.
# Two healthy pollers are normal when two bots share the machine; only orphans go.
for ZOMBIE in $(pgrep -f 'bun.*telegram/0\.0\.[0-9]+' 2>/dev/null); do
    PPID_OF=$(ps -o ppid= -p "$ZOMBIE" 2>/dev/null | tr -d ' ')
    if [ "$PPID_OF" = "1" ]; then
        ETIMES=$(ps -o etimes= -p "$ZOMBIE" 2>/dev/null | tr -d ' ')
        CPU=$(ps -o %cpu= -p "$ZOMBIE" 2>/dev/null | tr -d ' ')
        echo "$(date -u) - SIGKILL orphan bun PID=$ZOMBIE (etimes=${ETIMES}s, %CPU=${CPU})" >> "$LOG"
        kill -9 "$ZOMBIE" 2>/dev/null
    fi
done

# 0b. Guard against the stray 'court'/'count' filler-token degeneration. Self-reinforcing:
# each instance left in the transcript raises the odds of the next. The guard tails the
# live transcript and injects /compact when it crosses the threshold.
python3 "$SCRIPT_DIR/court-guard.py" 2>/dev/null

# 0c. Reconcile the chat log against the transcript. The UserPromptSubmit hook only sees
# messages that arrive as a prompt; anything injected mid-turn bypasses it. The transcript
# has no such blind spot, so this sweeps it every minute and appends whatever is missing.
python3 "$SCRIPT_DIR/chatlog-sweep.py" 2>/dev/null

# 0d. Chat-log health: inbound messages in the last hour but no new log lines means both
# writers are down. A rule with no failure signal decays silently; this is the signal.
python3 "$SCRIPT_DIR/chatlog-health.py" 2>/dev/null

# 0e. Break up a long chain of short, tool-less turns before the model starts imitating
# itself and inventing inbound messages. Same cure as court-guard: compact away the
# examples being copied.
python3 "$SCRIPT_DIR/monotony-guard.py" 2>/dev/null

# 0f. Catch <channel> blocks the model generated itself instead of receiving. The guard
# writes a marker and the UserPromptSubmit nag prints it before the next reply.
python3 "$SCRIPT_DIR/phantom-guard.py" 2>/dev/null

# 1. Ensure the tmux session exists.
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "$(date -u) - $SESSION dead, restarting" >> "$LOG"
    tmux new-session -d -s "$SESSION" "$SCRIPT_DIR/claude-bot.sh"
    echo "$(date -u) - $SESSION created" >> "$LOG"
    rm -f "$MCP_STATE"
    exit 0
fi

# 2. Telegram plugin health via process + API. Identify OUR bun by its
# TELEGRAM_STATE_DIR so a sibling bot's poller is not mistaken for ours.
BUN_PID=""
for p in $(pgrep -f "bun server.ts" 2>/dev/null); do
    ENV_DIR=$(tr '\0' '\n' < "/proc/$p/environ" 2>/dev/null | grep "^TELEGRAM_STATE_DIR=" | cut -d= -f2)
    if [ -z "$ENV_DIR" ] || [ "$ENV_DIR" = "$BOT_TELEGRAM_STATE_DIR" ]; then
        BUN_PID=$p
        break
    fi
done
BUN_ALIVE="no"
[ -n "$BUN_PID" ] && BUN_ALIVE="yes(pid=$BUN_PID)"

API_OK="unknown"
BOT_TOKEN="$(bot_token)" || BOT_TOKEN=""
if [ -n "$BOT_TOKEN" ]; then
    if curl -s --max-time 5 "https://api.telegram.org/bot${BOT_TOKEN}/getMe" | grep -q '"ok":true'; then
        API_OK="yes"
    else
        API_OK="no"
    fi
fi
unset BOT_TOKEN

# Visible MCP failure indicator in the tmux footer.
FOOTER=$(tmux capture-pane -t "$SESSION" -p 2>/dev/null | tail -3)
MCP_FAIL_VISIBLE="no"
if echo "$FOOTER" | grep -qE "[0-9]+ MCP server[s]? failed"; then
    MCP_FAIL_VISIBLE="yes"
fi

{
    echo "$(date -u) bun=$BUN_ALIVE api=$API_OK mcp_fail_visible=$MCP_FAIL_VISIBLE"
    echo "  footer: $(echo "$FOOTER" | tr '\n' '|' | cut -c1-300)"
} > "$DIAG_LOG"

# 3. Decision: bun gone OR MCP failure visible -> accumulate; three strikes -> restart.
PLUGIN_DEAD="no"
if [ "$BUN_ALIVE" = "no" ]; then
    PLUGIN_DEAD="yes"; REASON="bun process gone"
elif [ "$MCP_FAIL_VISIBLE" = "yes" ]; then
    PLUGIN_DEAD="yes"; REASON="MCP fail visible in footer"
fi

if [ "$PLUGIN_DEAD" = "yes" ]; then
    FAIL_COUNT=1
    [ -f "$MCP_STATE" ] && FAIL_COUNT=$(( $(cat "$MCP_STATE") + 1 ))
    echo "$FAIL_COUNT" > "$MCP_STATE"
    echo "$(date -u) - plugin dead ($REASON, $FAIL_COUNT/3)" >> "$LOG"
    if [ "$FAIL_COUNT" -ge 3 ]; then
        echo "$(date -u) - plugin dead for 3+ min, restarting $SESSION" >> "$LOG"
        tmux kill-session -t "$SESSION" 2>/dev/null
        rm -f "$MCP_STATE"
    fi
elif [ -f "$MCP_STATE" ]; then
    echo "$(date -u) - plugin recovered, clearing fail state" >> "$LOG"
    rm -f "$MCP_STATE"
fi
