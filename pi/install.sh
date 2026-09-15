#!/bin/bash
# Apiary Eyes — Raspberry Pi 5 camera node installer (v1.0.0)
#
#   sudo ./install.sh                 # defaults: cam0 = hive2, cam1 = hive3
#   sudo HIVE0=hive1 HIVE1=hive4 ./install.sh
#
# Idempotent. Every file it changes is copied first to /opt/beehive/backup/<timestamp>/
# and ./rollback.sh restores the most recent backup.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }

RUN_USER="${SUDO_USER:-${RUN_USER:-pi}}"
HIVE0="${HIVE0:-hive2}"
HIVE1="${HIVE1:-hive3}"
APP=/opt/beehive
CONF=/boot/firmware/config.txt
[ -f "$CONF" ] || CONF=/boot/config.txt
TUNING=/usr/share/libcamera/ipa/rpi/pisp/imx519.json
STAMP=$(date +%Y%m%d-%H%M%S)
BK="$APP/backup/$STAMP"
VER=$(cat "$SRC/../VERSION" 2>/dev/null || echo unknown)

echo "=== Apiary Eyes Pi node v$VER — user=$RUN_USER  cam0=$HIVE0  cam1=$HIVE1 ==="

echo "--- 1/6 pre-flight ---"
grep -qi "raspberry pi 5" /proc/device-tree/model 2>/dev/null \
  || echo "  note: not a Pi 5; the tuning file path below is the Pi 5 (pisp) one"
python3 -m py_compile "$SRC/cam_server.py" "$SRC/dashboard.py" "$SRC/imx519_af_patch.py"
echo "  python sources compile OK"

echo "--- 2/6 packages ---"
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  python3-picamera2 python3-flask rpicam-apps python3-libcamera git >/dev/null
echo "  ok"

echo "--- 3/6 backup to $BK ---"
mkdir -p "$BK"
for f in "$APP/cam_server.py" "$APP/dashboard.py" "$CONF" "$TUNING" \
         /etc/systemd/system/hive-cam0.service /etc/systemd/system/hive-cam1.service \
         /etc/systemd/system/hive-dashboard.service; do
  [ -f "$f" ] && mkdir -p "$BK$(dirname "$f")" && cp -p "$f" "$BK$f"
done
echo "$STAMP" > "$APP/backup/LATEST"

echo "--- 4/6 camera overlays in $CONF ---"
REBOOT=0
if grep -q '^camera_auto_detect=1' "$CONF"; then
  sed -i 's/^camera_auto_detect=1/camera_auto_detect=0/' "$CONF"; REBOOT=1
fi
for c in cam0 cam1; do
  if ! grep -q "^dtoverlay=imx519,$c" "$CONF"; then
    echo "dtoverlay=imx519,$c" >> "$CONF"; REBOOT=1
  fi
done
echo "  overlays present"

echo "--- 5/6 IMX519 autofocus tuning ---"
if [ -f "$TUNING" ]; then
  python3 "$SRC/imx519_af_patch.py" "$TUNING" | sed 's/^/  /'
else
  echo "  $TUNING not found (not an IMX519 / different pipeline) — skipped"
fi

echo "--- 6/6 install files and services ---"
mkdir -p "$APP/training/cam0" "$APP/training/cam1"
install -m 755 "$SRC/cam_server.py" "$APP/cam_server.py"
install -m 755 "$SRC/dashboard.py"  "$APP/dashboard.py"
install -m 755 "$SRC/imx519_af_patch.py" "$APP/imx519_af_patch.py"
chown -R "$RUN_USER" "$APP/training"
for i in 0 1; do
  sed -e "s/__CAM__/$i/g" -e "s/__PORT__/$((8090+i))/g" -e "s/__USER__/$RUN_USER/g" \
    "$SRC/hive-cam.service.tmpl" > /etc/systemd/system/hive-cam$i.service
done
sed -e "s/__USER__/$RUN_USER/g" -e "s/__HIVE0__/$HIVE0/g" -e "s/__HIVE1__/$HIVE1/g" \
  "$SRC/hive-dashboard.service.tmpl" > /etc/systemd/system/hive-dashboard.service
systemctl daemon-reload
systemctl enable hive-cam0 hive-cam1 hive-dashboard >/dev/null 2>&1

IP=$(hostname -I | awk '{print $1}')
if [ "$REBOOT" = 1 ]; then
  echo
  echo "=== DONE — camera overlays changed, REBOOT REQUIRED:  sudo reboot ==="
else
  systemctl restart hive-cam0 hive-cam1 hive-dashboard
  sleep 4
  ok=1
  for s in hive-cam0 hive-cam1 hive-dashboard; do
    systemctl is-active --quiet $s && echo "  $s: active" || { echo "  $s: FAILED"; ok=0; }
  done
  if [ $ok = 0 ]; then
    echo "  a service failed — journalctl -u hive-cam0 -n 30 ; ./rollback.sh restores the previous files"
    exit 1
  fi
  echo
  echo "=== DONE ==="
fi
echo "  control center : http://$IP:8080"
echo "  cam0 ($HIVE0)   : http://$IP:8090/stream"
echo "  cam1 ($HIVE1)   : http://$IP:8091/stream"
echo "  verify cameras : rpicam-hello --list-cameras"
