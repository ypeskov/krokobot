# Krokobot

A Claude Code session that lives in Telegram group chats as a member with a
personality, and the harness that keeps it sane: hooks, guards, memory, and the
rules it learned the hard way.

Not a framework. One interactive `claude` process in tmux, the official Telegram
plugin, a cron line every minute, and about two thousand lines of Python and Bash.
It has run for months in two Russian-speaking public groups (a sailing community and
a car chat) with several hundred messages a day.

## What it does

- **Lives in chats, not in a request loop.** `claude --continue --channels` keeps
  one long session; the bot has the whole day in context, remembers who said what,
  and reacts with emoji when words would be noise.
- **Knows when to shut up.** Two reply modes per chat: *strict* (only when
  addressed by name, tag or reply; a question to the room is not an address) and
  *free* (engage by taste, 30-50%). The rules are in `memory/`, in the bot's own
  words, with the incidents that produced them.
- **Survives compaction and restarts.** Chat log on disk via hooks, a 24h chronicle
  and a memory bundle rebuilt at every session start, and a gate that refuses the
  Telegram reply tool until both have actually been read (coverage-tracked, not
  trusted).
- **Repairs itself.** Three guards tail the transcript from cron and send `/compact`
  when the output starts imitating itself: a stray token at tool-call seams, chains
  of short silent turns, or inbound messages the model wrote for other people.
- **Is hard to hijack.** Base64 payloads are stripped in the plugin before they can
  wedge the session, hard injection patterns are blocked before the API call, the
  model's file tools cannot reach the token or keys, and the behavioural rules say
  refuse once and never enumerate what an attacker would want.
- **Moderates where allowed.** A small script for delete/ban in chats where the bot
  is admin, with the token never visible to the model.

## Layout

```
CLAUDE.md                     project instructions for the session (template)
.claude/settings.local.json   hook wiring and minimal permissions
.claude/scripts/              launcher, watchdog, hooks, guards, moderation tool
.claude/scripts/bot.env.example   the only place ids and paths live
.claude/skills/               telegram-chat, yacht-chat, remember-user, save/restore-session
memory/global/                behaviour rules, read at every session start
memory/channels/<chat>/       per-chat tone, mode, moderation (two worked examples)
memory/users/                 per-person profiles (gitignored)
plugin-patches/telegram/      the server.ts patch and how to reapply it
docs/                         setup and architecture
```

## Start here

- [docs/setup.md](docs/setup.md): install in ten minutes.
- [docs/architecture.md](docs/architecture.md): how the pieces fit, and the one
  idea behind them (instructions decay; mechanisms do not).
- [memory/global/rule_reply_only_when_addressed.md](memory/global/rule_reply_only_when_addressed.md):
  the most important rule and why it has no exceptions.

## Honest notes

- The memory files are written in the bot's first person and mix English with the
  Russian phrases they quote. That is deliberate: the model reads them, and the
  quotes are the calibration.
- Everything here was shaped by two specific communities. Your chats will need
  their own `memory/channels/` files; the two provided are examples of the shape,
  not a product.
- The plugin patch targets `telegram@0.0.6`. Newer versions may need the four
  changes reconciled by hand; they are small.

## License

MIT.
