# MIM News autopost — setup (one time, about 20 minutes)

Facebook page post  ->  (every 30 min) GitHub Actions  ->  video download + transcript  ->  Gemini writes a Pinglish news item
->  website publishes it (category, cover image, Facebook video embed, source link).

Already done by Claude: website receiver (`mu-plugins/mim-autopost.php`), this program, the GitHub repo, the secrets `MIM_KEY`
and variable `MIM_URL`. What is left needs YOUR logins:

## 1. Facebook (free)
1. Open https://developers.facebook.com/apps  -> **Create App** -> use case **Other** -> type **Business** -> name it "MIM Autopost".
2. App settings -> Basic: note **App ID** and **App Secret**.
3. Open https://developers.facebook.com/tools/explorer  -> choose your app -> **Generate Access Token**
   and tick: `pages_show_list`, `pages_read_engagement`. (Log in as the person who is ADMIN of the page.)
4. Copy the short token it shows, then in a terminal inside this folder run:  `python get_page_token.py`
   Paste App ID, App Secret, token when asked. It stores `FB_PAGE_ID` and `FB_PAGE_TOKEN` in GitHub for you.

## 2. Gemini (free) — writes the Pinglish news text
1. https://aistudio.google.com/apikey -> **Create API key**.
2. Terminal:  `gh secret set GEMINI_API_KEY`  and paste the key.
Without it, posts are still imported but saved as DRAFT with the raw caption/transcript.

## 3. Test, then switch on
- GitHub repo -> Actions -> **autopost** -> **Run workflow** -> tick **Dry run**. It prints what it would publish and publishes nothing.
- Untick dry run to run for real. After that it runs by itself every 30 minutes.

## Switches
- **Stop everything now:** on the server `wp option update mim_autopost_on 0`  (the website refuses new posts).
- Whisper size: repo variable `WHISPER_MODEL` (`tiny` fast / `small` default / `medium` best Urdu, slow).
- Language hint: variable `WHISPER_LANG` (e.g. `ur`), empty = auto-detect.

## Safety rules built in
- Only posts from the last 24 h are published; older unseen ones are ignored (no flood on first run).
- Max 3 posts per run, max 12 per hour on the server. Same Facebook post is never published twice.
- Very short text posts ("Eid Mubarak") and non-news are ignored.
- If Gemini fails or the text looks too thin, the item is saved as DRAFT instead of going live.
- The AI is told to use only facts from the caption/transcript. Transcripts can be wrong, so keep an eye on the first days.

## Free-quota note (GitHub Actions)
A private repo gets 2,000 free minutes/month. Every scheduled run is billed at least 1 minute, even when nothing is new:
- every 30 min = ~1,440 min/month for idle checks, leaving ~560 min for videos (a 3-minute video costs ~5 min) -> about 3 videos/day.
- If you post more videos than that, or want checks every 10 min, make the repo PUBLIC: unlimited minutes, and there are no secrets in the code
  (secrets live in GitHub Secrets). Logs would then be public too (only post titles / Facebook links).
  `gh repo edit --visibility public --accept-visibility-change-consequences`  then change the cron in `.github/workflows/autopost.yml` to `*/10 * * * *`.
