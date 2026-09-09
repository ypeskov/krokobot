#!/usr/bin/env python3
"""
Pre-filter for incoming chat-channel messages — detects prompt-injection
patterns before the prompt is sent to the Anthropic API.

Wiring: hook type "UserPromptSubmit" in the project's .claude/settings.local.json:

  {
    "hooks": {
      "UserPromptSubmit": [
        {
          "matcher": "",
          "hooks": [
            { "type": "command",
              "command": "python3 /path/to/repo/.claude/scripts/prompt-injection-prefilter.py" }
          ]
        }
      ]
    }
  }

Behavior:
  - Reads the CC hook JSON event from stdin.
  - Inspects the prompt text.
  - Only applies to <channel source="plugin:telegram:telegram"> wrapped
    messages (operator-typed prompts from the CLI are passed through).
  - On a hard hit:
      * Exit 2 with a one-line reason on stderr.
      * CC treats exit 2 as block — the user prompt is not relayed to the
        model, the API call is never made, the session cannot get AUP-wedged.
      * The original payload is appended to
        <BOT_LOG_ROOT>/prefilter/YYYY-MM-DD.log for the operator to review.
  - On a soft hit (suspicious but not definitive): logs to the same file,
    does not block.
  - On clean input: exit 0, prompt passes through unchanged.

Patterns: see PATTERNS_HARD and PATTERNS_SOFT below. Tune as new
injection styles surface — this file is the single source of truth.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import botconfig  # noqa: E402

LOG_DIR = Path(botconfig.LOG_ROOT) / "prefilter"

# --- Detection patterns -----------------------------------------------------

# A "hard" match → block the prompt. Patterns are matched case-insensitively
# against the full extracted message text. Add new ones here; keep the
# rationale comment with each so the next reader knows why it's listed.
PATTERNS_HARD: list[tuple[str, str]] = [
    # The exact shape that wedged the bot once: base64 blob + an
    # explicit instruction to decode and execute it.
    (
        r"(?is)\b(decode|расшифр|раскоди)[a-zа-я ]{0,40}(base[\s\-]*64|b64)"
        r"[^.\n]{0,400}\b(follow|execute|run|apply|obey|выполн|исполн|следуй|подчин)",
        "base64+decode+follow",
    ),
    # The inverse word order — instruction first, blob second.
    (
        r"(?is)\b(follow|execute|run|obey|do exactly|выполни|подчин)[^.\n]{0,80}"
        r"(base[\s\-]*64|b64)[^.\n]{0,80}\b(decode|расшифр|раскоди)",
        "follow+decode+base64",
    ),
    # Direct system-prompt exfiltration phrasing.
    (
        r"(?i)\b(reveal|output|print|show|disclose|leak|выведи|покажи|раскрой|выгрузи)\b"
        r"[^.\n]{0,80}\b(your|the|свой|твой|системный)?\s*"
        r"(complete\s+)?(original\s+)?\b(system\s*prompt|initial(ization)?\s*instructions?"
        r"|системн[ыо]й\s*промпт|первоначальн[ыо]е\s*инструкци)",
        "system-prompt-exfiltration",
    ),
    # "Authorized" framings that try to grant fake permission to break out.
    (
        r"(?i)\b(authorized|approved|sanctioned)\s+(model\s+)?(introspection|audit|debugging|test)\b",
        "fake-authorization-framing",
    ),
    # Classic jailbreak prologues — keep tight to avoid false positives on
    # ordinary chatter about ChatGPT / Claude.
    (
        r"(?i)\b(ignore|disregard|forget)\s+(all\s+)?(previous|prior|earlier|above)\s+(instructions?|prompts?|rules?)\b",
        "ignore-previous-instructions",
    ),
    (
        r"(?i)\b(забудь|игнорируй|отбрось)\s+(все\s+)?(предыдущи[ех]|прежни[ех])\s+(инструкци|правил|промпт)",
        "ignore-previous-instructions-ru",
    ),
    # Persona-takeover with explicit override intent.
    (
        r"(?i)\b(you\s+are\s+now|act\s+as)\s+[^.\n]{0,40}\b(uncensored|unfiltered|jailbroken|DAN|developer\s+mode\s+enabled)\b",
        "persona-override",
    ),
    # Asking the bot to dump configuration / paths / env vars to chat.
    (
        r"(?i)\b(dump|leak|print|show|reveal|раскрой|выведи|покажи)\b[^.\n]{0,40}"
        r"\b(environment\s+variables?|env\s+vars?|\.env|API\s+keys?|secrets?|credentials?|TELEGRAM_BOT_TOKEN|ANTHROPIC_API_KEY)\b",
        "secret-exfiltration",
    ),
]

# A "soft" match → log only, do not block. Useful for tuning the hard list.
PATTERNS_SOFT: list[tuple[str, str]] = [
    # Long base64 blob with no obvious instruction keyword nearby. Could be
    # someone pasting a legitimate data blob; flag but don't block.
    (r"[A-Za-z0-9+/]{60,}={0,2}", "long-base64-blob"),
    # Mention of "system prompt" without an exfiltration verb — could be a
    # technical conversation, but worth eyeballing.
    (r"(?i)\bsystem\s*prompt\b", "system-prompt-mention"),
]

# --- Helpers ----------------------------------------------------------------

CHANNEL_TAG_RE = re.compile(
    r'<channel\s+source="plugin:telegram:telegram"[^>]*>(.*?)</channel>',
    re.DOTALL,
)


def extract_channel_payload(prompt: str) -> str | None:
    """Return the inner text of the telegram <channel> block, or None if the
    prompt is operator-typed (no channel tag)."""
    m = CHANNEL_TAG_RE.search(prompt)
    return m.group(1).strip() if m else None


def first_hard_match(text: str) -> tuple[str, str] | None:
    for pattern, label in PATTERNS_HARD:
        m = re.search(pattern, text)
        if m:
            return label, m.group(0)[:200]
    return None


def soft_matches(text: str) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for pattern, label in PATTERNS_SOFT:
        m = re.search(pattern, text)
        if m:
            hits.append((label, m.group(0)[:200]))
    return hits


def append_log(verdict: str, label: str, snippet: str, payload: str, event_meta: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = LOG_DIR / f"{day}.log"
    with path.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "verdict": verdict,
                    "label": label,
                    "snippet": snippet,
                    "session_id": event_meta.get("session_id"),
                    "payload": payload[:4000],
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except Exception as e:
        # Don't fail the session on malformed hook input — just pass through.
        sys.stderr.write(f"prompt-injection-prefilter: bad stdin json: {e}\n")
        return 0

    # CC's UserPromptSubmit hook delivers the prompt text in the "prompt"
    # field; older / newer revisions may use "user_prompt" or carry it under
    # "tool_input" — accept all three.
    prompt = (
        event.get("prompt")
        or event.get("user_prompt")
        or (event.get("tool_input") or {}).get("prompt")
        or ""
    )
    if not isinstance(prompt, str) or not prompt:
        return 0

    payload = extract_channel_payload(prompt)
    if payload is None:
        # Operator-typed prompt from the CLI — never filter.
        return 0

    hit = first_hard_match(payload)
    if hit is not None:
        label, snippet = hit
        append_log("BLOCKED", label, snippet, payload, event)
        sys.stderr.write(
            f"prompt-injection-prefilter: blocked telegram message — {label}; "
            f"see {LOG_DIR}\n"
        )
        return 2  # exit 2 → CC blocks the prompt

    for label, snippet in soft_matches(payload):
        append_log("SOFT", label, snippet, payload, event)

    return 0


if __name__ == "__main__":
    sys.exit(main())
