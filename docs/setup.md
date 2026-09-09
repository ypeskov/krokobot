# Setup

## Prerequisites

- A Linux box that stays on (a small VPS is enough). Everything assumes UTC system
  time.
- `tmux`, `python3` (3.9+ for `zoneinfo`), `curl`, `jq`.
- Claude Code CLI, logged in (`claude login`). The bot runs on a subscription, not
  on API keys; a flat monthly fee is what makes an always-on chat member affordable.
- `bun` (the Telegram plugin runs on it).
- A Telegram bot token from @BotFather. Add the bot to your groups; grant admin
  rights only in chats where you want it to moderate.

## Install

```sh
git clone <this repo> ~/krokobot
cd ~/krokobot

# 1. Configuration
cp .claude/scripts/bot.env.example .claude/scripts/bot.env
$EDITOR .claude/scripts/bot.env        # chat ids, owner id, timezone, log root

# 2. Telegram plugin
claude                                  # inside: /plugin install telegram@claude-plugins-official
                                        #         /telegram:configure <token>
                                        #         /telegram:access   (allow your groups)
                                        #         /exit
# The plugin keeps its state in ~/.claude/channels/telegram by default. The launcher
# points it at .claude/channels/telegram inside the repo instead (gitignored), so
# move that directory there once:
mkdir -p .claude/channels && mv ~/.claude/channels/telegram .claude/channels/

# 3. Plugin patch (base64 filter, names, quote visibility)
cd ~/.claude/plugins/cache/claude-plugins-official/telegram/0.0.6/
git init -q && git add -A && git commit -qm "vendor snapshot"     # once
git apply --check ~/krokobot/plugin-patches/telegram/0.0.6-local.patch && \
git apply ~/krokobot/plugin-patches/telegram/0.0.6-local.patch
cd ~/krokobot

# 4. Memory
$EDITOR memory/global/persona.md        # name, nicknames
$EDITOR memory/INDEX.md                 # channel table
# One directory per chat under memory/channels/, named exactly as in BOT_CHATS.
# yacht-chat/ (strict) and car-chat/ (free) are worked examples; rename or copy.

# 5. Cron
chmod +x .claude/scripts/*.sh
(crontab -l 2>/dev/null; cat <<EOF
* * * * * $HOME/krokobot/.claude/scripts/claude-watchdog.sh
*/30 * * * * $HOME/krokobot/.claude/scripts/kill-stuck-claude-p.sh
EOF
) | crontab -
```

The watchdog creates the tmux session within a minute. Attach with
`tmux attach -t claude` to watch it; detach with `Ctrl-b d`.

## Finding chat ids

Group ids are negative and start with `-100`. The quickest way: open the group in
Telegram Web, the URL contains the number; prepend `-100`. Or read the `chat_id`
attribute of the first `<channel>` block that arrives in the session.

The plugin gates inbound messages by numeric chat id and can send by username, so
`access.json` may need both forms for a public group with a username.

## Verify

```sh
tmux ls                                                # session "claude" exists
tail -5 ~/bot-logs/scripts/watchdog.log                # no restart loop
cat ~/bot-logs/scripts/watchdog-diag.log               # bun=yes api=yes
python3 .claude/scripts/botconfig.py                   # paths resolve as intended
python3 .claude/scripts/pre_tool_denylist.py --self-test
.claude/scripts/tg-mod.sh whoami                       # rights in the mod chat
```

Send the bot a DM. The reply should appear, and a line should land in
`~/bot-logs/telegram/dm-owner/<yyyy-mm>/<yyyy-mm-dd>.txt`.

## Operating

- **Console:** `tmux attach -t claude`. What you type there is the only source of
  configuration changes; the bot treats your Telegram account as a normal user for
  config purposes.
- **Compact:** the guards send `/compact` when the transcript degrades; you can also
  type it. After a compact the bot must re-read the chronicle and the memory bundle
  before it may reply; the gate enforces it.
- **Plugin update:** the marketplace replaces the plugin directory wholesale.
  Reapply the patch (`plugin-patches/telegram/README.md`) or quote visibility and
  the base64 filter silently disappear.
- **Wedged session** (usage-policy error on every turn): rename the active jsonl
  under `~/.claude/projects/<repo-path-with-dashes>/` to `<uuid>.jsonl.aup-stuck-backup-<date>`,
  then `tmux kill-session -t claude`. The watchdog restarts it.
- **Never load the Telegram plugin in a cron `claude -p`.** A second `getUpdates`
  poller on the same token knocks the main bot offline. Cron jobs that need to send
  use `lib/tg_send.py` or `curl`.
- **Never write under `.claude/` from a headless run.** The harness treats it as a
  sensitive path and denies the Write without a human to approve. Keep outputs under
  `BOT_LOG_ROOT`.

## What is not in this repo

- The token, `access.json`, approved pairings, inbox: `.claude/channels/` is
  gitignored.
- `bot.env`: gitignored.
- `memory/users/*.md`: gitignored, they describe real people.
- Anything scheduled beyond the watchdog: digests, reminders, weather posts. The
  pattern is `claude -p "<prompt>" --allowedTools ... > file && python3 lib/tg_send.py file <chat_id>`
  from cron; add your own.
