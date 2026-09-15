#!/usr/bin/env python3
"""Grab a snapshot from a hive's camera and draw its counting line + direction arrow.

  /opt/beecounter/venv/bin/python3 tools/line_preview.py hive2            # reads /opt/beecounter/hive2.env
  ... line_preview.py hive2 --line 0.62 --dir up                           # try values before editing the env

Writes <hive>_line.jpg in the current directory. Open it, adjust LINE_POS until the
line sits across the landing board, then put the value in the env file and restart.
"""
import sys, os, argparse, urllib.request
import cv2, numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("hive")
ap.add_argument("--env-dir", default="/opt/beecounter")
ap.add_argument("--line", type=float)
ap.add_argument("--dir", choices=["down", "up"])
a = ap.parse_args()

env = {}
p = os.path.join(a.env_dir, f"{a.hive}.env")
if os.path.exists(p):
    for line in open(p):
        if "=" in line and not line.startswith("#"):
            k, v = line.strip().split("=", 1); env[k] = v
stream = env.get("STREAM_URL", "")
if not stream:
    sys.exit(f"no STREAM_URL in {p}")
snap = stream.replace("/stream", "/snapshot")
line_pos = a.line if a.line is not None else float(env.get("LINE_POS", 0.5))
direction = a.dir or env.get("IN_DIRECTION", "down")

data = urllib.request.urlopen(snap, timeout=10).read()
img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
h, w = img.shape[:2]
y = int(h * line_pos)
cv2.line(img, (0, y), (w, y), (0, 255, 255), 3)
tip = (w // 2, y + 60) if direction == "down" else (w // 2, y - 60)
cv2.arrowedLine(img, (w // 2, y), tip, (0, 255, 0), 4, tipLength=0.4)
cv2.putText(img, f"{a.hive}  LINE_POS={line_pos}  IN_DIRECTION={direction} (arrow = entering)",
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
out = f"{a.hive}_line.jpg"
cv2.imwrite(out, img)
print(f"wrote {out}  ({w}x{h}, line at y={y})")
