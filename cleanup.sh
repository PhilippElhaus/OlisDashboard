#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure we're in the repo root (has a compose file)
if [ ! -f "docker-compose.yml" ] && [ ! -f "compose.yml" ] && [ ! -f "compose.yaml" ]; then
	echo "No compose file found in $SCRIPT_DIR"
	exit 1
fi

echo "[1/3] Bringing down stack and removing volumes/images..."
docker compose down -v --rmi local --remove-orphans

echo "[2/3] Removing seeded config directory..."
CFG="$SCRIPT_DIR/config"
if [ -d "$CFG" ] && [ "$CFG" != "/" ]; then
	rm -rf -- "$CFG"
	echo "Removed: $CFG"
else
	echo "Config directory not found or unsafe path: $CFG (skipped)"
fi

echo "[3/3] Optional prune of dangling resources..."
docker volume prune -f >/dev/null || true
docker image prune -f >/dev/null || true
docker network prune -f >/dev/null || true

echo "Cleanup complete."
