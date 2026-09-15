#!/bin/bash
# Apiary Eyes — fine-tune bees.pt on frames captured from YOUR hives (v1.0.0)
#
#   PI=192.168.1.185 ./finetune.sh
#
# 1. pulls training.tar.gz from the Pi control center (frames you captured on :8080)
# 2. auto-labels them with the current bees.pt (tools/autolabel.py) — review the
#    preview images it writes before trusting them
# 3. builds a dataset that mixes your frames with the public set, fine-tunes from
#    the current bees.pt for a few epochs at a low learning rate, deploys.
#
# Needs: a trained bees.pt, dataset/ from train.sh, ~200+ captured frames.
# NOTE: this script has been written from the working pieces but is the least
# field-tested part of the project. Check the preview labels; report issues.
set -euo pipefail
APP=/opt/beecounter
cd "$APP"
PI="${PI:-192.168.1.185}"
EPOCHS="${EPOCHS:-15}"; BATCH="${BATCH:-16}"
RUN="${RUN:-own-$(date +%Y%m%d-%H%M)}"
OWN="$APP/own-hives"

[ -f models/bees.pt ]   || { echo "no models/bees.pt — run train.sh first"; exit 1; }
[ -f dataset/data.yaml ] || { echo "no dataset/ — run train.sh first"; exit 1; }

echo "--- 1/4 pulling captured frames from http://$PI:8080 ---"
mkdir -p "$OWN"
curl -sf -o /tmp/apiary-eyes-training.tar.gz "http://$PI:8080/training.tar.gz"
tar xzf /tmp/apiary-eyes-training.tar.gz -C "$OWN"
N=$(find "$OWN/training" -name '*.jpg' | wc -l)
echo "  $N frames"
[ "$N" -ge 50 ] || { echo "  fewer than 50 frames — capture more first (Auto-capture on the control center)"; exit 1; }

echo "--- 2/4 auto-labelling with current bees.pt ---"
./venv/bin/python3 tools/autolabel.py "$OWN/training" "$OWN/labelled" --model models/bees.pt --conf 0.4
echo "  review a few of $OWN/labelled/preview/*.jpg before trusting the labels"

echo "--- 3/4 building mixed dataset ---"
./venv/bin/python3 - << PYEOF
import yaml, glob, os, random
base = yaml.safe_load(open("$APP/dataset/data.yaml"))
own = "$OWN/labelled"
imgs = sorted(glob.glob(f"{own}/images/*.jpg")); random.seed(1); random.shuffle(imgs)
cut = max(1, int(len(imgs)*0.85))
open(f"{own}/train.txt","w").write("\n".join(imgs[:cut])+"\n")
open(f"{own}/val.txt","w").write("\n".join(imgs[cut:])+"\n")
# the public set stays in for regularisation; own frames are listed explicitly
d = dict(base)
d["path"] = "$APP"
def resolve(rel):
    # Roboflow yaml paths are absolute after download, or the quirky "../train/images"
    # which actually means dataset/train/images
    if rel.startswith("/"): return rel
    for c in (os.path.normpath(os.path.join("$APP/dataset", rel)),
              os.path.join("$APP/dataset", rel.lstrip("./"))):
        if os.path.isdir(c): return c
    raise SystemExit(f"cannot resolve dataset path {rel}")
d["train"] = [resolve(base["train"]), f"{own}/train.txt"]
d["val"]   = [resolve(base["val"]),   f"{own}/val.txt"]
yaml.safe_dump(d, open(f"{own}/data.yaml","w"))
print("  train images (own):", cut, " val (own):", len(imgs)-cut)
PYEOF

echo "--- 4/4 fine-tuning from bees.pt: epochs=$EPOCHS lr0=0.002 ---"
sudo systemctl stop 'beecounter@*' || true
curl -s -m 5 http://localhost:11434/api/generate -d '{"model":"qwen3:30b-a3b","keep_alive":0}' >/dev/null || true
./venv/bin/yolo train model="$APP/models/bees.pt" data="$OWN/labelled/data.yaml" \
  epochs="$EPOCHS" imgsz=640 batch="$BATCH" lr0=0.002 patience=5 \
  project="$APP/runs" name="$RUN" exist_ok=True
cp models/bees.pt models/bees-prev.pt
cp "runs/$RUN/weights/best.pt" models/bees.pt
for e in "$APP"/*.env; do sudo systemctl start "beecounter@$(basename "$e" .env)"; done
echo "=== DONE: bees.pt fine-tuned on your hives (previous kept as bees-prev.pt) ==="
echo "If counts got worse:  cp models/bees-prev.pt models/bees.pt && sudo systemctl restart 'beecounter@*'"
