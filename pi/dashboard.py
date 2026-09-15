#!/usr/bin/env python3
"""Apiary Eyes — control center: both cameras, live config, training capture.

Proxies the two cam_server instances so one page can show and control both.

Environment:
  PORT        default 8080
  CAM0_PORT   default 8090
  CAM1_PORT   default 8091
  CAM0_HIVE   label for camera 0, default hive2
  CAM1_HIVE   label for camera 1, default hive3
  TRAIN_ROOT  default /opt/beehive/training
"""
import io, os, tarfile, urllib.request
from flask import Flask, Response, render_template_string, request, jsonify

VERSION = "1.0.0"
PORT = int(os.environ.get("PORT", 8080))
CAMS = {0: int(os.environ.get("CAM0_PORT", 8090)),
        1: int(os.environ.get("CAM1_PORT", 8091))}
HIVES = {0: os.environ.get("CAM0_HIVE", "hive2"),
         1: os.environ.get("CAM1_HIVE", "hive3")}
TRAIN_ROOT = os.environ.get("TRAIN_ROOT", "/opt/beehive/training")

app = Flask(__name__)

PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>Apiary Eyes</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 body { margin:0; background:#1a1a1a; color:#eee; font-family:sans-serif; }
 h1 { text-align:center; padding:12px 0 8px; margin:0; font-size:1.3em; }
 h1 small { color:#888; font-weight:normal; font-size:0.6em; margin-left:8px; }
 .grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; padding:10px; }
 @media (max-width:950px){ .grid { grid-template-columns:1fr; } }
 .cam { background:#242424; border-radius:10px; overflow:hidden; }
 .cam h2 { margin:0; padding:8px 12px; font-size:1em; background:#2e2e2e; display:flex; }
 .cam img { width:100%; display:block; background:#000; min-height:200px; }
 .bar { display:flex; gap:6px; align-items:center; padding:8px 10px; flex-wrap:wrap; font-size:0.85em; }
 select,button { background:#3a3a3a; color:#eee; border:1px solid #555; border-radius:6px; padding:5px 9px; font-size:0.9em; }
 button { cursor:pointer; } button:hover { background:#4a4a4a; }
 button.primary { background:#2d6a4f; border-color:#2d6a4f; }
 .stat { color:#9ad29a; margin-left:auto; }
 .train { border-top:1px solid #3a3a3a; }
 .toggle-on { background:#8a5a2d !important; }
 .footer { text-align:center; color:#888; font-size:0.8em; padding:12px; }
 .footer a { color:#7ab8ff; }
</style>
</head>
<body>
<h1>&#128029; Apiary Eyes <small>v{{version}}</small></h1>
<div class="grid">
 {% for n, hive in cams %}
 <div class="cam" id="cam{{n}}">
  <h2>Camera {{n}} &mdash; {{hive}} <span class="stat" id="stat{{n}}">...</span></h2>
  <img src="/proxy/{{n}}/stream" onerror="this.alt='OFFLINE'">
  <div class="bar">
   <select id="res{{n}}">
    <option value="640x480">640&times;480</option>
    <option value="1280x960" selected>1280&times;960</option>
    <option value="1920x1440">1920&times;1440</option>
    <option value="2328x1748">2328&times;1748 (max)</option>
   </select>
   <select id="fps{{n}}">
    <option value="5">5 fps</option><option value="10">10 fps</option>
    <option value="15" selected>15 fps</option><option value="25">25 fps</option>
   </select>
   <button class="primary" onclick="applyCfg({{n}})">Apply</button>
   <a href="/proxy/{{n}}/snapshot" target="_blank" style="color:#7ab8ff;font-size:0.9em">snapshot</a>
  </div>
  <div class="bar train">
   <button onclick="capture({{n}})">&#128247; Capture</button>
   <button id="auto{{n}}" onclick="toggleAuto({{n}})">Auto-capture: OFF</button>
   <span class="stat"><span id="count{{n}}">0</span> training images</span>
  </div>
 </div>
 {% endfor %}
</div>
<div class="footer">
 Training images saved on the Pi &middot; <a href="/training.tar.gz">download all (.tar.gz)</a>
 &middot; <a href="https://github.com/winreboot/apiary-eyes">apiary-eyes on GitHub</a>
</div>
<script>
const timers = {};
async function refresh(n){
 try{
  const s = await (await fetch(`/proxy/${n}/status`)).json();
  document.getElementById(`stat${n}`).textContent = `${s.width}\u00d7${s.height} @ ${s.fps}fps`;
  document.getElementById(`count${n}`).textContent = s.training_images;
 }catch(e){ document.getElementById(`stat${n}`).textContent = 'OFFLINE'; }
}
async function applyCfg(n){
 const [w,h] = document.getElementById(`res${n}`).value.split('x');
 const fps = document.getElementById(`fps${n}`).value;
 await fetch(`/proxy/${n}/config`, {method:'POST', headers:{'Content-Type':'application/json'},
   body: JSON.stringify({width:+w, height:+h, fps:+fps})});
 setTimeout(()=>{ refresh(n);
   const img = document.querySelector(`#cam${n} img`);
   img.src = `/proxy/${n}/stream?t=` + Date.now(); }, 2000);
}
async function capture(n){
 const r = await (await fetch(`/proxy/${n}/capture`, {method:'POST'})).json();
 document.getElementById(`count${n}`).textContent = r.total;
}
function toggleAuto(n){
 const btn = document.getElementById(`auto${n}`);
 if(timers[n]){ clearInterval(timers[n]); timers[n]=null;
   btn.textContent='Auto-capture: OFF'; btn.classList.remove('toggle-on'); }
 else { timers[n]=setInterval(()=>capture(n), 30000); capture(n);
   btn.textContent='Auto-capture: ON (30s)'; btn.classList.add('toggle-on'); }
}
refresh(0); refresh(1); setInterval(()=>{refresh(0);refresh(1);}, 10000);
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE, version=VERSION,
                                  cams=[(n, HIVES[n]) for n in sorted(CAMS)])


@app.route("/proxy/<int:n>/stream")
def proxy_stream(n):
    port = CAMS[n]
    def gen():
        r = urllib.request.urlopen(f"http://127.0.0.1:{port}/stream")
        while True:
            chunk = r.read(16384)
            if not chunk:
                break
            yield chunk
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/proxy/<int:n>/snapshot")
def proxy_snapshot(n):
    with urllib.request.urlopen(f"http://127.0.0.1:{CAMS[n]}/snapshot", timeout=10) as r:
        return Response(r.read(), mimetype="image/jpeg")


@app.route("/proxy/<int:n>/<path:ep>", methods=["GET", "POST"])
def proxy(n, ep):
    url = f"http://127.0.0.1:{CAMS[n]}/{ep}"
    if request.method == "POST":
        req = urllib.request.Request(url, data=request.get_data() or b"{}",
                                     headers={"Content-Type": "application/json"}, method="POST")
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return Response(r.read(), mimetype="application/json")
    except Exception as e:
        return jsonify(error=str(e)), 502


@app.route("/training.tar.gz")
def download_training():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(TRAIN_ROOT, arcname="training")
    buf.seek(0)
    return Response(buf.read(), mimetype="application/gzip",
                    headers={"Content-Disposition": "attachment; filename=apiary-eyes-training.tar.gz"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
