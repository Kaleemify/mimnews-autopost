# If the autopost stops: what to check and what to do

No secrets are written in this file. It only says where they live and how to make new ones.

## 1. How it works (one line)
`cron-job.org` (every 15 min) -> starts the **autopost** workflow on GitHub -> `autopost.py` asks Facebook for new posts and asks
https://mimnews.com which are new -> video: download, ffmpeg audio, Whisper transcript -> Gemini writes the item -> the site publishes it.
Backups of that chain: GitHub's own timer (`autopost.yml` schedule) and the **watchdog** workflow (restarts autopost if nothing ran for ~75 min).

## 2. One-look health check
Open **https://mimnews.com/wp-json/mim/v1/health**
- `"ok": true` (HTTP 200) = a run reached the site within the last 45 minutes. Everything in the chain is alive.
- HTTP **503** = no run for 45+ minutes, or the site switch is off. Go to section 3.
- `alarm_job_last_ping_min_ago` = minutes since the cron-job.org alarm job last called this address (it recognises cron-job.org by its user agent). `null` = that job was never created or has never run; a number above ~15 = the alarm job stopped.
- `autopost_drafts_waiting` = items the writer could not finish (they wait as drafts in WordPress for a person to fix or trash).
- A second cron-job.org job that calls this address every 10 minutes and e-mails on failure is the outside alarm (see AUTOTRIGGER.md, "Alarm job").

## 3. Symptom -> cause -> fix
| What you see | Likely cause | What to do |
|---|---|---|
| health = 503 and GitHub > Actions shows no new run | cron-job.org stopped or its GitHub token expired / was deleted | Log in to cron-job.org, open the job, press "Test run". 401/403/404 = new GitHub token needed (fine-grained, this repo only, Actions: read and write, see AUTOTRIGGER.md). The watchdog restarts autopost after ~75 min anyway. |
| runs are red with `HTTP 521/522/523` | the website (Hostinger) was down for a moment | Nothing. The next run catches up, no post is lost. If it lasts for hours, check the hosting panel. |
| runs are red with `exit code 100` / `Failed to fetch ... ubuntu.com` | Ubuntu package servers unreachable | Nothing: the install is tried 4 times and the next run tries again. |
| runs are red at "Check for new Facebook posts" with `Error validating access token: The session has been invalidated because the user changed their password ...` (this happened on 2026-11-20 at ~12:15 UTC) | the Facebook token is tied to the personal profile that made it; changing that profile's password or Facebook's own security reset kills it | **Double-click `refresh-facebook-token.bat`** (opens the 2 Facebook pages, then asks for App ID, App secret and the new token). It stores the new secrets and starts a run. Do not change that Facebook password / use "log out of all devices" without running it again afterwards. |
| posts appear as drafts with Urdu text | Gemini left Urdu-script words, or no model answered for 6 h | Edit the draft in WordPress (change the few Urdu words to Roman letters) and publish, or trash it. Trashed items are rebuilt by the next run when started with `redo_drafts`. |
| a post is missing on the site | it was judged "not news" / a campaign post / too short (the run log says so), or it is older than 48 h | Actions > autopost > run log: look for the Facebook id. To re-check ignored posts start the workflow with `backfill` ticked. |
| nothing publishes, runs say `website says autopost is switched off` | the site switch `mim_autopost_on` is 0 | On the server: `wp option update mim_autopost_on 1`. |
| GitHub says minutes are used up | only possible if the repo is private again (public repos have no minute limit) | Keep the repo public, or set cron-job.org to 30 min. |
| the watchdog / token-check never run any more | GitHub switches scheduled workflows off after 60 days without a commit in a public repo | Every autopost run already switches them back on. If it does not: Actions tab > pick the workflow > "Enable workflow". |

## 4. Making new secrets (GitHub > repo > Settings > Secrets and variables > Actions)
- `FB_PAGE_TOKEN` + `FB_PAGE_ID`: generate a short user token in Graph API Explorer for the app "MIM Autopost" with `pages_show_list` and `pages_read_engagement`,
  put app id / app secret / short token in `../.env` (never commit it), then double-click `setup-facebook.bat`. It stores both secrets for you.
- `GEMINI_API_KEY`: https://aistudio.google.com/apikey -> create key -> double-click `set-gemini-key.bat` (reads it from the clipboard).
- `MIM_KEY` (password between GitHub and the site): make a long random text, save it as the secret, and on the server store its hash:
  `wp option update mim_autopost_key_hash "$(printf '%s' 'THE-NEW-KEY' | sha256sum | cut -d' ' -f1)"`.
- cron-job.org token: GitHub > Settings > Developer settings > Fine-grained tokens (this repo only, **Actions: Read and write**, 1 year). Paste it only into cron-job.org.
  Header must read `Authorization: Bearer <token>` (with the space).

## 5. Switches
- Stop the site accepting posts: `wp option update mim_autopost_on 0` (on the server). Start again with `1`.
- Stop the workflow: GitHub > Actions > autopost > "..." > Disable workflow.
- Manual runs: Actions > autopost > Run workflow. Options: `dry_run` (publish nothing), `backfill` (re-check ignored posts), `redo_drafts` (trash unfinished drafts, rebuild), `max_posts`.

## 6. Built-in safety nets (what already repairs itself)
- Network / website / Facebook hiccups: retried 4 times with pauses; a failed run is simply repeated 15 minutes later.
- A video that cannot be read: retried for 3 h, then written from the caption (`VIDEO_RETRY_HOURS`). A silent video goes straight to the caption.
- Gemini rate limit or outage: the post waits up to 6 h (`GEMINI_RETRY_HOURS`) instead of becoming a raw draft. Four models are tried in order: the fast lite model first (the stronger flash models time out too often to be used first, measured 2026-11-20).
- Duplicates: the site refuses the same Facebook post twice. Flood guard: 30 posts per hour.
- Ubuntu package outage: the ffmpeg install is tried 4 times.
- Dates: posts keep the original Facebook time.

## 7. Limits nobody can remove
- If the client removes page access from the profile that made the token, or Facebook disables the page / app, the autopost cannot read posts.
- Meta's data-access renewal for the app is due around **14 Feb 2027** (see the weekly `token-check` log, `data_access_expires_at`).
- The cron-job.org GitHub token lasts one year.
- Gemini's free tier has daily limits; the 6 h wait covers short outages only.
