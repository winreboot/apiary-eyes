# Troubleshooting

**Counts are zero.**
Night? Correct — bees do not fly in the dark. Daytime? Check
`journalctl -u beecounter@hive2 | grep starting`: if `model=` ends in `yolo11n.pt`
you have no bee model yet — run `train.sh`. If it is `bees.pt`, open the control
center and confirm the camera is actually looking at bees.

**`Waiting for stream 0` repeated forever (older versions).**
The ultralytics stream loader stalls on Flask multipart MJPEG. This repo's counter
reads frames with OpenCV itself and reconnects after 25 failed reads; if you see this
you are running an old `bee_counter.py`.

**`Permission denied: 'yolo11n.pt'`.**
The service's working directory was not writable, so ultralytics could not download
the stock model. The unit sets `WorkingDirectory=/opt/beecounter` and the installer
pre-downloads the file; re-run `install.sh`.

**`stream lost, reconnecting in 5s` every few minutes.**
Wi-Fi at the hives. The counter recovers on its own; each reconnect loses a few
seconds of tracking. A directional antenna or a Wi-Fi extender near the apiary is
the real fix. Dropping the Pi stream to 1280×960 @ 10 fps halves the bandwidth.

**Counts inverted (in/out swapped).**
Flip `IN_DIRECTION` in the hive's env file and restart the service.
`tools/line_preview.py` draws the arrow so you can see which way "in" points.

**Big in counts, tiny out (or vice versa) all day.**
The line is probably on the wrong side of where bees cluster or land. Move
`LINE_POS` so bees must cross it to reach the entrance and cannot loiter on it.

**Training OOMs or runs at batch 4.**
Something else is on the GPU. `train.sh` stops the counters and unloads Ollama;
if you started training by hand, do that first. `nvidia-smi` shows who has the memory.

**Pi: one camera missing after reboot.**
`rpicam-hello --list-cameras`. Reseat the ribbon (contacts toward the board on the
Pi 5's mini connectors). `dmesg | grep -i imx519` shows whether the sensor probed.

**Pi: focus barely moves.**
The tuning patch did not apply. `sudo python3 /opt/beehive/imx519_af_patch.py` prints
what it did; then `sudo systemctl restart hive-cam0 hive-cam1`. See
[imx519-autofocus.md](imx519-autofocus.md).

**Control center shows OFFLINE for a camera.**
`systemctl status hive-cam0`. The usual cause is a second process holding the
camera (a stray `rpicam-hello`). Only one process can open a camera at a time.
