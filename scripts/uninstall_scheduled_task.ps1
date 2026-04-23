$ErrorActionPreference = "Stop"

$taskName = "TPEAirportFlightForecastHourly"

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
  Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
  Write-Output "已移除排程：$taskName"
} else {
  Write-Output "未找到排程：$taskName"
}

