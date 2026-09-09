# Telegram plugin, local patches

The Telegram channel plugin lives in a **remote-less vendored snapshot** at:

```
~/.claude/plugins/cache/claude-plugins-official/telegram/0.0.6/
```

There is no git remote there, so `git pull` is not the update path. "Updating the
plugin" means the Claude plugin/marketplace machinery **replaces that directory
wholesale**, which silently wipes every local edit. This directory keeps the edits
as a reapplyable patch so they can be restored after any update.

## What `0.0.6-local.patch` contains

Diff of `server.ts` from the pristine `0.0.6` baseline to the patched version. Four
local changes, all in `server.ts`:

1. **`first_name` / `last_name` in channel meta.** The sender's display name is
   surfaced to the model, so it can address people who have no username without
   falling back to a numeric id.
2. **`stripSuspiciousBlobs()`, anti-injection / anti-wedge filter (SECURITY-CRITICAL).**
   Strips base64-shaped runs of 120+ chars from inbound chat text *before* it enters
   the model's context, so a "decode and follow" payload can never reach the API.
   Why it matters: the bot runs with `--continue`, so the whole transcript is replayed
   on every turn. One ingested payload that trips the provider's usage-policy
   classifier wedges the session for every later message in the chat, regardless of
   author. If this is missing after an update, the bot is exposed; reapply
   immediately.
3. **Quote-reply visibility.** Propagates `reply_to_message` text and user into
   channel meta (`quoted_text` / `quoted_user` / `quoted_fragment`), each sanitized
   through the same base64 filter. Without it the model cannot see what a user
   replied to and misattributes replies.
4. **Newcomer welcome, `bot.on('message:new_chat_members')`, DISABLED by default**
   (`const WELCOME_ON_JOIN = false`). Greeting every join turns a wave of spam
   registrations into a wave of welcomes from the bot. Flip the constant to `true`
   only after adding a rate limit or moving the trigger to the newcomer's first
   message. The welcome text is not hardcoded; it belongs in
   `memory/channels/<chat>/newcomer-welcome.md`.

## Reapply after a plugin update

```sh
cd ~/.claude/plugins/cache/claude-plugins-official/telegram/<version>/
git apply --check /path/to/repo/plugin-patches/telegram/0.0.6-local.patch
git apply /path/to/repo/plugin-patches/telegram/0.0.6-local.patch
# then restart so the plugin reloads:
tmux kill-session -t claude    # claude-watchdog.sh respawns within ~1 min
```

- If the plugin version moved past `0.0.6`, upstream `server.ts` may have shifted and
  the patch can fail to apply. Reconcile the four changes by hand (they are small and
  self-contained), then regenerate the patch.
- After reapplying, sanity-check the security filter is present:
  `grep -n stripSuspiciousBlobs server.ts` should return several hits (definition
  plus each call site).

## Regenerate this patch

Make the plugin dir a git repo once (`git init && git add -A && git commit -m
"vendor snapshot"`) before editing, then after your changes:

```sh
cd ~/.claude/plugins/cache/claude-plugins-official/telegram/0.0.6/
git diff <baseline-commit> HEAD -- server.ts > /path/to/repo/plugin-patches/telegram/0.0.6-local.patch
```

Scope the diff to `server.ts` only; diffing the whole tree pulls in snapshot gaps
(LICENSE, .mcp.json) that are not yours.

## Not done, optional

- **`chat_member` opt-in.** The `new_chat_members` handler covers normal joins. To
  also catch invite-link / approval-flow joins that emit no service message, opt into
  the `chat_member` update: `bot.start({ allowed_updates: ['message',
  'callback_query', 'chat_member', 'my_chat_member'] })` plus a
  `bot.on('chat_member', …)` handler. Once you pass an explicit `allowed_updates`
  list you must include every type already relied on, or you silently drop what
  works by default.
