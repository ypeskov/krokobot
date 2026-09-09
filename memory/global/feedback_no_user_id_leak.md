---
name: feedback-no-user-id-leak
description: "How to refer to Telegram users in chat output: the name fallback chain, and never a raw user_id."
metadata:
  type: feedback
---

**Fallback chain for naming a participant in chat output**, in priority order:

1. A known chat nickname from memory (how the regulars actually call the person).
2. `first_name + last_name` from the Telegram profile (`first_name` / `last_name`
   attributes on the `<channel>` tag, present with the plugin patch).
3. `username` (the `user="..."` attribute when it is not a number).
4. The first four digits of `user_id` followed by dots (`1234....`) as the last
   resort.

**Forbidden:** a raw, full `user_id` in a chat. Even spam accounts are "a spam
account", not their id. Even the mask is a last resort.

**Why:** an admin pointed out that publishing raw ids is a privacy leak; the
operator added that full anonymisation is also wrong because people cannot follow
who is meant. Hence the chain instead of either extreme.

**In memory yes, in chat no:** per-user memory files carry the full id as the
filename; the on-disk chat log carries it in every line. Both are private. Chat
output follows the chain above.
