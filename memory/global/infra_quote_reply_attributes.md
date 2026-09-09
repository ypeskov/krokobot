---
name: infra-quote-reply-attributes
description: "`<channel>` blocks carry quoted_text / quoted_user / quoted_fragment on quote-replies (plugin patch). A fragment inherits its subject from the quote: read the quote first."
metadata:
  type: reference
---

With the plugin patch applied (`plugin-patches/telegram/`), a quote-reply arrives
with `reply_to_message_id`, `quoted_text`, `quoted_user` and, for a highlighted
partial quote, `quoted_fragment`. Without the patch the bot sees only the new text
and misattributes replies (answering a question that was aimed at another bot, for
instance).

**The patch lives in the versioned plugin cache and is lost on every plugin update.**
If quote visibility "randomly" breaks, check the plugin version first and reapply.

## The quote answers «what», not only «who»

The patch worked and the bot still got it wrong. Someone wrote «есть проблема.
караси или карпы» quoting a message about pouring kerosene into a pond. The bot read
the quote for attribution, decided it was not aimed at it, and parsed the bare
sentence on its own as "which fish to stock". With the quote in hand it is obviously
the opposite: the problem *with the kerosene* is that the fish die.

**Rule: a fragment inherits its subject from the quoted message.** Before answering
any short or elliptical line, read the quote as the first half of the sentence.
Especially lines with no verb («и что», «а если наоборот»): those are almost never
standalone questions.

Until confirmed working, or if the patch is lost: on any bare «объясни / а ты уверен /
это не так» with no name and no antecedent, treat it as possibly a quote-reply to
someone else. Tagging stays the reliable way for users to reach the bot.
