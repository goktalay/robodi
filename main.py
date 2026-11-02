#!/usr/bin/env python3
"""
ROBODİ - Ana Giriş Noktası
Kullanım: python main.py [--config config/settings.yaml] [--web-only]
"""
import asyncio
import argparse
import logging
import signal
import sys
import threading
from pathlib import Path

# ── Logging ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/robodi.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("robodi")


def parse_args():
    p = argparse.ArgumentParser(description="ROBODİ Robot Kontrolcüsü")
    p.add_argument("--config",   default="config/settings.yaml", help="Config dosyası")
    p.add_argument("--web-only", action="store_true", help="Sadece web arayüzü")
    p.add_argument("--no-web",   action="store_true", help="Web arayüzü olmadan")
    p.add_argument("--debug",    action="store_true", help="Debug modu")
    return p.parse_args()


async def main():
    args = parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Log klasörü oluştur
    Path("logs").mkdir(exist_ok=True)

    logger.info("=" * 50)
    logger.info("  ROBODİ v1.0.0 başlatılıyor")
    logger.info("=" * 50)

    from src.core.robot import Robodi
    from web.app import run_web, set_robot

    robot = Robodi(config_path=args.config)
    robot._loop = asyncio.get_event_loop()

    # Web arayüzü ayrı thread'de
    if not args.no_web:
        set_robot(robot)
        import yaml
        with open(args.config) as f:
            cfg = yaml.safe_load(f)
        web_cfg = cfg.get("robodi", {}).get("web", {})
        web_thread = threading.Thread(
            target=run_web,
            kwargs={"host": web_cfg.get("host","0.0.0.0"),
                    "port": web_cfg.get("port", 8080)},
            daemon=True
        )
        web_thread.start()
        logger.info(f"Web arayüzü: http://localhost:{web_cfg.get('port',8080)}")

    if args.web_only:
        logger.info("Sadece web modu, robot başlatılmıyor.")
        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        return

    # Graceful shutdown
    def _shutdown(sig, frame):
        logger.info(f"Sinyal alındı ({sig}), kapatılıyor...")
        asyncio.create_task(robot.stop())

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        await robot.start()
    except KeyboardInterrupt:
        logger.info("Klavye kesintisi.")
    finally:
        await robot.stop()
        logger.info("ROBODİ kapatıldı.")


if __name__ == "__main__":
    asyncio.run(main())
