---
name: restore-session
description: >
  Restore conversation context from the latest saved session JSONL file after
  a reboot or crash. Use on startup, when context was lost, or when the user
  says "restore session", "load context", or "what happened before."
compatibility: Requires python3
allowed-tools: Bash(python3 *) Read
metadata:
  version: "1.1"
---

# /restore-session, Restore Context from Last Session

## Arguments

- No arguments: last 200 messages, 500 chars each (~50K tokens)
- `full`: last 500 messages, 1000 chars each (~150K tokens)
- `brief`: last 50 messages, 300 chars each (~10K tokens)

## Instructions

### 1. Extract messages from last session

```bash
python3 scripts/extract-session.py --last 200 --max-chars 500
```

For `full`: `--last 500 --max-chars 1000`
For `brief`: `--last 50 --max-chars 300`

The script finds the latest `.jsonl` in the Claude Code project dir (`BOT_PROJECT_DIR`, derived from the repo path by `botconfig.py`), extracts user/assistant messages, and prints a clean conversation log.

### 2. Read session logs

```bash
ls -t <BOT_LOG_ROOT>/sessions/????-??/*.md | head -2
```

Read the two most recent log files for structured context (timeline, decisions, people).

### 3. Load chat rules

Read [telegram-chat SKILL.md](../telegram-chat/SKILL.md) and the relevant `memory/channels/<chat>/` files for active chats. (Normally the SessionStart hooks already did the memory and chronicle part; this step is the fallback.)

### 4. Confirm restoration

Summarize what you restored:
- Active chats and their modes
- Recent topics and ongoing threads
- Pending tasks
- Key people

## Gotchas

- The `.jsonl` contains the PREVIOUS session, the one before this clean restart
- Messages are truncated to `--max-chars` to save context. Key details may be cut
- Tool calls and system messages are excluded, only user/assistant content
- If no `.jsonl` found, fall back to session logs only
