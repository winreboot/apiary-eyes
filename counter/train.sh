#!/bin/bash
# Apiary Eyes — train bees.pt from the public Roboflow bee dataset (v1.0.0)
#
#   ./train.sh                      # prompts for a free Roboflow API key
#   RF_API_KEY=xxxx ./train.sh
#   EPOCHS=40 BATCH=16 ./train.sh
#
# Reproduces the reference model: thesisbees / bee-detector-6zlc9 / version 4
# (8,175 annotated images), YOLO11n, imgsz 640, 40 epochs, batch 16, patience 10
# -> mAP50 0.944 on an RTX 4070 SUPER in roughly 3-4 hours.
#
# It stops the counters and asks Ollama to unload its model first: training with
# two live counters and a 30B LLM on a 12 GB card OOMs down to batch 4 and takes
# 10x longer. Run inside tmux so you can disconnect:  tmux new -s beetrain ./train.sh
set -euo pipefail
APP=/opt/beecounter
cd "$APP"
EPOCHS="${EPOCHS:-40}"; BATCH="${BATCH:-16}"; IMGSZ="${IMGSZ:-640}"
RUN="${RUN:-bees-$(date +%Y%m%d-%H%M)}"
OLLAMA="${OLLAMA_URL:-http://localhost:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3:30b-a3b}"

if [ ! -f dataset/data.yaml ]; then
  [ -n "${RF_API_KEY:-}" ] || read -rp "Roboflow API key (free account, Settings -> API Keys): " RF_API_KEY
  echo "--- downloading dataset (thesisbees/bee-detector-6zlc9 v4, ~1.8 GB) ---"
  RF_API_KEY="$RF_API_KEY" ./venv/bin/python3 - << 'PYEOF'
import os
from roboflow import Roboflow
rf = Roboflow(api_key=os.environ["RF_API_KEY"])
ds = rf.workspace("thesisbees").project("bee-detector-6zlc9").version(4).download("yolov11", location="/opt/beecounter/dataset")
print("dataset at", ds.location)
PYEOF
else
  echo "--- dataset already present in $APP/dataset ---"
fi

echo "--- freeing the GPU: stopping counters, unloading $OLLAMA_MODEL ---"
sudo systemctl stop 'beecounter@*' || true
curl -s -m 5 "$OLLAMA/api/generate" -d "{\"model\":\"$OLLAMA_MODEL\",\"keep_alive\":0}" >/dev/null || true
sleep 5
command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=memory.used,memory.free --format=csv

echo "--- training YOLO11n: epochs=$EPOCHS batch=$BATCH imgsz=$IMGSZ run=$RUN ---"
./venv/bin/yolo train model="$APP/models/yolo11n.pt" data="$APP/dataset/data.yaml" \
  epochs="$EPOCHS" imgsz="$IMGSZ" batch="$BATCH" patience=10 \
  project="$APP/runs" name="$RUN" exist_ok=True

echo "--- deploying ---"
[ -f "$APP/models/bees.pt" ] && cp "$APP/models/bees.pt" "$APP/models/bees-prev.pt"
cp "$APP/runs/$RUN/weights/best.pt" "$APP/models/bees.pt"
sudo systemctl start 'beecounter@*' 2>/dev/null || for e in "$APP"/*.env; do sudo systemctl start "beecounter@$(basename "$e" .env)"; done
echo
echo "=== DONE: bees.pt deployed from runs/$RUN (previous kept as bees-prev.pt) ==="
echo "Back it up somewhere off this box, e.g.:"
echo "  scp $APP/models/bees.pt root@192.168.1.24:/volume1/docker/beehive-briefing/backup/bees-$(date +%Y%m%d).pt"
echo "Results: $APP/runs/$RUN/results.csv   (look at metrics/mAP50(B))"
