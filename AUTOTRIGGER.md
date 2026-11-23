# Make the autopost start exactly every 15 minutes (optional, fixes GitHub skipping its own timer)

GitHub's built-in timer is often late or skipped. The watchdog workflow restarts autopost after ~75 quiet minutes, which is a safety net.
For exact timing, an outside timer can press the "Run workflow" button through GitHub's API.

1. GitHub > Settings > Developer settings > Personal access tokens > **Fine-grained tokens** > Generate new token
   - Repository access: **Only select repositories** > `mimnews-autopost`
   - Permissions: **Actions: Read and write** (nothing else). Expiry: 1 year.
2. https://cron-job.org (free) > Create cronjob
   - URL: `https://api.github.com/repos/Kaleemify/mimnews-autopost/actions/workflows/autopost.yml/dispatches`
   - Schedule: every 15 minutes
   - Advanced: Method **POST**, Headers `Authorization: Bearer <the token>`, `Accept: application/vnd.github+json`, `Content-Type: application/json`, Body `{"ref":"main"}`
3. Keep the token only inside cron-job.org (never in chat or files). If it ever leaks, delete it on GitHub: it can only start this one workflow.

Running every 15 minutes uses more GitHub minutes: make the repo public first (unlimited minutes).


## Alarm job (second job in cron-job.org, tells YOU when the chain stops)
The first job starts the autopost. This second one only watches it, from outside GitHub, and e-mails you.
1. cron-job.org > Create cronjob. URL: `https://mimnews.com/wp-json/mim/v1/health`  Method: **GET** (no headers, no body, no token needed).
2. Schedule: every 10 minutes.
3. Notifications: turn ON "Notify me when the execution fails" (also when it succeeds again, if offered).
   cron-job.org counts HTTP 503 as a failure. The address answers 200 while a run reached the site within the last 45 minutes and 503 when none did (or the site switch is off).
4. Also turn on failure e-mails for the first job (the one that starts the autopost).
What an alarm means: see RECOVERY.md, section 3.

## Alarm job 2 (recommended): is the WEBSITE itself up?
The /health alarm only watches the autopost chain. If Hostinger, Cloudflare or a WordPress update takes the whole site down, nothing e-mails you. Add a second cron-job.org job:
1. Create cronjob. Title `MIM website up`. URL `https://mimnews.com/` . Method GET. Every **5 minutes**.
2. Notifications (same switches as the first alarm): "execution fails" (notify after 2 failures), "succeeds after it failed before", "disabled because of too many failures".
3. Test run must say 200.
What an alarm means: HTTP 403/5xx/timeouts for cron-job.org's servers, i.e. the site is not reachable (Hostinger down, a blocked range, a broken update). See RECOVERY.md.
(Both alarm jobs live in the same cron-job.org account. If you want an alarm that survives even a cron-job.org problem, add the same two addresses to a second free monitor such as UptimeRobot with e-mail alerts.)
