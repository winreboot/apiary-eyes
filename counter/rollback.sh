#!/bin/bash
# Restore the most recent counter backup (or a named one: ./rollback.sh 20260915-101500)
set -euo pipefail
APP=/opt/beecounter
STAMP="${1:-$(cat $APP/backup/LATEST 2>/dev/null || true)}"
[ -n "$STAMP" ] && [ -d "$APP/backup/$STAMP" ] || { echo "no backup found"; ls "$APP/backup" 2>/dev/null; exit 1; }
BK="$APP/backup/$STAMP"
echo "restoring from $BK"
( cd "$BK" && find . -type f | while read -r f; do
    dst="${f#.}"; echo "  $dst"; sudo mkdir -p "$(dirname "$dst")"; sudo cp -p "$f" "$dst"; done )
sudo systemctl daemon-reload
sudo systemctl restart 'beecounter@*' 2>/dev/null || true
echo "done"
