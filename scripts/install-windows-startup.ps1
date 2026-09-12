param(
  [Parameter(Mandatory=$true)][string]$Distro,
  [Parameter(Mandatory=$true)][string]$RepoPath,
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$Instance
)
$ErrorActionPreference = 'Stop'
if ($Distro -match '["\r\n]' -or $RepoPath -match '["\r\n]') { throw 'Unsupported quote or newline in path.' }
$AgentFolder = Join-Path $env:LOCALAPPDATA "AI-Agent-OS\$Instance"
New-Item -ItemType Directory -Force -Path $AgentFolder | Out-Null
$AgentDistroLiteral = $Distro.Replace("'", "''")
$AgentRepoLiteral = $RepoPath.Replace("'", "''")
$KeepAlive = @"
`$ErrorActionPreference = 'Continue'
while (`$true) {
  & wsl.exe -d '$AgentDistroLiteral' --exec /bin/sleep infinity
  Start-Sleep -Seconds 15
}
"@
$OpenDashboard = @"
`$ErrorActionPreference = 'Stop'
& wsl.exe -d '$AgentDistroLiteral' --exec python3 '$AgentRepoLiteral/.agent-os/open.py'
"@
$KeepAlivePath = Join-Path $AgentFolder 'keep-alive.ps1'
$DashboardPath = Join-Path $AgentFolder 'open-dashboard.ps1'
Set-Content -LiteralPath $KeepAlivePath -Value $KeepAlive -Encoding UTF8
Set-Content -LiteralPath $DashboardPath -Value $OpenDashboard -Encoding UTF8
$AgentShell = New-Object -ComObject WScript.Shell
$Startup = [Environment]::GetFolderPath('Startup')
$Desktop = [Environment]::GetFolderPath('Desktop')
foreach ($Spec in @(@{Folder=$Startup; Name="AI Agent OS $Instance"; Script=$KeepAlivePath}, @{Folder=$Desktop; Name="AI Agent OS $Instance"; Script=$DashboardPath})) {
  $Shortcut = $AgentShell.CreateShortcut((Join-Path $Spec.Folder ($Spec.Name + '.lnk')))
  $Shortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
  $Shortcut.Arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $Spec.Script + '"'
  $Shortcut.WindowStyle = 7
  $Shortcut.Save()
}
# Start this user's WSL keep-alive now. Reinstalling does not add another startup entry.
$AgentAlreadyRunning = Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($KeepAlivePath) }
if (-not $AgentAlreadyRunning) {
  Start-Process powershell.exe -WindowStyle Hidden -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File "' + $KeepAlivePath + '"')
}
Write-Output "Windows startup and dashboard shortcut installed for $Instance."
