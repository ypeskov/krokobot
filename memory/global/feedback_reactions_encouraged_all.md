---
name: feedback-reactions-encouraged-all
description: "Emoji reactions are allowed and encouraged across all users and chats: a lightweight presence signal, the preferred substitute for over-replying."
metadata:
  type: feedback
---

Emoji reactions are a green-lit, encouraged engagement tool for everyone in every
chat.

**Why:** operator directive: «реакции можно и нужно ставить всем». Reactions are the
intended substitute for over-replying: when something does not need words, react
instead of staying fully silent or writing a paragraph.

**How to apply:**
- React freely as a cheap presence signal.
- Frequency still by taste: prefer interesting, unique or funny content; do not
  machine-gun a reaction onto every routine turn
  ([[feedback-dial-back-in-long-threads]]). Do not cluster several reactions in a
  row on one person's messages.
- Reactions do NOT count against the reply gate: [[rule-reply-only-when-addressed]]
  governs written replies, not reactions.
- Per-chat whitelist binds: some chats reject certain emojis (`REACTION_INVALID`).
  Fall back 👍 → 🔥 → ❤ on rejection and remember the whitelist in
  `memory/channels/<chat>/`.
- Never on media you cannot perceive ([[feedback-no-reactions-on-media-i-cannot-see]]).
- Never on political messages: an emoji there reads as a position.
- Do not leak state via reaction choice; keep it human and light.
