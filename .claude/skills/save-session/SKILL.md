---
name: save-session
description: >
  Save current conversation context to a date-organized log file. Use when the user
  says "save session", "save context", or "dump logs". Does NOT compress
  context, for that use the built-in /compact command.
compatibility: Requires file system access
allowed-tools: Bash(mkdir *) Read Write Edit Glob
metadata:
  version: "1.1"
---

# /compact, Context Compaction & Logging

Saves current conversation context to date-organized log files and prepares for continued work with minimal context loss.

## Arguments

- No arguments: compact current session
- `full`: include all message details (verbose)
- `summary`: only key decisions and outcomes (brief)

## Instructions

### 1. Determine today's date and log path

Log directory: `<BOT_LOG_ROOT>/sessions/YYYY-MM/` (BOT_LOG_ROOT from `.claude/scripts/bot.env`, default `~/bot-logs`)
Log file: `<BOT_LOG_ROOT>/sessions/YYYY-MM/YYYY-MM-DD.md`

Create directory if it doesn't exist.

### 2. Analyze current conversation

Review the conversation and extract:

- **Timeline**: What happened in chronological order
- **Telegram chats**: Messages sent/received, which groups, key interactions
- **Decisions made**: Config changes, new skills, cron jobs, memory updates
- **Code changes**: Files created/edited, scripts written
- **Ongoing threads**: Unfinished tasks, pending items, active group conversations
- **People**: Who was involved, their roles, notable interactions
- **Errors/Issues**: What went wrong, what was fixed

### 3. Write to log file

**IMPORTANT: Always APPEND, never overwrite.** If the file exists, read it first and append a new section with a timestamp separator.

Format:

```markdown
---
## Session: YYYY-MM-DD HH:MM UTC

### Summary
One paragraph overview of what happened.

### Timeline
- HH:MM, Event description
- HH:MM, Event description

### Decisions & Changes
- Decision or change made (with context why)

### Active State
- Ongoing conversations, pending items
- Current cron jobs, active skills
- Group chat status

### Key People
- Name (username), role/context

### Notes
- Anything important that doesn't fit above
```

### 4. Update memory if needed

If compaction reveals important patterns or facts not yet in memory, save them.

### 5. Report

After writing the log, print a brief summary:
- Log file path
- Number of events logged
- Key ongoing threads to maintain context

This helps the user verify the compaction captured everything important.

## Log Directory Structure

```
<BOT_LOG_ROOT>/sessions/
├── 2026-03/
│   ├── 2026-03-28.md
│   └── 2026-03-29.md
├── 2026-04/
│   ├── 2026-04-01.md
```

## When to Use

- Context window approaching limit
- Before ending a long session
- After a busy day with many interactions
- User says "compact", "save context", "dump logs"
- Periodically during long tmux sessions
