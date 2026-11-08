@echo off
rem Sets GEMINI_API_KEY (taken from your clipboard) as a GitHub secret of the autopost repo.
rem The key is never printed and never written to a file.
echo.
echo  Step 1: In Google AI Studio click "Copy key".
echo  Step 2: This window reads it from the clipboard and stores it in GitHub.
echo.
pause
powershell -NoProfile -Command "$k=(Get-Clipboard -Raw); if($null -eq $k){Write-Host 'Clipboard is empty. Click Copy key first.'; exit 2}; $k=$k.Trim(); if($k.Length -lt 20 -or $k -match '\s'){Write-Host 'The clipboard does not look like an API key. Click Copy key first.'; exit 2}; $k | gh secret set GEMINI_API_KEY -R Kaleemify/mimnews-autopost; exit $LASTEXITCODE"
echo.
if errorlevel 1 (echo  FAILED. Tell Claude what the line above says.) else (echo  DONE. The Gemini key is stored in GitHub. You can close this window.)
echo.
pause
