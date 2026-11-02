"""
ROBODİ - Gmail Entegrasyonu
Sabah mail özetleri için
"""
import logging
import base64
import email
from datetime import datetime, timedelta
from pathlib import Path
from core.config import GMAIL_CREDENTIALS_FILE, GMAIL_TOKEN_FILE, GMAIL_SCOPES

logger = logging.getLogger(__name__)


class GmailReader:
    def __init__(self):
        self.service = None
        self._init_service()

    def _init_service(self):
        """Gmail API servisini başlat"""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build

            creds = None
            token_path = Path(GMAIL_TOKEN_FILE)
            creds_path = Path(GMAIL_CREDENTIALS_FILE)

            if token_path.exists():
                creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not creds_path.exists():
                        logger.error("Gmail credentials.json bulunamadı!")
                        return
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(creds_path), GMAIL_SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                with open(token_path, "w") as token:
                    token.write(creds.to_json())

            self.service = build("gmail", "v1", credentials=creds)
            logger.info("Gmail API hazır")
        except ImportError:
            logger.error("google-api-python-client paketi bulunamadı")
        except Exception as e:
            logger.error(f"Gmail başlatma hatası: {e}")

    def get_unread_emails(self, hours: int = 12, max_results: int = 10) -> list:
        """Son N saatteki okunmamış mailleri al"""
        if not self.service:
            return []

        try:
            since = datetime.now() - timedelta(hours=hours)
            query = f"is:unread after:{since.strftime('%Y/%m/%d')}"

            results = self.service.users().messages().list(
                userId="me",
                q=query,
                maxResults=max_results
            ).execute()

            messages = results.get("messages", [])
            emails = []

            for msg in messages:
                email_data = self._parse_email(msg["id"])
                if email_data:
                    emails.append(email_data)

            logger.info(f"{len(emails)} okunmamış mail bulundu")
            return emails
        except Exception as e:
            logger.error(f"Mail alma hatası: {e}")
            return []

    def _parse_email(self, message_id: str) -> dict:
        """Mail detaylarını parse et"""
        try:
            msg = self.service.users().messages().get(
                userId="me",
                id=message_id,
                format="full"
            ).execute()

            headers = msg["payload"]["headers"]
            header_dict = {h["name"]: h["value"] for h in headers}

            subject = header_dict.get("Subject", "(Konu yok)")
            sender = header_dict.get("From", "(Bilinmeyen)")
            date = header_dict.get("Date", "")

            # Gövdeyi al
            body = self._extract_body(msg["payload"])

            return {
                "id": message_id,
                "subject": subject,
                "sender": sender,
                "date": date,
                "snippet": msg.get("snippet", ""),
                "body": body[:500] if body else ""  # İlk 500 karakter
            }
        except Exception as e:
            logger.error(f"Mail parse hatası {message_id}: {e}")
            return None

    def _extract_body(self, payload) -> str:
        """Mail gövdesini çıkar"""
        body = ""

        if "body" in payload and payload["body"].get("data"):
            data = payload["body"]["data"]
            body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        elif "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain":
                    if part["body"].get("data"):
                        data = part["body"]["data"]
                        body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                        break

        return body

    def get_summary_text(self, hours: int = 12) -> str:
        """Özet metin oluştur"""
        emails = self.get_unread_emails(hours=hours)

        if not emails:
            return "Okunmamış mailin yok."

        summary = f"{len(emails)} okunmamış mailin var:\n"
        for i, mail in enumerate(emails[:5], 1):
            # Gönderen adını temizle
            sender = mail["sender"].split("<")[0].strip().strip('"')
            summary += f"{i}. {sender}: {mail['subject']}\n"

        if len(emails) > 5:
            summary += f"...ve {len(emails) - 5} mail daha."

        return summary

    def is_ready(self) -> bool:
        return self.service is not None
