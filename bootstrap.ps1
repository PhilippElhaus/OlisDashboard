#!/usr/bin/env pwsh
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Move to repo root (directory of this script)
Set-Location -Path $PSScriptRoot

# Sanity checks
& docker --version | Out-Null
& docker compose version | Out-Null

Write-Host "[1/3] Building init..."
& docker compose --profile init build init

Write-Host "[2/3] Seeding config (one-shot init)..."
& docker compose --profile init run --rm -T init

Write-Host "[3/3] Starting stack..."
& docker compose up -d

Write-Host "Done. Status:"
& docker compose ps
