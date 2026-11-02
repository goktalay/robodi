"""
ROBODİ - Gmail okuyucu (sabah özeti için)

İlk yetkilendirme (tarayıcı gerekir, bir kez):
    python -m src.services.gmail
Robot çalışırken etkileşimli giriş yapılmaz; token yoksa Gmail kapalı kalır.
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("robodi.gmail")

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailReader:
    def __init__(self, config: dict):
        self.credentials_file = Path(config.get("credentials_file", "data/gmail_credentials.json"))
        self.token_file       = Path(config.get("token_file", "data/gmail_token.json"))
        self.service = None
        if config.get("enabled", True):
            self._init_service()

    def _init_service(self):
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError:
            logger.warning("Google API paketleri kurulu değil, Gmail kapalı.")
            return

        if not self.token_file.exists():
            logger.warning("Gmail token yok. Yetkilendirmek için: python -m src.services.gmail")
            return
        try:
            creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    self.token_file.write_text(creds.to_json())
                else:
                    logger.warning("Gmail token geçersiz. Yeniden: python -m src.services.gmail")
                    return
            self.service = build("gmail", "v1", credentials=creds)
            logger.info("Gmail API hazır.")
        except Exception as e:
            logger.error(f"Gmail başlatma hatası: {e}")

    def is_ready(self) -> bool:
        return self.service is not None

    def get_unread_emails(self, hours: int = 12, max_results: int = 10) -> list:
        if not self.service:
            return []
        try:
            since = int((datetime.now() - timedelta(hours=hours)).timestamp())
            result = self.service.users().messages().list(
                userId="me", q=f"is:unread after:{since}", maxResults=max_results
            ).execute()
            emails = []
            for msg in result.get("messages", []):
                meta = self.service.users().messages().get(
                    userId="me", id=msg["id"], format="metadata",
                    metadataHeaders=["Subject", "From"],
                ).execute()
                headers = {h["name"]: h["value"] for h in meta["payload"]["headers"]}
                emails.append({
                    "id": msg["id"],
                    "subject": headers.get("Subject", "(Konu yok)"),
                    "sender": headers.get("From", "(Bilinmeyen)"),
                    "snippet": meta.get("snippet", ""),
                })
            logger.info(f"{len(emails)} okunmamış mail bulundu.")
            return emails
        except Exception as e:
            logger.error(f"Mail alma hatası: {e}")
            return []

    def get_summary_text(self, hours: int = 12) -> str:
        """Bloklayıcı; executor'da çağırın."""
        emails = self.get_unread_emails(hours=hours)
        if not emails:
            return "Okunmamış mailin yok."
        lines = [f"{len(emails)} okunmamış mailin var:"]
        for i, mail in enumerate(emails[:5], 1):
            sender = mail["sender"].split("<")[0].strip().strip('"')
            lines.append(f"{i}. {sender}: {mail['subject']}")
        if len(emails) > 5:
            lines.append(f"...ve {len(emails) - 5} mail daha.")
        return "\n".join(lines)


def authorize(config: dict):
    """Tarayıcıyla tek seferlik OAuth yetkilendirmesi."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds_file = Path(config.get("credentials_file", "data/gmail_credentials.json"))
    token_file = Path(config.get("token_file", "data/gmail_token.json"))
    if not creds_file.exists():
        raise SystemExit(f"{creds_file} bulunamadı (Google Cloud Console'dan indirin).")
    flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
    creds = flow.run_local_server(port=0, open_browser=False)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json())
    print(f"Gmail token kaydedildi: {token_file}")


if __name__ == "__main__":
    import yaml
    with open("config/settings.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    authorize(cfg.get("gmail", {}))
