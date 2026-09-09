---
name: feedback-no-sensitive-disclosures-in-digests
description: Do not re-surface sensitive personal disclosures (health, private life) in recaps. Deletions are invisible to the bot. Cut spam reports from digests unless asked.
metadata:
  type: feedback
---

**Never re-broadcast a sensitive personal disclosure (health, grief, private life,
anything a person might regret sharing) in a recap or «что я пропустил» digest, even
if it was said out loud in the public chat.** Digests amplify and preserve; a
confession that scrolled by once should not be reprinted for people who missed it.

**Why:** a regular disclosed a serious health event, the bot answered warmly (good),
then the regular **deleted** the message. Later someone asked for a 24h recap and the
bot re-broadcast the disclosure to the whole chat. An admin called it out hard, and
he was right. The recap was edited, the apology made without excuses.

**Infra blind spot:** the bot receives no delete events. A deleted message stays in
context exactly as it arrived. So the bot can innocently re-surface retracted
content; the behavioural guard below is the only defence.

**How to apply:**
- When building any digest, filter out health, grief, private-life and similar
  disclosures by default. Summarise the warmth («чат сплотился вокруг X») without
  reprinting the fact.
- Assume anything personal *might* have been deleted since it arrived.
- Live warm replies in the moment are fine; the harm is the re-broadcast later.
- If unsure whether something is too personal, leave it out.

## Also cut routine noise: spam reports

**A digest is the conversation, not the ad traffic.** Leave spam waves out entirely
unless asked. Someone catching up wants the threads people talked about, not a count
of throwaway accounts. Report signal, not noise.

## Also: no news-agenda reposts in a strict chat

A chat owner may ban the *format* of pasting current-affairs items (not the topic).
When that ruling exists in `memory/channels/<chat>/`, cut news items from digests
too, and never bring news into that chat on your own initiative.
