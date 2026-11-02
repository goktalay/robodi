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
    if _robot is None:
        data = {"state": "OFFLINE", "running": False, "servos": {}}
    elif hasattr(_robot, "status"):
        data = _robot.status()
    else:   # eski/sahte robot nesneleri
        data = {"state": _robot.state.current.name, "running": _robot.running,
                "servos": getattr(_robot.servos, "_positions", {})}
    data["cpu_temp"] = _cpu_temp()
    return jsonify(data)


def _cpu_temp():
    """Raspberry Pi CPU sıcaklığı (°C); okunamazsa None."""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip()) / 1000, 1)
    except (OSError, ValueError):
        return None


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


def _start_announcement(method_name: str):
    """Robotun duyuru yöntemini (şaka, sabah özeti) arka planda başlat."""
    if _robot is None or getattr(_robot, "_loop", None) is None:
        return jsonify({"ok": False, "error": "Robot çevrimdışı"}), 503
    if not _robot.can_announce():
        return jsonify({"ok": False, "error": "Robot şu an meşgul (konuşuyor veya dinliyor)"}), 409
    future = asyncio.run_coroutine_threadsafe(getattr(_robot, method_name)(), _robot._loop)
    future.add_done_callback(
        lambda f: not f.cancelled() and f.exception()
        and logger.error(f"{method_name} hatası: {f.exception()}")
    )
    return jsonify({"ok": True}), 202


@app.route("/api/joke", methods=["POST"])
def api_joke():
    return _start_announcement("tell_joke")


@app.route("/api/morning-summary", methods=["POST"])
def api_morning_summary():
    return _start_announcement("morning_summary")


@app.route("/api/snapshot")
async def api_snapshot():
    if _robot:
        path = await _robot.camera.snapshot()
        if path:
            with open(path, "rb") as f:
                return Response(f.read(), mimetype="image/jpeg")
    return jsonify({"error": "Kamera yok"}), 404


LOG_FILE      = "logs/robodi.log"
LOG_MAX_LINES = 1000
ANSI_RE       = re.compile(r"\x1b\[[0-9;]*m")


@app.route("/api/logs")
def api_logs():
    """Son N log satırını döndür (?lines=, varsayılan 200, en fazla 1000)."""
    try:
        n = max(1, min(int(request.args.get("lines", 200)), LOG_MAX_LINES))
    except ValueError:
        n = 200
    try:
        with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-n:]
        return jsonify({"lines": [ANSI_RE.sub("", l).rstrip("\n") for l in lines]})
    except FileNotFoundError:
        return jsonify({"lines": []})


# ── Ayarlar ───────────────────────────────────────────────────────

REQUIRED_SECTIONS = ("gpio", "audio", "vision", "display", "esp32", "web", "ai")


def _settings_path() -> str:
    return getattr(_robot, "config_path", None) or "config/settings.yaml"


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    """settings.yaml'ı metin olarak oku/yaz; yorumlar korunur, kaydetmeden önce doğrulanır."""
    path = _settings_path()
    if request.method == "GET":
        with open(path, encoding="utf-8") as f:
            return jsonify({"path": path, "text": f.read()})

    text = (request.get_json(silent=True) or {}).get("text")
    if not isinstance(text, str) or not text.strip():
        return jsonify({"ok": False, "error": "Boş ayar metni"}), 400
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return jsonify({"ok": False, "error": f"YAML hatası: {e}"}), 400
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "Ayar dosyası bir sözlük (anahtar: değer) olmalı"}), 400
    missing = [k for k in REQUIRED_SECTIONS if not isinstance(data.get(k), dict)]
    if missing:
        return jsonify({"ok": False, "error": "Eksik bölüm(ler): " + ", ".join(missing)}), 400

    try:
        with open(path, encoding="utf-8") as f:
            old = f.read()
        with open(path + ".bak", "w", encoding="utf-8") as f:
            f.write(old)
    except FileNotFoundError:
        pass
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    logger.info("Ayarlar web panelinden güncellendi (yedek: %s.bak).", path)
    return jsonify({"ok": True, "restart_required": True})


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
    # Her istek için erişim satırı yazılmasın; panel birkaç saniyede bir durum sorguluyor
    # ve bu satırlar robodi.log'u doldurup robot loglarını gömüyordu.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    app.run(host=host, port=port, debug=False, threaded=True)
