@echo off
:: Auto-update senate2026.html betting odds and push to GitHub
:: Runs every hour via Windows Task Scheduler

cd /d "%~dp0"

:: Run the scraper
python update_betting_odds.py
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python script failed with code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

:: Commit and push if there are changes
git diff --quiet senate2026.html
if %ERRORLEVEL% neq 0 (
    git add senate2026.html
    git commit -m "Auto-update senate betting odds"
    git push
    echo Pushed updated betting odds to GitHub.
) else (
    echo No changes to senate2026.html, skipping commit.
)
