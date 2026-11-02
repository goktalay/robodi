"""
ROBODİ Web Arayüzü - Flask tabanlı kontrol paneli
Gerçek zamanlı kamera akışı, servo kontrolü, log görüntüleme
"""
import asyncio
import hmac
import logging
import os
import re
import secrets
import threading
import time
from flask import (Flask, render_template, jsonify, request, Response,
                   session, redirect, url_for)
import yaml

logger = logging.getLogger("robodi.web")

app = Flask(__name__)
_robot = None   # Global robot instance

# Kullanıcı eklerken kameradan alınacak kare sayısı ve aralığı
CAPTURE_FRAMES   = 5
CAPTURE_INTERVAL = 0.3
USERNAME_RE      = re.compile(r"^[a-z0-9_]{2,32}$")


def _load_secret_key(cfg_path="config/settings.yaml") -> str:
    """Oturum anahtarı: önce ROBODI_SECRET_KEY, yedek olarak web.secret_key."""
    key = os.environ.get("ROBODI_SECRET_KEY")
    if key:
        return key
    try:
        with open(cfg_path, encoding="utf-8") as f:
            key = (yaml.safe_load(f) or {}).get("web", {}).get("secret_key")
    except (OSError, yaml.YAMLError):
        key = None
    if key:
        logger.warning("ROBODI_SECRET_KEY tanımlı değil, settings.yaml'daki yedek anahtar kullanılıyor.")
        return key
    logger.warning("Oturum anahtarı bulunamadı, rastgele üretildi (yeniden başlatınca oturumlar düşer).")
    return secrets.token_hex(32)


app.secret_key = _load_secret_key()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")


def set_robot(robot):
    global _robot
    _robot = robot


# ── Giriş ─────────────────────────────────────────────────────────

PUBLIC_ENDPOINTS = {"login", "static"}


@app.before_request
def require_login():
    if request.endpoint in PUBLIC_ENDPOINTS or session.get("logged_in"):
        return None
    if request.path.startswith("/api/"):
        return jsonify({"error": "Giriş gerekli"}), 401
    return redirect(url_for("login", next=request.path))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        expected = os.environ.get("ROBODI_ADMIN_PASSWORD")
        given = request.form.get("password", "")
        if not expected:
            logger.error("ROBODI_ADMIN_PASSWORD tanımlı değil, giriş kapalı.")
            error = "Sunucuda yönetici şifresi tanımlı değil (ROBODI_ADMIN_PASSWORD)."
        elif hmac.compare_digest(given.encode(), expected.encode()):
            session.clear()
            session["logged_in"] = True
            nxt = request.args.get("next", "")
            # Sadece site içi yönlendirme (açık yönlendirmeye izin verme)
            if not nxt.startswith("/") or nxt.startswith("//"):
                nxt = url_for("index")
            return redirect(nxt)
        else:
            logger.warning(f"Hatalı giriş denemesi: {request.remote_addr}")
            error = "Şifre hatalı."
    return render_template("login.html", error=error), (401 if error else 200)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Sayfa Routes ──────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/users")
def users():
    return render_template("users.html", robot_online=_robot is not None)


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


# ── Kullanıcı yönetimi ───────────────────────────────────────────

def _face_id():
    return getattr(_robot, "face_id", None) if _robot else None


@app.route("/api/users")
def api_users():
    face_id = _face_id()
    if face_id is None:
        return jsonify({"error": "Robot çevrimdışı"}), 503
    return jsonify(face_id.authorized_users)


@app.route("/api/users/<username>", methods=["DELETE"])
def api_user_delete(username):
    face_id = _face_id()
    if face_id is None:
        return jsonify({"success": False, "error": "Robot çevrimdışı"}), 503
    if username == "admin":
        return jsonify({"success": False, "error": "Admin silinemez"}), 403
    if not face_id.remove_user(username):
        return jsonify({"success": False, "error": "Kullanıcı bulunamadı"}), 404
    return jsonify({"success": True})


def _capture_frames(count=CAPTURE_FRAMES, interval=CAPTURE_INTERVAL) -> list:
    """Robotun kamerasından kare al (asyncio döngüsüne köprü)."""
    frames = []
    for i in range(count):
        fut = asyncio.run_coroutine_threadsafe(_robot.camera.get_frame(), _robot._loop)
        try:
            frame = fut.result(timeout=5)
        except Exception as e:
            logger.error(f"Kare alınamadı: {e}")
            frame = None
        if frame is not None:
            frames.append(frame)
        if i < count - 1:
            time.sleep(interval)
    return frames


@app.route("/api/users/add", methods=["POST"])
def api_user_add():
    face_id = _face_id()
    if face_id is None or getattr(_robot, "_loop", None) is None:
        return jsonify({"success": False, "error": "Robot çevrimdışı"}), 503

    data     = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip().lower()
    name     = str(data.get("name", "")).strip()
    role     = data.get("role", "user")
    if not USERNAME_RE.match(username):
        return jsonify({"success": False,
                        "error": "Kullanıcı adı 2-32 karakter; küçük harf, rakam ve _ olmalı"}), 400
    if not name:
        return jsonify({"success": False, "error": "Görünen ad gerekli"}), 400
    if role not in ("user", "admin"):
        return jsonify({"success": False, "error": "Geçersiz rol"}), 400
    if username in face_id.authorized_users:
        return jsonify({"success": False, "error": "Bu kullanıcı zaten var"}), 409
    if not face_id.available:
        return jsonify({"success": False, "error": "Yüz tanıma kurulu değil (face_recognition)"}), 503

    frames = _capture_frames()
    if not frames:
        return jsonify({"success": False, "error": "Kameradan kare alınamadı"}), 503

    info = {
        "name":     name,
        "role":     role,
        "greeting": str(data.get("greeting", "")).strip() or f"Merhaba {name}!",
    }
    if not face_id.add_user(username, info, frames):
        return jsonify({"success": False, "error": "Karelerde yüz bulunamadı, tekrar deneyin"}), 422
    return jsonify({"success": True})


def run_web(host="0.0.0.0", port=8080):
    app.run(host=host, port=port, debug=False, threaded=True)
