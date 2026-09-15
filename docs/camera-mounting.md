# Camera mounting

What the counter needs from the picture:

- **Looking down on the landing board**, straight or slightly angled, so bees move
  mostly up/down in the frame. The counting line is horizontal; traffic that crosses
  it sideways is not counted.
- **Bees at least ~20 px** at the stream resolution. At 1280×960 that is roughly
  30–50 cm from lens to landing board with the IMX519.
- **The entrance slot near one edge**, the approach area filling the rest, so a bee
  has to cross the middle of the frame to get in. Put `LINE_POS` across the board
  between the two — `counter/tools/line_preview.py` draws it for you.
- **Shade the lens.** Direct sun on the sensor and strong shadows moving across the
  board through the day are the main sources of false tracks. A small hood over the
  camera helps more than any software setting.
- Autofocus is continuous; once mounted it will lock on the board within a few seconds.
  If the lens hunts constantly, the scene is too flat (all one colour) — a strip of
  contrasting tape on the board gives it something to focus on.

Reference: 1280×960 @ 15 fps is the everyday setting. 2328×1748 @ 25 fps is
"inspection mode" — it pushes the Pi's CPU and Wi-Fi hard and gains nothing for
counting, since the counter caps inference at 10 fps anyway.

Camera to hive mapping is only a label. Ports are fixed (cam0 :8090, cam1 :8091);
which hive each points at is set with `HIVE0` / `HIVE1` on the Pi installer and by
the `HIVE=` line in each env file on the GPU box.
