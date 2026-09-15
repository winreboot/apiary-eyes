#!/bin/bash
# Restore the most recent backup made by install.sh (or a named one: ./rollback.sh 20260915-101500)
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
APP=/opt/beehive
STAMP="${1:-$(cat $APP/backup/LATEST 2>/dev/null || true)}"
[ -n "$STAMP" ] && [ -d "$APP/backup/$STAMP" ] || { echo "no backup found"; ls "$APP/backup" 2>/dev/null; exit 1; }
BK="$APP/backup/$STAMP"
echo "restoring from $BK"
( cd "$BK" && find . -type f | while read -r f; do
    dst="${f#.}"; echo "  $dst"; mkdir -p "$(dirname "$dst")"; cp -p "$f" "$dst"; done )
systemctl daemon-reload
systemctl restart hive-cam0 hive-cam1 hive-dashboard 2>/dev/null || true
echo "done. If config.txt or the tuning file were restored, reboot."
