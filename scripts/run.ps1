# Run SnipText in development
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$env:PYTHONPATH = $Root
Write-Host "[SnipText] starting from $Root"
py -3 -m sniptext
