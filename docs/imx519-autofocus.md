# IMX519 autofocus fix

The Arducam / LEEKWI 16 MP IMX519 modules have an AK7375 voice-coil motor and **no
manual focus ring**, so software autofocus is not optional.

Two problems with a stock Raspberry Pi OS:

1. `libcamera`'s tuning file for this sensor ships **without an `rpi.af` section**,
   so `AfMode=Continuous` is accepted but nothing moves.
2. The `rpi.af` block people usually graft in from another sensor has a lens map of
   `[0.0, 445, 15.0, 925]` — about 12 % of the motor's 0–4095 travel. Focus "works"
   but changes are barely perceptible.

`pi/imx519_af_patch.py` (run by `install.sh`) adds an `rpi.af` block with the map
widened to `[0.0, 0, 15.0, 4095]` and both AF ranges set to 0–15. It is idempotent
and the installer backs the original file up first.

Tuning file location:

| board | pipeline | path |
|---|---|---|
| Pi 5 | pisp | `/usr/share/libcamera/ipa/rpi/pisp/imx519.json` |
| Pi 4 / Zero 2 / Zero | vc4 | `/usr/share/libcamera/ipa/rpi/vc4/imx519.json` |

Other things worth knowing:

- The `imx519` and `ak7375` drivers are in the stock kernel. `dtoverlay=imx519,cam0`
  enables the VCM; no Arducam binaries are needed (they do not run on ARMv6 anyway).
- `camera_auto_detect=0` is required; auto-detect does not identify the IMX519.
- `2328×1748` is the sensor's 2×2 binned mode — the sweet spot for detail vs. load.
  The cam server requests it as the sensor mode and scales the stream from there.
- The `Unsupported V4L2 pixel format Nc12` line in the log on Pi 5 is cosmetic.
- Verify after reboot with `rpicam-hello --list-cameras` (expect two entries) and by
  waving a hand 30 cm in front of a lens while watching the stream — the refocus
  should be obvious.
