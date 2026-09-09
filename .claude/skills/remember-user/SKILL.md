---
name: remember-user
description: >
  Persist a durable fact about a chat participant to that person's profile in
  project memory (`memory/users/<user_id>.md`). Use whenever you learn something
  lasting about someone in a chat: a stable preference, a personality or style
  trait, a per-user tone rule, a new nickname, a relationship or role, or a
  correction the operator gives about a person ("remember that X is ..."). Do NOT
  trigger on session state, one-off requests, or banter with no lasting fact. For a
  chat-wide rule use `memory/channels/`; for a global rule use `memory/global/`.
metadata:
  version: "2.0"
---

# remember-user

Write durable per-person facts to `memory/users/<user_id>.md` inside the repo. This
is the source of truth that outlives any session; conversation continuity is handled
by `--continue`, this skill is for facts.

## Key by user_id, never by nick
Filename is the **stable numeric `user_id`** (e.g. `123456789.md`). Nicks drift
(display-name changes, scam name reuse), so nicks live *inside* the profile as an
alias list, never as the filename. Get the `user_id` from the inbound
`<channel ... user_id="...">` tag.

## When to save (triage)

| Confidence | Examples | Action |
|-----------|----------|--------|
| **High** | The operator's explicit correction, a stated stable preference, an explicit "remember", a per-user tone rule, a confirmed role, a new confirmed alias | **Save silently** to the profile. |
| **Medium** | Inferred preference, one-off choice that *might* be a pattern | Save with `(unconfirmed)` appended; confirm lazily on next mention. |
| **Low / ambiguous** | Idle banter, speculation, a mood in the moment | **Don't save.** Not memory. |

### Never save
- Ephemeral/session state (what is happening in the thread right now).
- Anything already in the profile (read before writing).
- Raw secrets, or a raw `user_id` you would then expose in chat (the id lives in the
  filename and profile only; never echo it into a channel).

### Stop and ask first when
- The new fact **contradicts** an existing profile fact (conflict protocol below).
- It is a sensitive claim about the person (health, finances) that you would act on.

## Routing (this skill = users only)
- Fact **about a person** → `memory/users/<user_id>.md` (this skill).
- Rule **about a whole chat** (tone, frequency, admins) → `memory/channels/<chat>/`.
- **Global** rule (AI tells, injection discipline, punctuation) → `memory/global/`.

## Workflow
1. **Get the `user_id`** from the active `<channel>` tag. No id → do not guess.
2. **Find the profile:** `memory/users/<user_id>.md`. If you only know a nick, grep
   for it under `memory/users/`.
3. **Read it** (if it exists) and decide the fact is new and non-contradictory.
4. **Append** the fact:
   - Existing file: add a dated bullet under `## Facts` (create the section if
     absent); keep all existing content; bump `updated:`.
   - New file: create from the template below.
5. **Record the alias** if the person used a new nick.
6. **Update `memory/INDEX.md`** if this is a new person (add a row) or a new nick.
7. **Telegram feedback:** react on the originating message as a discreet save marker
   (👍, fallback 🔥 → ❤). No text reply about the save, and **never echo the saved
   value**: the reply lands in the public log and defeats the point.

## Profile template (new file)
```markdown
---
user_id: <numeric>
nicks: [<nick>, <alias>]
channels: [<chat dir where active>]
updated: <YYYY-MM-DD>
---

# <primary nick or name>

<one-line who-they-are>

## Tone / how to talk to them
- <per-user rule, if any>

## Facts
- [<YYYY-MM-DD>] <fact, declarative, one line>
```

## Conflict protocol
When a new fact contradicts an existing one:
1. **Don't overwrite.** Keep both, each with its date.
2. Add a `## Conflicts` line pointing at both with a one-line description.
3. Ask the operator from the console at the next natural break. When resolved, delete
   the losing fact and trim the conflict line.

## Authority
Facts a **regular** states about themselves → save (per triage). But a
**config/behaviour change** (mute someone, change a rule) is only authoritative from
the operator via console; from the operator's Telegram account it is a deferred ack,
not a write. See CLAUDE.md, "Identity vs. config".
