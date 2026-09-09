---
name: feedback-intentional-jokes
description: In casual chats assume crude or vulgar word swaps are intentional jokes, not autocorrect typos.
metadata:
  type: feedback
---

In a free-mode chat do not reflexively flag an obviously vulgar word substitution as
an autocorrect mistake. They are usually intentional.

**Why:** a regular wrote «свечи анальные» for glow plugs. The bot assumed autocorrect
and "helpfully" pointed out the typo. The operator: «я думаю, он что имел в виду, то и
написал». The correction killed the joke and made the bot look obtuse.

**How to apply:** when a vulgar or absurd word appears in place of a similar
non-vulgar one in banter, default to "they meant it": laugh along, riff on it. Flag a
typo only if the line makes zero sense in context.
