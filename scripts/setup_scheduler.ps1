# Setup Windows Task Scheduler for AifaQuant daily refresh.
# Run this script once as Administrator to register the scheduled task.
# The task runs every weekday at 15:35 (after A-share market close).

param(
    [string]$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path,
    [string]$TaskName = "AifaQuant_DailyRefresh",
    [string]$At = "15:35"
)

$batPath = Join-Path $ProjectRoot "scripts\daily_refresh.bat"
if (-not (Test-Path -LiteralPath $batPath)) {
    throw "daily_refresh.bat not found: $batPath"
}

# Remove existing task if present.
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task: $TaskName"
}

$action = New-ScheduledTaskAction -Execute $batPath -WorkingDirectory $ProjectRoot
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $At
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "AifaQuant: fetch data + run strategy + push to Supabase (Mon-Fri $At)"

Write-Host ""
Write-Host "Done! Task '$TaskName' registered."
Write-Host "  Schedule: Mon-Fri at $At"
Write-Host "  Action:   $batPath"
Write-Host ""
Write-Host "To test manually: schtasks /Run /TN $TaskName"
Write-Host "To check status:  schtasks /Query /TN $TaskName"