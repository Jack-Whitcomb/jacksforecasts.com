@echo off
:: Auto-update house2026.html betting odds and push to GitHub
:: Runs every hour via Windows Task Scheduler

cd /d "%~dp0"

:: Run the scraper
python update_house_betting_odds.py
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python script failed with code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

:: Commit and push if there are changes
git diff --quiet house2026.html
if %ERRORLEVEL% neq 0 (
    git add house2026.html
    git commit -m "Auto-update house betting odds"
    git push
    echo Pushed updated betting odds to GitHub.
) else (
    echo No changes to house2026.html, skipping commit.
)
