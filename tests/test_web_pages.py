"""
Web paneli sayfaları, loglar, ayarlar ve durum uç noktası testleri.
Donanım gerekmez. Çalıştırma: python -m pytest tests/
"""
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from web import app as web_app

PASSWORD = "test-sifre"
REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ROBODI_ADMIN_PASSWORD", PASSWORD)
    web_app.app.config["TESTING"] = True
    web_app.set_robot(None)
    c = web_app.app.test_client()
    c.post("/login", data={"password": PASSWORD})
    yield c
    web_app.set_robot(None)


@pytest.fixture
def config_copy(tmp_path):
    path = tmp_path / "settings.yaml"
    shutil.copy(REPO / "config" / "settings.yaml", path)
    web_app.set_robot(SimpleNamespace(config_path=str(path)))
    return path


# ── Sayfalar ─────────────────────────────────────────────────────

@pytest.mark.parametrize("path", ["/", "/users", "/logs", "/settings"])
def test_sayfalar_acilir_ve_ortak_duzeni_kullanir(client, path):
    r = client.get(path)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'class="sidebar"' in html          # base.html düzeni
    assert 'href="/users"' in html and 'href="/logs"' in html and 'href="/settings"' in html


def test_sayfalar_girissiz_acilmaz(monkeypatch):
    monkeypatch.setenv("ROBODI_ADMIN_PASSWORD", PASSWORD)
    c = web_app.app.test_client()
    for path in ("/logs", "/settings"):
        assert c.get(path).status_code == 302
    assert c.get("/api/settings").status_code == 401
    assert c.get("/api/logs").status_code == 401


# ── Loglar ───────────────────────────────────────────────────────

def test_loglar_son_n_satir_ve_renk_kodu_temizligi(client, tmp_path, monkeypatch):
    log = tmp_path / "robodi.log"
    satirlar = [f"satır {i} çğüşöı" for i in range(10)] + ["\x1b[32mHEAD /\x1b[0m 302"]
    log.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    monkeypatch.setattr(web_app, "LOG_FILE", str(log))

    d = client.get("/api/logs?lines=3").get_json()
    assert d["lines"] == ["satır 8 çğüşöı", "satır 9 çğüşöı", "HEAD / 302"]


def test_loglar_dosya_yoksa_bos(client, tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "LOG_FILE", str(tmp_path / "yok.log"))
    assert client.get("/api/logs").get_json() == {"lines": []}


def test_loglar_gecersiz_sayi(client, tmp_path, monkeypatch):
    log = tmp_path / "robodi.log"
    log.write_text("a\nb\n", encoding="utf-8")
    monkeypatch.setattr(web_app, "LOG_FILE", str(log))
    assert client.get("/api/logs?lines=abc").get_json()["lines"] == ["a", "b"]


# ── Ayarlar ──────────────────────────────────────────────────────

def test_ayarlar_metin_olarak_okunur(client, config_copy):
    d = client.get("/api/settings").get_json()
    assert d["path"] == str(config_copy)
    assert "# ─── LLM / AI" in d["text"]           # yorumlar korunuyor


def test_ayarlar_kaydedilir_yorumlar_korunur_yedek_alinir(client, config_copy):
    eski = config_copy.read_text(encoding="utf-8")
    yeni = eski.replace("max_turns: 5", "max_turns: 7")
    r = client.post("/api/settings", json={"text": yeni})
    assert r.status_code == 200 and r.get_json()["ok"]
    assert config_copy.read_text(encoding="utf-8") == yeni
    assert Path(str(config_copy) + ".bak").read_text(encoding="utf-8") == eski
    assert yaml.safe_load(yeni)["conversation"]["max_turns"] == 7


@pytest.mark.parametrize("metin, hata", [
    ("", "Boş"),
    ("ai: [kapanmayan", "YAML hatası"),
    ("- sadece\n- liste\n", "sözlük"),
    ("ai:\n  provider: claude\n", "Eksik bölüm"),
])
def test_ayarlar_gecersizse_dosyaya_dokunulmaz(client, config_copy, metin, hata):
    eski = config_copy.read_text(encoding="utf-8")
    r = client.post("/api/settings", json={"text": metin})
    assert r.status_code == 400
    assert hata in r.get_json()["error"]
    assert config_copy.read_text(encoding="utf-8") == eski
    assert not Path(str(config_copy) + ".bak").exists()


# ── Durum ────────────────────────────────────────────────────────

def test_durum_robot_yokken(client):
    d = client.get("/api/status").get_json()
    assert d["state"] == "OFFLINE" and d["running"] is False
    assert "cpu_temp" in d


def test_durum_robot_ozetini_dondurur(client):
    ozet = {"state": "LISTENING", "running": True, "current_user": "Muhammed",
            "conversation": True, "camera": "IMX500", "ai": "Claude (claude-opus-5-5)",
            "servos": {"head_pan": 10.0}}
    web_app.set_robot(SimpleNamespace(status=lambda: dict(ozet)))
    d = client.get("/api/status").get_json()
    for k, v in ozet.items():
        assert d[k] == v
