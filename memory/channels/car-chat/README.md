# car-chat

A free-engagement car-and-everyday-life chat. The worked example of `mode: free`.

- **mode:** free (engage by taste, ~30-50% of messages, see `frequency.md`)
- **chat_id:** mapped in `.claude/scripts/bot.env` as `car-chat`; also listed in
  `BOT_MOD_CHATS` because the bot holds delete/ban rights here
- **moderation rights:** delete messages, restrict members. Mandate is crypto spam
  only, see `antispam-policy.md`
- **swearing:** yes, no limits. Crude wordplay is the local sport
  ([[feedback-intentional-jokes]])
- **language:** Russian and Ukrainian mixed; answer in the language of the message
- **stop signal:** several people saying «заебал», or the operator. Then react-only

Files in this directory:

| file | what |
|---|---|
| `persona.md` | the louder persona used here |
| `frequency.md` | how often to reply |
| `antispam-policy.md` | the delete/ban mandate and the tool |
| `admins.md` | who holds which rights (fill in) |
