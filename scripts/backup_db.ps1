# Daily database backup for the Triam CRM (Windows).
#
#   powershell -ExecutionPolicy Bypass -File scripts\backup_db.ps1
#
# Reads the database address from the file named in -ConfigFile (default: backup.config next to this
# script, one line: DATABASE_URL=postgresql://user:pass@host:port/db). Keep that file private.
#
# Writes <BackupDir>\daily\triam-crm-YYYY-MM-DD.sql.gz and, on Saturdays, a copy in <BackupDir>\weekly
# (weekend data kept without being overwritten). Keeps the last 14 daily and 8 weekly backups.
# Needs pg_dump from PostgreSQL client tools with the same major version as the server, or newer.
#
# Restore into an EMPTY database:
#   gzip -dc triam-crm-YYYY-MM-DD.sql.gz | psql "<target database url>"
param(
  [string]$ConfigFile = (Join-Path $PSScriptRoot "backup.config"),
  [string]$BackupDir = "D:\Backups\TriamCRM",
  [string]$PgDump = "pg_dump",
  [int]$DailyKeep = 14,
  [int]$WeeklyKeep = 8
)
$ErrorActionPreference = "Stop"

$line = Get-Content $ConfigFile | Where-Object { $_ -match '^\s*DATABASE_URL\s*=' } | Select-Object -First 1
if (-not $line) { throw "DATABASE_URL not found in $ConfigFile" }
$url = ($line -split '=', 2)[1].Trim() -replace '^postgresql\+[a-z0-9]+://', 'postgresql://'

$daily = Join-Path $BackupDir "daily"; $weekly = Join-Path $BackupDir "weekly"
New-Item -ItemType Directory -Force $daily, $weekly | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd"
$sql = Join-Path $daily "triam-crm-$stamp.sql"
$gz = "$sql.gz"

& $PgDump --no-owner --no-privileges --file $sql $url
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed with exit code $LASTEXITCODE" }

# gzip the dump, then remove the plain file
$in = [IO.File]::OpenRead($sql); $out = [IO.File]::Create($gz)
$zip = New-Object IO.Compression.GZipStream($out, [IO.Compression.CompressionLevel]::Optimal)
$in.CopyTo($zip); $zip.Dispose(); $out.Dispose(); $in.Dispose()
Remove-Item $sql
"Backup written: $gz ({0:N1} MB)" -f ((Get-Item $gz).Length / 1MB)

if ((Get-Date).DayOfWeek -eq "Saturday") {
  Copy-Item $gz $weekly -Force
  "Weekly copy kept: $(Join-Path $weekly (Split-Path $gz -Leaf))"
}

# Retention: newest first, delete beyond the limits
Get-ChildItem $daily -Filter "triam-crm-*.sql.gz" | Sort-Object LastWriteTime -Descending | Select-Object -Skip $DailyKeep | Remove-Item
Get-ChildItem $weekly -Filter "triam-crm-*.sql.gz" | Sort-Object LastWriteTime -Descending | Select-Object -Skip $WeeklyKeep | Remove-Item
