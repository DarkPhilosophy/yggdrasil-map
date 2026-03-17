#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_JSON="$(mktemp /tmp/ygg-topology-XXXXXX.json)"
trap 'rm -f "$TMP_JSON"' EXIT

python3 "$ROOT_DIR/scripts/export_live_admin_snapshot.py" --output "$TMP_JSON"
python3 "$ROOT_DIR/scripts/load_snapshot_to_pg.py" \
  "$TMP_JSON" \
  --host /var/run/postgresql \
  --port 5432 \
  --dbname ygg \
  --user postgres \
  --source yggdrasil-admin \
  --source-revision atvps-live-tree
