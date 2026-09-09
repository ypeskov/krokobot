#!/bin/bash
# Kill `claude -p` invocations that have been running longer than any cron job should.
# Headless runs occasionally hang forever (one was found alive after six days, busy-waited
# by a `sleep 5` wrapper). Threshold 30 min: legitimate one-shot jobs finish in under 10.
# Cron: */30 * * * *

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/bot-env.sh"

LOG="$BOT_SCRIPT_LOG_DIR/kill-stuck-claude-p.log"
THRESHOLD_SEC=1800

KILLED=0
for PID in $(pgrep -f '^claude -p' 2>/dev/null); do
    ETIMES=$(ps -p "$PID" -o etimes= 2>/dev/null | tr -d ' ')
    [ -z "$ETIMES" ] && continue
    if [ "$ETIMES" -gt "$THRESHOLD_SEC" ]; then
        CMD=$(ps -p "$PID" -o cmd= 2>/dev/null | cut -c1-200)
        echo "[$(date -u)] killing stuck claude -p PID=$PID etimes=${ETIMES}s cmd=$CMD" >> "$LOG"
        kill "$PID" 2>>"$LOG"
        sleep 5
        if kill -0 "$PID" 2>/dev/null; then
            echo "[$(date -u)]   SIGTERM ignored, escalating to SIGKILL" >> "$LOG"
            kill -9 "$PID" 2>/dev/null
        fi
        # Also kill any busy-wait bash that was sentinel'ing this claude:
        # pattern `bash -c ... until ! ps -p <PID>`.
        for WAITER in $(pgrep -fa "until ! ps -p $PID" 2>/dev/null | awk '{print $1}'); do
            echo "[$(date -u)]   killing busy-wait sentinel PID=$WAITER" >> "$LOG"
            kill -9 "$WAITER" 2>/dev/null
        done
        KILLED=$((KILLED + 1))
    fi
done

[ "$KILLED" -gt 0 ] && echo "[$(date -u)] done, killed $KILLED stuck claude -p process(es)" >> "$LOG"
exit 0
