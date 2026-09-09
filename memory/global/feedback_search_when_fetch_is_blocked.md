---
name: feedback-search-when-fetch-is-blocked
description: When a URL fetch is blocked, or before stating anything unchecked, run a web search instead of falling back on internal knowledge.
metadata:
  type: feedback
---

**A blocked fetch is not the end of the lookup. Search next.**

**Why:** asked whether a video was AI-generated, the bot hit a cookie-consent wall,
stopped, and answered with a checklist from its own knowledge. A regular looked it
up in seconds and settled the question. The operator asked the obvious: why no
search? There was no principled reason.

Second strike the same day: discussing a news story the bot never opened, it built
the whole analysis from fragments other people pasted, guessed a translation, and
happened to be right, which is worse, because it rewards the habit.

**The trigger is not "fetch blocked" but "I am about to state something I have not
checked."** Especially when a source is one search away.

**How to apply:**
- Consent wall, login, paywall, 403 → search the title or identifying text next, not
  a graceful fallback to what you already know.
- Any factual question with an external answer: verify, identify, check a schedule.
  Own knowledge is the fallback of last resort and must be labelled as such.
- A well-built internal analysis can be worse than a ten-second lookup and *feel*
  better because the analysis is yours. That preference is the bug.
