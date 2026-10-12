# Registers the daily Triam CRM backup in Windows Task Scheduler (runs at 02:00 every day as the
# current user). Run once, in PowerShell, after creating scripts\backup.config:
#
#   powershell -ExecutionPolicy Bypass -File scripts\register_backup_task.ps1 -PgDump "C:\Program Files\PostgreSQL\16\bin\pg_dump.exe"
#
# Check it with:  Get-ScheduledTask -TaskName "Triam CRM daily backup"
# Run it now:      Start-ScheduledTask -TaskName "Triam CRM daily backup"
param(
  [string]$PgDump = "pg_dump",
  [string]$BackupDir = "D:\Backups\TriamCRM",
  [string]$At = "02:00"
)
$script = Join-Path $PSScriptRoot "backup_db.ps1"
$config = Join-Path $PSScriptRoot "backup.config"
if (-not (Test-Path $config)) { throw "Create $config first (one line: DATABASE_URL=postgresql://...)" }

$args = "-NoProfile -ExecutionPolicy Bypass -File `"$script`" -ConfigFile `"$config`" -BackupDir `"$BackupDir`" -PgDump `"$PgDump`""
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $args
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "Triam CRM daily backup" -Action $action -Trigger $trigger -Settings $settings `
  -Description "Daily pg_dump of the Triam CRM database (14 daily + 8 weekly copies)" -Force | Out-Null
"Registered: daily at $At, backups in $BackupDir"
