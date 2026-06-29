# Setup Windows Task Scheduler for AifaQuant daily refresh
# Run this script once as Administrator to register the scheduled task.
# The task runs every weekday at 15:35 (after A-share market close).

$taskName = "AifaQuant_DailyRefresh"
$projectRoot = "d:\kimi\aifa_quant"
$batPath = Join-Path $projectRoot "scripts\daily_refresh.bat"

# Remove existing task if present
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Removed existing task: $taskName"
}

$action = New-ScheduledTaskAction -Execute $batPath -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At "15:35"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "AifaQuant: fetch data + run strategy + push to Supabase (Mon-Fri 15:35)"

Write-Host ""
Write-Host "Done! Task '$taskName' registered."
Write-Host "  Schedule: Mon-Fri at 15:35"
Write-Host "  Action:   $batPath"
Write-Host ""
Write-Host "To test manually: schtasks /Run /TN $taskName"
Write-Host "To check status:  schtasks /Query /TN $taskName"
