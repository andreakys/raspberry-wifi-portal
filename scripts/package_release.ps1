$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$ProjectName = Split-Path -Leaf $ProjectDir
$ProjectParent = Split-Path -Parent $ProjectDir
$OutputDir = Join-Path $ProjectDir "release"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$ArchivePath = Join-Path $OutputDir "raspberry-wifi-portal-$Timestamp.tar.gz"

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

tar.exe `
  --exclude="$ProjectName/.agents" `
  --exclude="$ProjectName/.codex" `
  --exclude="$ProjectName/.codex-remote-attachments" `
  --exclude="$ProjectName/.git" `
  --exclude="$ProjectName/.git.*" `
  --exclude="$ProjectName/.venv" `
  --exclude="$ProjectName/output" `
  --exclude="$ProjectName/release" `
  --exclude="$ProjectName/tmp" `
  --exclude="$ProjectName/__pycache__" `
  --exclude="$ProjectName/scripts/__pycache__" `
  --exclude="$ProjectName/services/__pycache__" `
  --exclude="$ProjectName/tests/__pycache__" `
  -czf $ArchivePath `
  -C $ProjectParent `
  $ProjectName

Write-Host "Pacchetto creato: $ArchivePath"
