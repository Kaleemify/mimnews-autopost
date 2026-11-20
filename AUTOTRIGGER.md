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
