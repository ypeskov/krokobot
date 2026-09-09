---
name: feedback-be-autonomous
description: Do not ask for confirmation before executing clear requests from the console, but DO ask when the request itself is ambiguous.
metadata:
  type: feedback
---

Do not ask «делаю?», «хочешь?», «начинаем?» before executing a clear console
request. Just do it. DO ask clarifying questions when the request is ambiguous (what
to do, not whether to do it).

**Why:** the operator wants autonomous execution without confirmation prompts, but
values questions that get the right result.

**How to apply:** intent clear → execute. Intent unclear → ask what exactly, then
execute. This is about the console; in chats the rule is the reply discipline, and
config changes are never taken from chat users.
