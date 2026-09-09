---
name: infra-timezone
description: The server runs in UTC; the operator and the chats live in BOT_TZ. Convert before scheduling anything.
metadata:
  type: reference
---

The server runs in **UTC**. `date` returns UTC. The operator and the chat regulars
live in the timezone set as `BOT_TZ` in `bot.env`; chat log stamps and the recall
chronicle use it.

**Why:** an `at 08:00` job intended for 8am local fired at 08:00 UTC, three hours
late. The morning post arrived at 11.

**How to apply:**
- When a person says "tomorrow at 8", convert local → UTC before `at` or cron.
- For `at`: `TZ=<zone> at 08:00`, then verify with `atq`.
- Cron uses the system timezone (UTC). Add the offset, and remember it changes with
  daylight saving.
- Echo both resolved times back before scheduling anything time-sensitive.
