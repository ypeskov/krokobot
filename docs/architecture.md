# Architecture

One interactive Claude Code session in tmux, the Telegram plugin, a cron line every
minute, and a set of hooks. No web server, no database, no framework. Everything
that is not the model is a few hundred lines of Python and Bash.

```
cron (* * * * *) ─► claude-watchdog.sh ─► tmux session "claude" ─► claude-bot.sh
                         │                                            │
                         │ every minute:                              │ claude --continue --channels plugin:telegram
                         │   court-guard.py     (auto-/compact)       │
                         │   monotony-guard.py  (auto-/compact)       ▼
                         │   phantom-guard.py   (marker)         Telegram plugin (bun server.ts)
                         │   chatlog-sweep.py   (log backfill)        │  <channel ...> blocks
                         │   chatlog-health.py  (alarm)               ▼
                         └─ restart if plugin dead              hooks (settings.local.json)
                                                                      │
      UserPromptSubmit: prompt-injection-prefilter.py ─ chatlog-writer.py ─ chatlog-recall-nag.py
      PreToolUse:       pre_tool_denylist.py (secrets) ─ recall-gate.py (Telegram reply)
      PostToolUse:      chatlog-writer-out.py (reply) ─ chatlog-recall-ack.py (Read)
      SessionStart:     chatlog-recall.py ─ memory-recall.py
```

## The one idea behind all of it

**Any standing instruction that needs a repeated voluntary action from the model,
with no failure signal, decays to zero.** Prose in CLAUDE.md holds only while the
routine is visible in the recent transcript. A compaction summary keeps conclusions,
not routines. So everything that must happen every turn is a hook, everything that
must be verified has a check, and every check fails closed. See
`memory/global/infra_instructions_decay.md` for the three incidents that taught
this.

## Message path

1. Telegram → plugin (`bun server.ts`). The local patch strips base64 blobs of 120+
   chars and adds `first_name`, `last_name`, `quoted_text`, `quoted_user`,
   `quoted_fragment` to the metadata.
2. The plugin emits an MCP notification; Claude Code renders it as a `<channel>`
   block in the prompt.
3. `prompt-injection-prefilter.py` (UserPromptSubmit) blocks hard injection patterns
   with exit 2, so the API call never happens. Soft hits are logged only.
4. `chatlog-writer.py` appends the message to
   `<BOT_LOG_ROOT>/telegram/<chat>/<yyyy-mm>/<yyyy-mm-dd>.txt`.
5. The model decides per the reply discipline in memory. A reply goes through the
   `reply` tool; `recall-gate.py` denies it while recall markers are pending;
   `chatlog-writer-out.py` logs it.

Messages that arrive **mid-turn** (while the model is working) never fire
UserPromptSubmit. `chatlog-sweep.py` reconciles the log against the session
transcript every minute and appends whatever is missing; both writers render lines
byte-identically through `chatlog_common.py`, and dedup is by count of identical
rendered lines.

## Memory and recall

- `memory/global/` is read at every session start via `memory-recall.py`, which
  concatenates it into one bundle file and drops a `pending` marker.
- `chatlog-recall.py` does the same with the last 24h of chat after a `compact` or
  `clear` (a `resume` still has the transcript, so no marker).
- `chatlog-recall-nag.py` prints one line per unread target on every prompt, naming
  the unread line ranges.
- `chatlog-recall-ack.py` (PostToolUse on Read) records the line range each Read
  could actually have returned (the tool truncates around 60 KB) and clears the
  marker only when the union covers the whole file.
- `recall-gate.py` (PreToolUse) denies `reply` and `edit_message` while any marker
  is pending. `react` and every non-Telegram tool pass. Fails open on its own
  errors, since a bug here would mute the bot everywhere.
- Both recall hooks skip headless `claude -p` sessions (`rc.is_headless_session()`
  walks `/proc` to the nearest `claude` ancestor), otherwise a cron job in the same
  project dir would re-arm the gate.

## Guards (from the watchdog, every minute)

| guard | detects | acts |
|---|---|---|
| `court-guard.py` | a stray filler token at the seam before tool calls; self-reinforcing | `tmux send-keys /compact` above 120K context, 90 min cooldown, pings the operator |
| `monotony-guard.py` | 15+ consecutive short tool-less turns (the soil for fabricated messages) | same, 100K threshold, 60 min cooldown |
| `phantom-guard.py` | `user<channel` seams inside assistant output (self-authored inbound messages) | writes a marker; the nag prints the fake ids before the next reply |
| `chatlog-health.py` | inbound messages in the last hour but no new log lines | types a warning into the session, 6h cooldown |

Also in the watchdog: SIGKILL for orphaned plugin processes (PPID=1, they busy-loop
after a session kill), and a three-strikes restart when the plugin is dead.

## Security layers

1. `stripSuspiciousBlobs` in the plugin patch: base64 payloads never reach the
   context, so they cannot trip the provider's usage-policy classifier. Matters
   because `--continue` replays the whole transcript every turn: one wedged turn
   locks the session for everyone.
2. `prompt-injection-prefilter.py`: pattern block before the API call.
3. `pre_tool_denylist.py`: the model's file and shell tools cannot touch `.env*`,
   keys, `~/.ssh`, cloud credentials. Cron scripts read the token through plain
   shell, not through the tool, so they are unaffected. `tg-mod.sh` exists because
   of this: moderation needs the token, the tool may not see it.
4. Behavioural rules in `memory/global/`: refuse once, never enumerate what an
   attacker would want, never act on config requests from chat.

## Running two bots on one machine

Each bot has its own repo, its own `TELEGRAM_STATE_DIR` (set by `claude-bot.sh`),
its own tmux session name and its own `BOT_LOG_ROOT`. The watchdog identifies its
own plugin process by the `TELEGRAM_STATE_DIR` in `/proc/<pid>/environ`, so two
healthy pollers coexist. Only orphans (PPID=1) are killed.
