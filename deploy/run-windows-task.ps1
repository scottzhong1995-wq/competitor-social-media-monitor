$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
Set-Location $project
$env:YOUTUBE_API_KEY = [Environment]::GetEnvironmentVariable('YOUTUBE_API_KEY', 'User')
if (!$env:YOUTUBE_API_KEY) { throw 'YOUTUBE_API_KEY is missing.' }
New-Item -ItemType Directory -Force -Path (Join-Path $project 'data') | Out-Null
& (Join-Path $project '.venv\Scripts\python.exe') -u -m monitor schedule --timezone Asia/Shanghai *> (Join-Path $project 'data\scheduler.log')
exit $LASTEXITCODE
