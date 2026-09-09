---
name: infra-stale-telegram-pollers
description: Orphaned `bun server.ts` pollers (PPID=1) pile up across restarts and break delivery. Count orphans, not processes: two healthy pollers are normal when two bots share a machine.
metadata:
  type: reference
---

**Symptom:** intermittent «message to react not found» / «message to be replied not
found», occasional wedging, and a freshly patched plugin process not receiving
updates even though the code is loaded.

**Root cause:** several `bun server.ts` processes running at once, all polling the
**same bot token**. Telegram allows exactly one `getUpdates` consumer per token; the
extras get 409 Conflict and fight over it. Whichever stale process wins delivers to a
dead session. The watchdog respawns the Claude session but not these orphan plugin
children, so they linger for days.

**Two pollers can be normal.** Two bots on one machine, each with its own token and
its own `TELEGRAM_STATE_DIR`, run two healthy pollers side by side. The token-theft
theory applies only to orphans. Do not kill a parented poller without checking whose
it is.

**Diagnose, counting orphans:**
```sh
ps -eo pid,ppid,stat,lstart,cmd | grep 'server\.ts' | grep -v grep   # overview
ps -eo pid,ppid,stat,cmd | awk '$2==1 && /server\.ts/'               # the extras
readlink /proc/<client_pid>/cwd                                       # whose bot
tmux ls                                                               # which session
```
PPID=1 = orphan = candidate for removal. PPID = a live `claude` = leave it, check the
parent's cwd first.

**Fix:** kill orphans only. SIGTERM is often ignored; escalate to `kill -9`. The
watchdog does this automatically for bun processes with PPID=1.

**Do not use this as an excuse.** Reordering and duplication are what stale pollers
cause. Invented text is not ([[feedback-never-blame-infra-for-own-fabrication]]).
