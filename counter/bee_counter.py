#!/usr/bin/env python3
"""Apiary Eyes — count bees crossing a virtual line on an MJPEG stream.

YOLO11 detection + ByteTrack IDs, frames read with OpenCV (not the ultralytics
stream loader, which stalls on Flask multipart streams), explicit reconnect,
inference-rate cap, per-minute totals written to InfluxDB.

Environment (see hive.env.example):
  STREAM_URL     http://<pi>:8090/stream          required
  HIVE           tag value, e.g. hive2            required
  INFLUX_TOKEN                                    required
  INFLUX_URL     default http://192.168.1.24:8086
  INFLUX_ORG     default beehive-org
  INFLUX_BUCKET  default beehive
  MODEL          default /opt/beecounter/models/bees.pt (falls back to yolo11n.pt)
  LINE_POS       0.0 top .. 1.0 bottom, default 0.5
  IN_DIRECTION   down|up — which crossing direction counts as entering, default down
  CONF           detection confidence, default 0.25
  PROC_FPS       max inference rate, default 10
  FLUSH_S        write interval seconds, default 60
  COOLDOWN_S     same track cannot count twice within, default 3
"""
import os, time, threading
from collections import defaultdict
import cv2
from ultralytics import YOLO
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

VERSION = "1.0.0"

STREAM_URL   = os.environ["STREAM_URL"]
HIVE         = os.environ["HIVE"]
MODEL        = os.environ.get("MODEL", "/opt/beecounter/models/bees.pt")
FALLBACK     = os.environ.get("FALLBACK_MODEL", "/opt/beecounter/models/yolo11n.pt")
LINE_POS     = float(os.environ.get("LINE_POS", 0.5))
IN_DIRECTION = os.environ.get("IN_DIRECTION", "down")
CONF         = float(os.environ.get("CONF", 0.25))
PROC_FPS     = float(os.environ.get("PROC_FPS", 10))
FLUSH_S      = float(os.environ.get("FLUSH_S", 60))
COOLDOWN     = float(os.environ.get("COOLDOWN_S", 3.0))

INFLUX_URL    = os.environ.get("INFLUX_URL", "http://192.168.1.24:8086")
INFLUX_TOKEN  = os.environ["INFLUX_TOKEN"]
INFLUX_ORG    = os.environ.get("INFLUX_ORG", "beehive-org")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "beehive")

if not os.path.exists(MODEL):
    print(f"WARNING: {MODEL} not found, falling back to {FALLBACK} "
          f"(stock model has no bee class — counts will be ~0 until you run train.sh)", flush=True)
    MODEL = FALLBACK

model = YOLO(MODEL)
client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)

counts = {"in": 0, "out": 0}
visible = 0
lock = threading.Lock()


def flush_loop():
    global visible
    while True:
        time.sleep(FLUSH_S)
        with lock:
            n_in, n_out, n_vis = counts["in"], counts["out"], visible
            counts["in"] = counts["out"] = 0
        try:
            p = (Point("bee_traffic").tag("hive", HIVE)
                 .field("bees_in", n_in).field("bees_out", n_out)
                 .field("bees_visible", n_vis))
            write_api.write(bucket=INFLUX_BUCKET, record=p)
            print(f"[{HIVE}] in={n_in} out={n_out} visible={n_vis}", flush=True)
        except Exception as e:
            print(f"[{HIVE}] InfluxDB write failed: {e}", flush=True)


threading.Thread(target=flush_loop, daemon=True).start()

last_y = {}                       # track id -> last centre y
counted = defaultdict(lambda: 0)  # track id -> last time it was counted
frame_interval = 1.0 / PROC_FPS


def open_stream():
    cap = cv2.VideoCapture(STREAM_URL)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


print(f"[{HIVE}] apiary-eyes counter v{VERSION} stream={STREAM_URL} model={MODEL} "
      f"line={LINE_POS} in={IN_DIRECTION} fps={PROC_FPS}", flush=True)
cap = open_stream()
last_infer = 0.0
fail_count = 0

while True:
    ok, frame = cap.read()
    if not ok:
        fail_count += 1
        if fail_count >= 25:
            print(f"[{HIVE}] stream lost, reconnecting in 5s...", flush=True)
            cap.release()
            time.sleep(5)
            cap = open_stream()
            fail_count = 0
        continue
    fail_count = 0

    now = time.time()
    if now - last_infer < frame_interval:
        continue                      # drop frame: stay realtime, cap GPU load
    last_infer = now

    r = model.track(frame, persist=True, tracker="bytetrack.yaml",
                    conf=CONF, verbose=False)[0]
    line_y = frame.shape[0] * LINE_POS
    n_boxes = 0
    if r.boxes is not None and r.boxes.id is not None:
        ids = r.boxes.id.int().tolist()
        for box, tid in zip(r.boxes.xywh.tolist(), ids):
            n_boxes += 1
            cy = box[1]
            if tid in last_y:
                prev = last_y[tid]
                crossed_down = prev < line_y <= cy
                crossed_up   = prev > line_y >= cy
                if (crossed_down or crossed_up) and now - counted[tid] > COOLDOWN:
                    counted[tid] = now
                    going_in = crossed_down if IN_DIRECTION == "down" else crossed_up
                    with lock:
                        counts["in" if going_in else "out"] += 1
            last_y[tid] = cy
    with lock:
        visible = n_boxes
    if len(last_y) > 500:             # prune stale tracks
        last_y.clear()
        counted.clear()
