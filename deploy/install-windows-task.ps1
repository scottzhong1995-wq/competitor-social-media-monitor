param([string]$ProjectPath = (Split-Path $PSScriptRoot -Parent))
$ErrorActionPreference = 'Stop'
$python = Join-Path $ProjectPath '.venv\Scripts\python.exe'
if (!(Test-Path $python)) { throw 'Run 01-install.cmd first.' }
if (![Environment]::GetEnvironmentVariable('YOUTUBE_API_KEY', 'User')) {
    throw 'Set YOUTUBE_API_KEY in Windows user environment variables first. Never paste it into this script.'
}
$runner = Join-Path $ProjectPath 'deploy\run-windows-task.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -File "' + $runner + '"') -WorkingDirectory $ProjectPath
$trigger = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'QrongeMonitor' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Beijing 02:00 collection; Tuesday 03:00 reports; no daytime catch-up.' -Force | Out-Null
Write-Host 'Installed logon task QrongeMonitor. Not started. Close the old night window before starting this task.'
