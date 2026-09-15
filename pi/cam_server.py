#!/usr/bin/env python3
"""Apiary Eyes — MJPEG camera server for one libcamera camera (IMX519 tested).

Runtime resolution/FPS control and training-frame capture over a small HTTP API.

Environment:
  CAM_NUM     camera index (0 or 1)                    default 0
  PORT        HTTP port                                 default 8090
  WIDTH       initial stream width                      default 1280
  HEIGHT      initial stream height                     default 960
  FPS         initial frame rate                        default 15
  SENSOR_W/H  sensor mode requested from libcamera      default 2328x1748 (IMX519 2x2 binned)
  TRAIN_ROOT  where captured frames go                  default /opt/beehive/training

Endpoints:
  GET  /            minimal viewer
  GET  /stream      multipart MJPEG (what the counter reads)
  GET  /snapshot    one JPEG
  GET  /status      {width,height,fps,training_images}
  POST /config      {"width":1280,"height":960,"fps":15}
  POST /capture     save current frame to TRAIN_ROOT/cam<N>/
"""
import io, os, time, threading
from flask import Flask, Response, request, jsonify
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput
from libcamera import controls

VERSION = "1.0.0"

CAM_NUM   = int(os.environ.get("CAM_NUM", 0))
PORT      = int(os.environ.get("PORT", 8090))
SENSOR_W  = int(os.environ.get("SENSOR_W", 2328))
SENSOR_H  = int(os.environ.get("SENSOR_H", 1748))
TRAIN_DIR = os.path.join(os.environ.get("TRAIN_ROOT", "/opt/beehive/training"), f"cam{CAM_NUM}")
os.makedirs(TRAIN_DIR, exist_ok=True)

RESOLUTIONS = [(640, 480), (1280, 960), (1920, 1440), (2328, 1748)]
FRAME_RATES = (5, 10, 15, 25)

state = {
    "width":  int(os.environ.get("WIDTH", 1280)),
    "height": int(os.environ.get("HEIGHT", 960)),
    "fps":    int(os.environ.get("FPS", 15)),
}


class StreamOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = threading.Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


picam2 = Picamera2(camera_num=CAM_NUM)
output = StreamOutput()
cam_lock = threading.Lock()


def start_camera(width, height, fps):
    config = picam2.create_video_configuration(
        main={"size": (width, height)},
        sensor={"output_size": (SENSOR_W, SENSOR_H)},
    )
    picam2.configure(config)
    frame_us = int(1_000_000 / fps)
    picam2.start_recording(MJPEGEncoder(), FileOutput(output))
    try:
        picam2.set_controls({
            "AfMode": controls.AfModeEnum.Continuous,
            "FrameDurationLimits": (frame_us, frame_us),
        })
    except Exception as e:  # camera without AF, or older libcamera
        print(f"control warning: {e}", flush=True)
    state.update(width=width, height=height, fps=fps)
    print(f"cam{CAM_NUM}: streaming {width}x{height} @ {fps} fps", flush=True)


def reconfigure(width, height, fps):
    with cam_lock:
        try:
            picam2.stop_recording()
        except Exception:
            pass
        time.sleep(0.3)
        start_camera(width, height, fps)


def training_count():
    return len([f for f in os.listdir(TRAIN_DIR) if f.endswith(".jpg")])


start_camera(state["width"], state["height"], state["fps"])
app = Flask(__name__)


@app.route("/")
def index():
    return ('<html><body style="margin:0;background:#000">'
            '<img src="/stream" style="width:100%"></body></html>')


@app.route("/stream")
def stream():
    def gen():
        while True:
            with output.condition:
                output.condition.wait()
                frame = output.frame
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n"
                   b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
                   + frame + b"\r\n")
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/snapshot")
def snapshot():
    with output.condition:
        output.condition.wait()
        return Response(output.frame, mimetype="image/jpeg")


@app.route("/status")
def status():
    return jsonify(version=VERSION, cam=CAM_NUM, width=state["width"],
                   height=state["height"], fps=state["fps"],
                   training_images=training_count())


@app.route("/config", methods=["POST"])
def config():
    d = request.get_json(force=True)
    w, h, fps = int(d["width"]), int(d["height"]), int(d["fps"])
    if (w, h) not in RESOLUTIONS:
        return jsonify(error="bad resolution"), 400
    if fps not in FRAME_RATES:
        return jsonify(error="bad fps"), 400
    threading.Thread(target=reconfigure, args=(w, h, fps), daemon=True).start()
    return jsonify(ok=True)


@app.route("/capture", methods=["POST"])
def capture():
    with output.condition:
        output.condition.wait()
        frame = output.frame
    name = time.strftime(f"cam{CAM_NUM}_%Y%m%d_%H%M%S.jpg")
    with open(os.path.join(TRAIN_DIR, name), "wb") as f:
        f.write(frame)
    return jsonify(saved=name, total=training_count())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
