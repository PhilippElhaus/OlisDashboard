#!/usr/bin/env bash
set -euo pipefail

# Move to repo root (directory of this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Sanity checks
docker --version >/dev/null
docker compose version >/dev/null

echo "[1/3] Building init..."
docker compose --profile init build init

echo "[2/3] Seeding config (one-shot init)..."
docker compose --profile init run --rm -T init

echo "[3/3] Starting stack..."
docker compose up -d

echo "Done. Status:"
docker compose ps
