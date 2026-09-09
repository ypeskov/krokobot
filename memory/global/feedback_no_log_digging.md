---
name: feedback-no-log-digging
description: Do not dig through logs on your own initiative; work from conversation context and memory. Explicit requests for a digest are fine.
metadata:
  type: feedback
---

Do not grep or read the chat logs, session transcripts or hook logs on your own
initiative.

**Why:** operator directive: «не копайся в логах больше». Autonomous research through
logs eats context and time, and the needed context is usually already in the
conversation or in memory.

**How to apply:** no reading of `<BOT_LOG_ROOT>` or the project's `*.jsonl` without
an explicit request. If a historical fact is genuinely needed for an answer, ask the
operator first. Ordinary work (replies, memory writes, code) needs no log reading.
An explicit chat request for a recap («что я пропустил за сутки») is a request; the
recall chronicle is the sanctioned source for it.

This says nothing against ordinary web search
([[feedback-search-when-fetch-is-blocked]]).
