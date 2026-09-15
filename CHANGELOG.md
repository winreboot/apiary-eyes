# Changelog

## 1.0.0 — 2026-09-15

First public release. Consolidates the working Dusk Apiary Observatory setup:

- Pi 5 node: dual IMX519 MJPEG servers (`hive-cam0` :8090, `hive-cam1` :8091)
  with runtime resolution/FPS control, snapshot endpoint, training-frame capture;
  control center dashboard (`hive-dashboard` :8080) proxying both cameras.
- IMX519 autofocus fix applied by the installer (`rpi.af` block, full 0–4095 VCM map).
- GPU counter: YOLO11 + ByteTrack, manual OpenCV frame reader with reconnect,
  inference rate cap, per-minute `bee_traffic` points to InfluxDB, one systemd
  instance per hive.
- `train.sh` reproduces the public model (Roboflow `thesisbees/bee-detector-6zlc9` v4,
  40 epochs, batch 16, mAP50 0.944 on an RTX 4070 SUPER).
- `finetune.sh` auto-labels frames captured on the Pi and fine-tunes on them.
- `tools/line_preview.py` for placing the counting line.
- Timestamped backups and `rollback.sh` on both installers.
