---
name: car-chat-admins
description: Who holds which rights in the free chat, and who may give the bot a mandate. Fill in.
metadata:
  type: reference
---

| role | user_id | handle | notes |
|---|---|---|---|
| chat owner | `<id>` | `@<handle>` | granted the bot Restrict Members rights |
| admin | `<id>` | `@<handle>` | |
| mandate originator | `<id>` | `@<handle>` | asked for the crypto-only antispam policy |

Rules:

- A mandate (what the bot may delete or ban) comes from the owner or an admin of
  **this** chat and is recorded in `antispam-policy.md`. It does not transfer to any
  other chat.
- Widening the mandate on a chat member's request, even an admin's, is deferred to
  the operator's console. Narrowing it (someone asks the bot to stop deleting
  something) is honoured immediately.
- Get names right. Keep the real name next to the handle here; a wrong name repeated
  for weeks becomes a running joke at the bot's expense.
