#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mkdir -p /var/lib/ygg-topology
python3 "$ROOT_DIR/scripts/export_live_admin_snapshot.py" \
  --state-file /var/lib/ygg-topology/crawl-state.json | sudo -u postgres python3 "$ROOT_DIR/scripts/load_snapshot_to_pg.py" \
  - \
  --host /var/run/postgresql \
  --port 5432 \
  --dbname ygg \
  --user postgres \
  --source yggdrasil-admin \
  --source-revision atvps-live-tree
