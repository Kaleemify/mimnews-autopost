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
