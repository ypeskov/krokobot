---
name: infra-instructions-decay
description: Any standing instruction that needs a repeated voluntary action from the model, with no failure signal, decays to zero. Such rules belong in hooks. The design principle behind every guard in this repo.
metadata:
  type: reference
---

**The thesis:** behaviour follows the recent transcript, not the standing
instruction. While a routine is being performed it reproduces itself; a few misses
erase the pattern; compaction does not restore it because a summary carries
conclusions, not routines. If skipping breaks nothing visible, the rule dies
silently.

Three instances, each fixed by moving the rule out of prose and into a mechanism:

1. **Chat logging.** CLAUDE.md said "append every message to the log". The only
   writer was a helper the model had to call by hand. It stopped for nine days and
   nobody noticed. Fix: `chatlog-writer.py` (hook), `chatlog-sweep.py` (transcript
   reconciliation from cron, because mid-turn messages never fire the hook),
   `chatlog-health.py` (the missing failure signal).
2. **Reading memory at session start.** CLAUDE.md said "read all of memory/global/".
   It only looked like it worked because `--continue` carried the rules in the
   transcript. Fix: `memory-recall.py` builds a bundle, `chatlog-recall-nag.py` nags
   every turn, `chatlog-recall-ack.py` clears the nag only when the *union* of read
   ranges covers the whole file, and `recall-gate.py` refuses the Telegram reply
   tool until then. A hook that asks is CLAUDE.md with a higher frequency; the gate
   does not ask.
3. **Degenerate output.** A stray token at the seam before tool calls, then chains
   of near-identical short turns, then invented inbound messages. All self-imitation
   from the transcript. Discipline did nothing; `court-guard.py`,
   `monotony-guard.py` and `phantom-guard.py` detect the shape and send `/compact`,
   which removes the examples being copied.

Corollaries worth keeping:

- **A check must fail closed.** The first acknowledger cleared the marker on any
  Read without offset, but the Read tool truncates large files, so it reported
  "read" on two thirds of the day. Coverage math replaced trust.
- **A calibration measured on one file is not a constant.** The byte cap that
  converts "one Read" into "this many lines" was right for the chronicle and wrong
  for the memory bundle, because the real budget is tokens and Cyrillic costs more
  per byte. Err low.
- **Before installing a lock, see who else can pull its handle.** Cron `claude -p`
  jobs in the same project dir fire the same SessionStart hooks and would re-arm the
  gate four times a day. Both recall hooks now skip headless sessions.
- **The log lags by the length of the current turn.** The transcript is written as
  turns complete, so "not in my record" never means "did not happen" for the last
  few minutes.
