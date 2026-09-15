#!/bin/bash
# Apiary Eyes — GPU box counter installer (v1.0.0)
#
#   ./install.sh                         # interactive: asks Pi address + InfluxDB token
#   PI=192.168.1.185 INFLUX_TOKEN=xxx ./install.sh
#   HIVES="hive2:8090 hive3:8091" ./install.sh     # hive name : Pi stream port
#
# Installs to /opt/beecounter with its own venv, one systemd instance per hive.
# Existing hive .env files are NOT overwritten (your LINE_POS tuning survives).
# Changed files are backed up to /opt/beecounter/backup/<timestamp>/; ./rollback.sh restores.
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP=/opt/beecounter
RUN_USER="${SUDO_USER:-$USER}"
HIVES="${HIVES:-hive2:8090 hive3:8091}"
STAMP=$(date +%Y%m%d-%H%M%S)
BK="$APP/backup/$STAMP"
VER=$(cat "$SRC/../VERSION" 2>/dev/null || echo unknown)

echo "=== Apiary Eyes counter v$VER  user=$RUN_USER  hives: $HIVES ==="

echo "--- 1/6 pre-flight ---"
command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | sed 's/^/  GPU: /' \
  || echo "  nvidia-smi not found — will run on CPU (slow; fine for testing)"
python3 -m py_compile "$SRC/bee_counter.py" "$SRC/tools/line_preview.py" "$SRC/tools/autolabel.py"
echo "  python sources compile OK"

[ -n "${PI:-}" ] || read -rp "Raspberry Pi address [192.168.1.185]: " PI
PI="${PI:-192.168.1.185}"
if [ -z "${INFLUX_TOKEN:-}" ]; then
  if ls "$APP"/*.env >/dev/null 2>&1; then
    INFLUX_TOKEN=$(grep -h '^INFLUX_TOKEN=' "$APP"/*.env | head -1 | cut -d= -f2-)
    echo "  reusing InfluxDB token from existing env file"
  fi
fi
[ -n "${INFLUX_TOKEN:-}" ] || read -rp "InfluxDB token: " INFLUX_TOKEN
for h in $HIVES; do
  port=${h#*:}
  curl -s -m 5 -o /dev/null "http://$PI:$port/status" && echo "  Pi stream :$port reachable" \
    || echo "  WARNING: http://$PI:$port/status not reachable (counter will retry on its own)"
done

echo "--- 2/6 directories + backup ---"
sudo mkdir -p "$APP/models" "$APP/backup" "$APP/tools"
sudo chown -R "$RUN_USER" "$APP"
mkdir -p "$BK"
for f in "$APP/bee_counter.py" /etc/systemd/system/beecounter@.service; do
  [ -f "$f" ] && mkdir -p "$BK$(dirname "$f")" && sudo cp -p "$f" "$BK$f"
done
echo "$STAMP" > "$APP/backup/LATEST"

echo "--- 3/6 python venv (ultralytics, opencv, influxdb-client) ---"
[ -x "$APP/venv/bin/python3" ] || python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install -q --upgrade pip
"$APP/venv/bin/pip" install -q -r "$SRC/requirements.txt"
echo "  ok"

echo "--- 4/6 files ---"
install -m 755 "$SRC/bee_counter.py" "$APP/bee_counter.py"
install -m 755 "$SRC/tools/line_preview.py" "$APP/tools/line_preview.py"
install -m 755 "$SRC/tools/autolabel.py"    "$APP/tools/autolabel.py"
install -m 755 "$SRC/train.sh"    "$APP/train.sh"
install -m 755 "$SRC/finetune.sh" "$APP/finetune.sh"
cp "$SRC/hive.env.example" "$APP/hive.env.example"
if [ ! -f "$APP/models/yolo11n.pt" ]; then
  echo "  downloading stock yolo11n.pt (fallback until bees.pt is trained)"
  ( cd "$APP/models" && "$APP/venv/bin/python3" -c "from ultralytics import YOLO; YOLO('yolo11n.pt')" >/dev/null )
fi
[ -f "$APP/models/bees.pt" ] && echo "  bees.pt present" || echo "  no bees.pt yet — run $APP/train.sh"

echo "--- 5/6 per-hive env files (existing ones kept) ---"
for h in $HIVES; do
  name=${h%%:*}; port=${h#*:}
  if [ -f "$APP/$name.env" ]; then
    echo "  $name.env exists — kept"
  else
    sed -e "s|^STREAM_URL=.*|STREAM_URL=http://$PI:$port/stream|" \
        -e "s|^HIVE=.*|HIVE=$name|" \
        -e "s|^INFLUX_TOKEN=.*|INFLUX_TOKEN=$INFLUX_TOKEN|" \
        "$SRC/hive.env.example" > "$APP/$name.env"
    chmod 600 "$APP/$name.env"
    echo "  $name.env created (stream :$port)"
  fi
done

echo "--- 6/6 systemd ---"
sed "s/__USER__/$RUN_USER/" "$SRC/beecounter@.service" | sudo tee /etc/systemd/system/beecounter@.service >/dev/null
sudo systemctl daemon-reload
units=""
for h in $HIVES; do units="$units beecounter@${h%%:*}"; done
sudo systemctl enable $units >/dev/null 2>&1
sudo systemctl restart $units
sleep 8
ok=1
for u in $units; do
  systemctl is-active --quiet "$u" && echo "  $u: active" || { echo "  $u: FAILED"; ok=0; }
done
[ $ok = 1 ] || { echo "  see: journalctl -u ${units%% *} -n 40   |   ./rollback.sh restores previous files"; exit 1; }

echo
echo "=== DONE ==="
echo "  logs      : journalctl -u ${units#* } -f      (first count line after ~60 s)"
echo "  train     : $APP/train.sh                      (needs a free Roboflow API key)"
echo "  tune line : $APP/venv/bin/python3 $APP/tools/line_preview.py hive2"
