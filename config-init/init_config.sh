#!/bin/sh
set -eu

MARKER="/host-config/.seeded"
if [ -f "$MARKER" ]; then
    echo "Init already completed. Exiting."
    exit 0
fi

mkdir -p /host-config \
         /host-config/grafana/provisioning/datasources \
         /host-config/grafana/provisioning/dashboards

# If someone accidentally created /host-config/prometheus.yml as a dir, clean it
if [ -d /host-config/prometheus.yml ]; then
    rm -rf /host-config/prometheus.yml
fi

# If prometheus.yml was dropped at the root, move it into the dir
if [ -f /host-config/prometheus.yml ]; then
    mkdir -p /host-config/prometheus
    mv -f /host-config/prometheus.yml /host-config/prometheus/prometheus.yml
fi

mkdir -p /host-config/prometheus

# Seed only if missing
if [ ! -f /host-config/prometheus/prometheus.yml ]; then
    cp /defaults/prometheus.yml /host-config/prometheus/prometheus.yml
fi

# Seed Grafana provisioning files without overwriting existing
cp -n /defaults/grafana/provisioning/datasources/* /host-config/grafana/provisioning/datasources/ 2>/dev/null || true
cp -n /defaults/grafana/provisioning/dashboards/* /host-config/grafana/provisioning/dashboards/ 2>/dev/null || true

echo "Config seeding complete."
date -Iseconds > "$MARKER"
