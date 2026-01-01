#!/usr/bin/env pwsh
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

# Ensure we're in the repo root (has a compose file)
if (-not (Test-Path "docker-compose.yml") -and -not (Test-Path "compose.yml") -and -not (Test-Path "compose.yaml")) {
	Write-Error "No compose file found in $PSScriptRoot"
	exit 1
}

Write-Host "[1/3] Bringing down stack and removing volumes/images..."
& docker compose down -v --rmi local --remove-orphans

Write-Host "[2/3] Removing seeded config directory..."
$cfg = Join-Path $PSScriptRoot "config"
if (Test-Path $cfg) {
	# Safety: avoid deleting root
	if ($cfg -ne "\" -and $cfg -ne "/") {
		Remove-Item -Recurse -Force $cfg
		Write-Host "Removed: $cfg"
	} else {
		Write-Warning "Unsafe path resolved for config; skipping."
	}
} else {
	Write-Host "Config directory not found; skipping."
}

Write-Host "[3/3] Optional prune of dangling resources..."
& docker volume prune -f | Out-Null
& docker image prune -f | Out-Null
& docker network prune -f | Out-Null

Write-Host "Cleanup complete."
