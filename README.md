# Apiary Eyes

**Open-source bee traffic counting for hive entrances.**
Raspberry Pi 5 + two autofocus cameras at the hives, YOLO11 + ByteTrack on a
GPU box, per-minute in/out counts in InfluxDB.

Version **1.0.0** — see [CHANGELOG.md](CHANGELOG.md).

Apiary Eyes is the third of three companion projects from the Dusk Apiary
Observatory in Henryville, PA:

| Project | Sense | What it records |
|---|---|---|
| [apiary-nose](https://github.com/winreboot/apiary-nose) | smell | BME688 hive-smell fingerprints, open dataset |
| [apiary-ears](https://github.com/winreboot/apiary-ears) | hearing | INMP441 acoustics, scored swarm events |
| **apiary-eyes** (this repo) | sight | bee traffic at the entrance: bees in, bees out, bees visible |

---

## What it does

```
 hive entrance          hive entrance
      │                       │
 IMX519 cam0             IMX519 cam1
      └──────┐   Raspberry Pi 5   ┌──────┘
             │  MJPEG :8090/:8091 │
             │  control :8080     │
             └─────────┬──────────┘
                       │  http://pi:809x/stream
                       ▼
             GPU box  (RTX 4070 SUPER)
             YOLO11n bee model + ByteTrack
             virtual line crossing → in / out
                       │  every 60 s
                       ▼
             InfluxDB  measurement bee_traffic
             tag hive=hive2|hive3
             fields bees_in, bees_out, bees_visible
                       │
                       ▼
             your dashboard / Grafana / AI briefing
```

The Pi does no inference. It streams video and stores training frames.
All detection runs on a machine with a real GPU; the Pi 5 (2 GB) is not able to
train YOLO and only marginally able to run it.

## Repository layout

```
pi/          Raspberry Pi 5 camera node: installer, MJPEG servers, control center
counter/     GPU box: installer, bee_counter.py, training and fine-tuning scripts
docs/        camera mounting, IMX519 autofocus fix, InfluxDB schema, troubleshooting
publish.sh   push this folder to GitHub
```

## Hardware

- Raspberry Pi 5 (2 GB is enough) on a DHCP-reserved address
- 2 × Arducam / LEEKWI **IMX519 16 MP autofocus** camera modules on the two CSI ports
  (any libcamera camera works, but the autofocus fix in `docs/` is IMX519-specific)
- A Linux box with an NVIDIA GPU for the counter (an RTX 4070 SUPER runs two
  streams at 10 fps with headroom)
- InfluxDB 2.x reachable from the GPU box

Mount each camera looking down on the landing board, close enough that a bee is
at least ~20 px tall in the stream. See [docs/camera-mounting.md](docs/camera-mounting.md).

## Install — Raspberry Pi 5

```sh
git clone https://github.com/winreboot/apiary-eyes.git
cd apiary-eyes/pi
sudo ./install.sh
sudo reboot        # only if the installer says the camera overlays changed
```

After the reboot:

- `http://<pi>:8080` — control center: both cameras, resolution/FPS, training capture
- `http://<pi>:8090/stream` and `:8091/stream` — raw MJPEG, what the counter reads
- `http://<pi>:8090/snapshot` — single JPEG, handy for aiming

`sudo ./rollback.sh` restores the previous install from its timestamped backup.

## Install — GPU box

```sh
git clone https://github.com/winreboot/apiary-eyes.git
cd apiary-eyes/counter
./install.sh           # asks for the Pi address and your InfluxDB token
./train.sh             # first time: downloads the public bee dataset, trains bees.pt
journalctl -u beecounter@hive2 -f
```

Within about a minute of starting you should see lines like

```
[hive2] in=14 out=11 visible=6
```

Zeros at night are correct: bees do not fly in the dark.

## Tuning the counting line

Each hive has an env file in `/opt/beecounter/`:

```
STREAM_URL=http://192.168.1.185:8090/stream
HIVE=hive2
LINE_POS=0.5        # 0.0 = top of frame, 1.0 = bottom
IN_DIRECTION=down   # crossing the line downward counts as entering
PROC_FPS=10
CONF=0.25
```

`counter/tools/line_preview.py` grabs a snapshot and draws the line so you can
place it across the landing board without guessing:

```sh
/opt/beecounter/venv/bin/python3 tools/line_preview.py hive2   # writes hive2_line.jpg
```

If counts look inverted, flip `IN_DIRECTION` and `sudo systemctl restart beecounter@hive2`.

## Training on your own hives

The public model is good (mAP50 0.944) but it was trained on other people's
hives. The control center's **Capture** and **Auto-capture** buttons save frames
from *your* cameras to the Pi. When you have a few hundred, `counter/finetune.sh`
pulls them over, auto-labels them with the current model, and fine-tunes.
Details in [docs/training.md](docs/training.md).

## Data schema

Measurement `bee_traffic`, one point per hive per minute:

| field | type | meaning |
|---|---|---|
| `bees_in` | int | line crossings in the "in" direction during the minute |
| `bees_out` | int | line crossings in the "out" direction |
| `bees_visible` | int | bees tracked in the last processed frame of the minute |

Tag: `hive`. Full notes and example Flux queries in [docs/influxdb-schema.md](docs/influxdb-schema.md).

## Honest limits

- Line-crossing counts are a **traffic index**, not a census. Bees that hover
  across the line, land on the camera side, or re-cross within the 3 s
  cooldown are miscounted. Trends day-to-day are reliable; absolute totals are not.
- The Pi's Flask MJPEG server is single-viewer per stream in practice. The
  counter holds one connection per camera; opening the control center on top
  of that is fine, four browsers is not.
- Wi-Fi at the hives is the weakest link. The counter reconnects on its own,
  but a dropped minute is a dropped minute.

## Contributing

Issues and pull requests welcome. Most useful: labelled entrance images from
different hive types and camera angles, and reports of what `LINE_POS` /
`IN_DIRECTION` worked for your mount. Please open a Discussion for questions.

## License

MIT — see [LICENSE](LICENSE).
