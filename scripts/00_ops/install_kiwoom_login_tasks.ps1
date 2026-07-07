param(
  [ValidateSet("MarketHours", "UntilMidnight")]
  [string]$Mode = "MarketHours"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = "C:\claude cowork\01_projects\Anal_reports"
$PreflightBat = Join-Path $ProjectRoot "run_kiwoom_preflight_0650.bat"
$HealthBat = Join-Path $ProjectRoot "run_kiwoom_session_health.bat"
$WatchdogBat = Join-Path $ProjectRoot "run_kiwoom_session_watchdog.bat"
$StartupBat = Join-Path $ProjectRoot "run_kiwoom_startup_recovery.bat"
$KeeperModeArg = if ($Mode -eq "UntilMidnight") { "--24h" } else { "--market-hours" }
$User = "$env:USERDOMAIN\$env:USERNAME"
if ($env:USERDOMAIN -eq $env:COMPUTERNAME -or [string]::IsNullOrWhiteSpace($env:USERDOMAIN)) {
  $User = $env:USERNAME
}

function Register-Task {
  param(
    [string]$Name,
    [Microsoft.Management.Infrastructure.CimInstance]$Action,
    [Microsoft.Management.Infrastructure.CimInstance[]]$Trigger,
    [string]$Description
  )
  $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
  $principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
  Register-ScheduledTask -TaskName $Name -Action $Action -Trigger $Trigger -Settings $settings -Principal $principal -Description $Description -Force | Out-Null
  Write-Output "Registered $Name"
}

$weekdays = @("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
$preflightTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $weekdays -At "06:50"
$healthTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $weekdays -At "06:55"
$startupTrigger = New-ScheduledTaskTrigger -AtLogOn -User $User

Register-Task -Name "KiwoomPreflight_0650" -Action (New-ScheduledTaskAction -Execute $PreflightBat -Argument $KeeperModeArg -WorkingDirectory $ProjectRoot) -Trigger @($preflightTrigger) -Description "Weekday 06:50 Discord Kiwoom API login reminder and keeper launch. Mode=$Mode"
Register-Task -Name "KiwoomSessionHealth_10m" -Action (New-ScheduledTaskAction -Execute $HealthBat -WorkingDirectory $ProjectRoot) -Trigger @($healthTrigger) -Description "Weekday Kiwoom session health check after preflight."

$watchdogShort = (& cmd.exe /c "for %I in (`"$WatchdogBat`") do @echo %~sI").Trim()
schtasks /Create /TN "KiwoomSessionWatchdog_5m" /SC DAILY /ST 06:55 /RI 5 /DU 08:45 /TR $watchdogShort /RU $env:USERNAME /RL LIMITED /F | Write-Output

Register-Task -Name "KiwoomStartupRecovery_OnLogon" -Action (New-ScheduledTaskAction -Execute $StartupBat -Argument $KeeperModeArg -WorkingDirectory $ProjectRoot) -Trigger @($startupTrigger) -Description "Windows logon recovery: Discord notice and guarded Kiwoom keeper launch. Mode=$Mode"

Write-Output "Installed Kiwoom login automation tasks. Mode=$Mode KeeperArg=$KeeperModeArg"
