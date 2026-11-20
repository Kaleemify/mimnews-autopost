@echo off
rem Makes a NEW Facebook page token when the old one died (password change, "log out everywhere", Facebook security reset).
rem You do the Facebook login and 3 copy-pastes. Nothing secret is printed or saved to a file; the script puts the token straight into GitHub Secrets.
cd /d "%~dp0"
echo.
echo  === NEW FACEBOOK TOKEN for the MIM News autopost ===
echo.
echo  Two browser tabs will open. Do these steps there, then come back to this window:
echo.
echo   TAB 1 (Facebook app, "MIM Autopost"): Settings ^> Basic.
echo         Copy the "App ID" (it is shown) and click "Show" next to "App secret" to see the secret.
echo         Keep this tab open: you will paste both values here in a minute.
echo.
echo   TAB 2 (Graph API Explorer):
echo         - Meta App: choose "MIM Autopost"
echo         - Click "Add a Permission" and add:  pages_show_list  and  pages_read_engagement
echo         - Click "Generate Access Token". Log in if Facebook asks, and TICK the "MIM News" page in the popup.
echo         - Copy the long token shown in the box at the top.
echo.
start "" "https://developers.facebook.com/apps/"
start "" "https://developers.facebook.com/tools/explorer/"
pause
echo.
echo  Now this window asks 3 things: App ID, then App secret (hidden), then the token (hidden). Paste with a right-click, then Enter.
echo.
python get_page_token.py
if errorlevel 1 goto failed
echo.
echo  Starting the autopost once now to prove it works...
gh api -X POST repos/Kaleemify/mimnews-autopost/actions/workflows/autopost.yml/dispatches -f ref=main >nul 2>&1
if errorlevel 1 goto nostart
echo  Started. In about 3 minutes open https://mimnews.com/wp-json/mim/v1/health : "ok":true means the autopost is running again.
goto done
:nostart
echo  Could not start it from here. cron-job.org starts it by itself within 15 minutes.
:done
echo.
echo  DONE.
pause
exit /b 0
:failed
echo.
echo  FAILED. Copy only the ERROR line above to Claude (never the token, the app secret or the app id).
pause
exit /b 1
