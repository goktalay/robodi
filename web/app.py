"""
ROBODİ Web Arayüzü - Flask tabanlı kontrol paneli
Gerçek zamanlı kamera akışı, servo kontrolü, log görüntüleme
"""
import asyncio
import logging
import threading
from flask import Flask, render_template, jsonify, request, Response
import yaml

logger = logging.getLogger("robodi.web")

app = Flask(__name__)
_robot = None   # Global robot instance


def set_robot(robot):
    global _robot
    _robot = robot


# ── Sayfa Routes ──────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/logs")
def logs():
    return render_template("logs.html")


@app.route("/settings")
def settings():
    return render_template("settings.html")


# ── API Routes ────────────────────────────────────────────────────

@app.route("/api/status")
def api_status():
    state = _robot.state.current.name if _robot else "OFFLINE"
    return jsonify({
        "state":   state,
        "running": _robot.running if _robot else False,
        "servos":  _robot.servos._positions if _robot else {},
    })


@app.route("/api/servo", methods=["POST"])
def api_servo():
    data  = request.json
    name  = data.get("servo")
    angle = float(data.get("angle", 0))
    if _robot and name:
        asyncio.run_coroutine_threadsafe(
            _robot.servos.move_to(name, angle),
            _robot._loop
        )
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Robot offline"}), 503


@app.route("/api/say", methods=["POST"])
def api_say():
    text = request.json.get("text", "")
    if _robot and text:
        asyncio.run_coroutine_threadsafe(
            _robot.speaker.say(text),
            _robot._loop
        )
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 400


@app.route("/api/expression", methods=["POST"])
def api_expression():
    expr = request.json.get("expression", "idle")
    if _robot:
        _robot.esp32.set_expression(expr)
        _robot.display.show_face(expr)
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 503


@app.route("/api/snapshot")
async def api_snapshot():
    if _robot:
        path = await _robot.camera.snapshot()
        if path:
            with open(path, "rb") as f:
                return Response(f.read(), mimetype="image/jpeg")
    return jsonify({"error": "Kamera yok"}), 404


@app.route("/api/logs")
def api_logs():
    """Son 100 log satırını döndür."""
    try:
        with open("logs/robodi.log") as f:
            lines = f.readlines()[-100:]
        return jsonify({"lines": lines})
    except FileNotFoundError:
        return jsonify({"lines": []})


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    cfg_path = "config/settings.yaml"
    if request.method == "GET":
        with open(cfg_path) as f:
            return jsonify(yaml.safe_load(f))
    else:
        new_cfg = request.json
        with open(cfg_path, "w") as f:
            yaml.dump(new_cfg, f, allow_unicode=True)
        return jsonify({"ok": True})


def run_web(host="0.0.0.0", port=8080):
    app.run(host=host, port=port, debug=False, threaded=True)
