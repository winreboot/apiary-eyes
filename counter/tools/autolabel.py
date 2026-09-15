#!/usr/bin/env python3
"""Auto-label captured frames with an existing bee model, in YOLO txt format.

  autolabel.py <frames_dir> <out_dir> [--model bees.pt] [--conf 0.4]

Writes out_dir/images/*.jpg, out_dir/labels/*.txt and out_dir/preview/*.jpg
(boxes drawn, so you can eyeball label quality). Frames with zero detections are
kept as negatives (empty label file) — they teach the model what "no bee" looks like.
"""
import argparse, glob, os, shutil
from ultralytics import YOLO

ap = argparse.ArgumentParser()
ap.add_argument("frames"); ap.add_argument("out")
ap.add_argument("--model", default="/opt/beecounter/models/bees.pt")
ap.add_argument("--conf", type=float, default=0.4)
a = ap.parse_args()

for d in ("images", "labels", "preview"):
    os.makedirs(os.path.join(a.out, d), exist_ok=True)
model = YOLO(a.model)
files = sorted(glob.glob(os.path.join(a.frames, "**", "*.jpg"), recursive=True))
n_img = n_box = 0
for f in files:
    r = model.predict(f, conf=a.conf, verbose=False)[0]
    name = os.path.basename(f)
    shutil.copy(f, os.path.join(a.out, "images", name))
    lines = []
    if r.boxes is not None:
        for cls, xywhn in zip(r.boxes.cls.int().tolist(), r.boxes.xywhn.tolist()):
            lines.append(f"{cls} " + " ".join(f"{v:.6f}" for v in xywhn))
    with open(os.path.join(a.out, "labels", name[:-4] + ".txt"), "w") as fh:
        fh.write("\n".join(lines) + ("\n" if lines else ""))
    r.save(os.path.join(a.out, "preview", name))
    n_img += 1; n_box += len(lines)
print(f"labelled {n_img} frames, {n_box} boxes, previews in {a.out}/preview/")
