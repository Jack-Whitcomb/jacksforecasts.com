# Run this once (as yourself, no admin needed) to register the hourly Task Scheduler job.
# Open PowerShell, cd to this folder, and run:  .\register_task.ps1

$taskName   = "HouseBettingOddsUpdate"
$scriptPath = "$PSScriptRoot\run_house_update.bat"

$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$scriptPath`""
$trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Hours 1) -Once -At (Get-Date)
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
                                          -StartWhenAvailable `
                                          -RunOnlyIfNetworkAvailable

Register-ScheduledTask -TaskName $taskName `
                       -Action $action `
                       -Trigger $trigger `
                       -Settings $settings `
                       -Description "Scrape house betting odds and push to GitHub every hour" `
                       -Force

Write-Host "Task '$taskName' registered. It will run every hour." -ForegroundColor Green
Write-Host "To run it immediately: Start-ScheduledTask -TaskName '$taskName'"
Write-Host "To remove it:          Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
