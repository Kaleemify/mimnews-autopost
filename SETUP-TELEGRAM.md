# MIM News Telegram desk — setup (about 10 minutes, all free)

Reporter/editor sends a **text, photo, video or voice note** to the MIM News Telegram bot  ->  within ~30 minutes it is on the website:
transcript (for video/voice), Pinglish news text, section, cover image, the video playing on the site  ->  the bot replies to the sender with the link.

Already done: website receiver, this program, GitHub repo `Kaleemify/mimnews-autopost`, secrets `MIM_KEY` + variable `MIM_URL`.
Left (needs your accounts):

## 1. Make the bot (3 min)
1. In Telegram open **@BotFather** -> send `/newbot` -> give it a name (e.g. "MIM News Desk") and a username ending in `bot`.
2. BotFather gives a **token**. Keep it private (do not paste it in chat).

## 2. Allow your people (2 min)
In a terminal inside this folder: `python tg_setup.py`
It asks for the token (hidden), then you send "hi" to the bot from each allowed phone, then pick them from a list.
Anyone NOT on the list is ignored silently, so strangers cannot publish.

## 3. Gemini key (free) — writes the Pinglish text (2 min)
https://aistudio.google.com/apikey -> Create API key -> terminal: `gh secret set GEMINI_API_KEY -R Kaleemify/mimnews-autopost` and paste it.
Without it everything is saved as DRAFT with the raw text.

## 4. Try it
Send the bot a news message. Then GitHub -> repo -> Actions -> **telegram-desk** -> **Run workflow** (or wait up to 30 min).
The bot replies "Publish ho gayi: <link>".

## How senders use it
- Write the news in the caption/text (names, place, what happened). Video/voice: speak clearly; Urdu/English both work.
- Start with `draft:` to save it as a draft instead of publishing.
- Videos/voice up to **20 MB** (Telegram's limit for bots; a 1-2 minute phone video is fine). Longer than 15 min: no transcript.
- If something fails the bot says why.

## Safety built in
- Only allowed Telegram ids. Max 5 items per run, 12 per hour on the server, same message never published twice.
- AI is told to use only facts from the message/transcript and to skip non-news; if the AI fails or the text is too thin -> DRAFT.
- Stop everything: on the server `wp option update mim_autopost_on 0`.
- Transcripts can be wrong (especially Urdu). Read the first days' posts. Whisper size: variable `WHISPER_MODEL` (`small` default, `medium` is better for Urdu but slower).

## Free-minutes note
Private repo = 2,000 free minutes/month. A 30-minute schedule uses ~1,440 for idle checks, leaving ~560 for processing (~3 videos/day).
More than that, or faster checks (10 min)? Make the repo public (unlimited; the code has no secrets): `gh repo edit Kaleemify/mimnews-autopost --visibility public --accept-visibility-change-consequences`, then set cron to `*/10`.

## Facebook route (on hold)
`autopost.py` + `SETUP.md` read a Facebook page directly, but that needs ADMIN access to the page (client's). Its schedule is switched off.
