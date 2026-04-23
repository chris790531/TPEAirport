$ErrorActionPreference = "Stop"

function Test-IsAdmin {
  $currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (!(Test-IsAdmin)) {
  throw "Please run PowerShell as Administrator to register/update the scheduled task."
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path (Join-Path $projectRoot ".venv") "Scripts\\python.exe"

if (!(Test-Path $pythonExe)) {
  throw "Virtualenv python not found: $pythonExe. Please create .venv and install dependencies first."
}

$taskName = "TPEAirportFlightForecastHourly"

$outDir = Join-Path $projectRoot "data"
$actionArgs = "-m scripts.update_flightforecast --out `"$outDir`""

# Prefer setting working directory on the action if supported.
try {
  $action = New-ScheduledTaskAction -Execute $pythonExe -Argument $actionArgs -WorkingDirectory $projectRoot
} catch {
  $action = New-ScheduledTaskAction -Execute $pythonExe -Argument $actionArgs
}

# Create a daily trigger and repeat every hour
$trigger = New-ScheduledTaskTrigger -Daily -At 00:00
$trigger.RepetitionInterval = (New-TimeSpan -Hours 1)
$trigger.RepetitionDuration = (New-TimeSpan -Days 3650)

$settings = New-ScheduledTaskSettingsSet `
  -StartWhenAvailable `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -MultipleInstances IgnoreNew

$userId = ("{0}\\{1}" -f $env:UserDomain, $env:UserName)
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Highest

try {
  Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -WorkingDirectory $projectRoot -Force | Out-Null
} catch {
  # Some Windows builds don't accept -WorkingDirectory on Register-ScheduledTask.
  Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
}

Write-Output "已建立/更新排程：$taskName"
Write-Output "WorkingDirectory: $projectRoot"
Write-Output "Command: $pythonExe $actionArgs"

