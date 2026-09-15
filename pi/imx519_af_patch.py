#!/usr/bin/env python3
"""Add / widen the rpi.af block in libcamera's imx519.json so autofocus sweeps the
full AK7375 VCM range (0-4095). Idempotent. Usage: sudo python3 imx519_af_patch.py [path]

Why: the stock tuning file has no AF section, and the commonly copied default
lens map [0->445, 15->925] only covers ~12% of the motor's travel, so focus
changes are nearly invisible. See docs/imx519-autofocus.md.
"""
import json, sys, os

DEFAULT = "/usr/share/libcamera/ipa/rpi/pisp/imx519.json"   # Pi 5. Pi 4/Zero: .../vc4/imx519.json
path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
if not os.path.exists(path):
    print(f"not found: {path}")
    sys.exit(1)

FULL_MAP = [0.0, 0, 15.0, 4095]
AF_BLOCK = {
    "rpi.af": {
        "ranges": {
            "normal": {"min": 0.0, "max": 15.0, "default": 1.0},
            "macro":  {"min": 0.0, "max": 15.0, "default": 4.0},
        },
        "speeds": {
            "normal": {
                "step_coarse": 1.0, "step_fine": 0.25,
                "contrast_ratio": 0.75, "pdaf_gain": -0.02,
                "pdaf_squelch": 0.125, "max_slew": 2.0,
                "pdaf_frames": 20, "dropout_frames": 6, "step_frames": 4,
            }
        },
        "conf_epsilon": 8, "conf_thresh": 16, "conf_clip": 512,
        "skip_frames": 5,
        "map": FULL_MAP,
    }
}

with open(path) as f:
    data = json.load(f)

algos = data["algorithms"]
existing = [a for a in algos if "rpi.af" in a]
if not existing:
    algos.append(AF_BLOCK)
    print("rpi.af block added")
elif existing[0]["rpi.af"].get("map") != FULL_MAP:
    existing[0]["rpi.af"]["map"] = FULL_MAP
    existing[0]["rpi.af"]["ranges"] = AF_BLOCK["rpi.af"]["ranges"]
    print("rpi.af map widened to full range")
else:
    print("rpi.af already at full range, nothing to do")
    sys.exit(0)

with open(path, "w") as f:
    json.dump(data, f, indent=4)
print(f"written: {path}")
