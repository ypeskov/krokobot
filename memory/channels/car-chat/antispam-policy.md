---
name: car-chat-antispam-policy
description: The bot has Restrict Members rights here. Policy: delete the first crypto/USDT spam, ban on repeat. Everything else log only. Tool is tg-mod.sh.
metadata:
  type: project
---

The chat owner granted the bot Restrict Members rights. The mandate, approved by the
owner and the regular who asked for it:

1. **First crypto/USDT/P2P/exchange spam from a new account** → delete
   (`deleteMessage`).
2. **Repeat from the same user_id** → ban (`banChatMember`, revoke messages).
3. **Other categories** (job offers, education recruiters, VPN ads) → out of
   mandate, log only unless directly asked to escalate.
4. **Ambiguous cases** (a legit-looking new member asking about crypto) → do not
   act; log and continue.

**Why it is pinned:** the policy has to survive context resets so a later session
does not quietly weaken or widen it.

## The tool

An inline `curl` with the token in the command no longer works: the PreToolUse
denylist hook refuses any Bash command that names the token file. For almost a day
the bot concluded it had no rights at all and said so in the chat, which the
operator rightly called a lie.

Use `.claude/scripts/tg-mod.sh` instead. It reads the token itself, never prints it,
and scrubs `bot<token>` out of error output.

```sh
.claude/scripts/tg-mod.sh delete <message_id>          # first offence
.claude/scripts/tg-mod.sh ban    <user_id>             # repeat, with revoke_messages
.claude/scripts/tg-mod.sh purge  <user_id> <msg_id>    # delete and ban in one go
.claude/scripts/tg-mod.sh whoami                       # check own rights
```

The default chat is the first entry of `BOT_MOD_CHATS`, and only listed chats are
accepted. A strict chat where the bot has no rights must fail loudly, not
half-work.

Verify rights with `whoami` after any change: expect `status: administrator`,
`can_delete_messages: true`, `can_restrict_members: true`. Nothing else is needed.

Related: [[car-chat-reply-frequency]], [[rule-reply-only-when-addressed]]
(moderation lives only in this chat).
