"""
Web paneli giriş ve kullanıcı yönetimi testleri.
Donanım gerekmez: FaceIdentifier simülasyon modunda, kamera sahte.
Çalıştırma: python -m pytest tests/
"""
import asyncio
import threading
from types import SimpleNamespace

import pytest

from src.vision.face_id import FaceIdentifier
from web import app as web_app

PASSWORD = "test-sifre"


class FakeCamera:
    """Simülasyon kamerası; istenirse sahte kare döndürür."""
    def __init__(self, frame=None):
        self.frame = frame
        self.calls = 0

    async def get_frame(self):
        self.calls += 1
        return self.frame


@pytest.fixture
def loop():
    lp = asyncio.new_event_loop()
    t = threading.Thread(target=lp.run_forever, daemon=True)
    t.start()
    yield lp
    lp.call_soon_threadsafe(lp.stop)
    t.join(timeout=2)
    lp.close()


@pytest.fixture
def robot(tmp_path, loop):
    face_id = FaceIdentifier({
        "users_file":     str(tmp_path / "authorized_users.json"),
        "encodings_file": str(tmp_path / "face_encodings.pkl"),
    })
    return SimpleNamespace(face_id=face_id, camera=FakeCamera(), _loop=loop)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ROBODI_ADMIN_PASSWORD", PASSWORD)
    monkeypatch.setattr(web_app, "CAPTURE_INTERVAL", 0)
    web_app.app.config["TESTING"] = True
    web_app.set_robot(None)
    yield web_app.app.test_client()
    web_app.set_robot(None)


def login(client, password=PASSWORD):
    return client.post("/login", data={"password": password})


# ── Giriş ─────────────────────────────────────────────────────────

def test_korunan_sayfa_girise_yonlendirir(client):
    r = client.get("/users")
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_api_girissiz_401(client):
    r = client.get("/api/users")
    assert r.status_code == 401
    assert client.get("/api/status").status_code == 401


def test_login_sayfasi_acik(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert "Yönetici Şifresi" in r.get_data(as_text=True)


def test_hatali_sifre(client):
    r = login(client, "yanlis")
    assert r.status_code == 401
    assert "Şifre hatalı" in r.get_data(as_text=True)
    assert client.get("/api/users").status_code == 401


def test_sifre_tanimsizsa_giris_kapali(client, monkeypatch):
    monkeypatch.delenv("ROBODI_ADMIN_PASSWORD")
    r = login(client, "")
    assert r.status_code == 401
    assert client.get("/api/status").status_code == 401


def test_dogru_sifre_ve_cikis(client):
    r = login(client)
    assert r.status_code == 302
    assert client.get("/api/status").status_code == 200
    client.get("/logout")
    assert client.get("/api/status").status_code == 401


def test_next_sadece_site_ici(client):
    r = client.post("/login?next=//evil.example", data={"password": PASSWORD})
    assert r.headers["Location"] == "/"
    client.get("/logout")
    r = client.post("/login?next=/users", data={"password": PASSWORD})
    assert r.headers["Location"] == "/users"


# ── Kullanıcılar ─────────────────────────────────────────────────

def test_robot_yokken_cevrimdisi(client):
    login(client)
    r = client.get("/users")
    assert r.status_code == 200
    assert "Robot çevrimdışı" in r.get_data(as_text=True)
    r = client.get("/api/users")
    assert r.status_code == 503
    assert client.post("/api/users/add", json={"username": "ali", "name": "Ali"}).status_code == 503


def test_kullanicilari_listele(client, robot):
    web_app.set_robot(robot)
    login(client)
    r = client.get("/api/users")
    assert r.status_code == 200
    assert r.get_json()["admin"]["role"] == "admin"
    assert "Robot çevrimdışı" not in client.get("/users").get_data(as_text=True)


def test_admin_silinemez(client, robot):
    web_app.set_robot(robot)
    login(client)
    r = client.delete("/api/users/admin")
    assert r.status_code == 403
    assert "admin" in robot.face_id.authorized_users


def test_kullanici_sil(client, robot):
    robot.face_id.authorized_users["ali"] = {"name": "Ali", "role": "user"}
    web_app.set_robot(robot)
    login(client)
    r = client.delete("/api/users/ali")
    assert r.get_json()["success"] is True
    assert "ali" not in client.get("/api/users").get_json()
    assert client.delete("/api/users/ali").status_code == 404


def test_ekle_gecersiz_girdi(client, robot):
    web_app.set_robot(robot)
    login(client)
    assert client.post("/api/users/add", json={"username": "A B", "name": "x"}).status_code == 400
    assert client.post("/api/users/add", json={"username": "ali"}).status_code == 400
    assert client.post("/api/users/add", json={"username": "admin", "name": "x"}).status_code == 409


def test_ekle_kare_yoksa_hata(client, robot):
    robot.face_id.available = True            # face_recognition kurulu gibi davran
    web_app.set_robot(robot)
    login(client)
    r = client.post("/api/users/add", json={"username": "ali", "name": "Ali"})
    assert r.status_code == 503
    assert robot.camera.calls == web_app.CAPTURE_FRAMES
    assert "ali" not in robot.face_id.authorized_users


def test_ekle_kameradan_karelerle(client, robot, monkeypatch):
    robot.camera.frame = object()             # sahte kare
    robot.face_id.available = True
    captured = {}

    def fake_add_user(username, info, frames):
        captured.update(username=username, info=info, frames=frames)
        robot.face_id.authorized_users[username] = info
        return True

    monkeypatch.setattr(robot.face_id, "add_user", fake_add_user)
    web_app.set_robot(robot)
    login(client)
    r = client.post("/api/users/add",
                    json={"username": "ali", "name": "Ali", "role": "user"})
    assert r.get_json() == {"success": True}
    assert captured["username"] == "ali"
    assert len(captured["frames"]) == web_app.CAPTURE_FRAMES
    assert captured["info"]["greeting"] == "Merhaba Ali!"
    assert "ali" in client.get("/api/users").get_json()
