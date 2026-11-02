"""
ROBODİ - AI Agent Modülü
Online: Claude API | Offline: Llama 3.2 3B (NPU)
"""
import logging
import time
from collections import deque
from core.config import (
    CLAUDE_API_KEY, CLAUDE_MODEL, LLAMA_MODEL_PATH,
    USE_OFFLINE_FALLBACK, CONVERSATION_HISTORY_SIZE, SYSTEM_PROMPT
)

logger = logging.getLogger(__name__)


class AIAgent:
    def __init__(self):
        self.conversation_history = deque(maxlen=CONVERSATION_HISTORY_SIZE)
        self.current_user = None
        self.claude_client = None
        self.llama_model = None
        self._init_claude()
        if USE_OFFLINE_FALLBACK:
            self._init_llama()

    def _init_claude(self):
        """Claude API istemcisini başlat"""
        if not CLAUDE_API_KEY:
            logger.warning("ANTHROPIC_API_KEY bulunamadı, Claude devre dışı")
            return
        try:
            import anthropic
            self.claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
            logger.info("Claude API hazır")
        except ImportError:
            logger.error("anthropic paketi bulunamadı: pip install anthropic")

    def _init_llama(self):
        """Llama modeli yükle (NPU için llama-cpp-python)"""
        if not LLAMA_MODEL_PATH.exists():
            logger.warning(f"Llama model bulunamadı: {LLAMA_MODEL_PATH}")
            return
        try:
            from llama_cpp import Llama
            logger.info("Llama modeli yükleniyor...")
            self.llama_model = Llama(
                model_path=str(LLAMA_MODEL_PATH),
                n_ctx=2048,
                n_threads=4,
                verbose=False
            )
            logger.info("Llama hazır (offline)")
        except ImportError:
            logger.warning("llama-cpp-python bulunamadı")
        except Exception as e:
            logger.error(f"Llama yükleme hatası: {e}")

    def set_user(self, username: str, user_info: dict):
        """Aktif kullanıcıyı ayarla"""
        self.current_user = username
        self.conversation_history.clear()
        logger.info(f"Kullanıcı değişti: {username}")

    def _build_system_prompt(self) -> str:
        """Kullanıcıya özel sistem promptu"""
        prompt = SYSTEM_PROMPT
        if self.current_user:
            prompt += f"\nŞu anda konuştuğun kişi: {self.current_user}"
        return prompt

    def _build_messages(self, user_text: str) -> list:
        """API için mesaj listesi oluştur"""
        messages = list(self.conversation_history)
        messages.append({"role": "user", "content": user_text})
        return messages

    def chat_claude(self, user_text: str) -> str:
        """Claude API ile sohbet"""
        try:
            messages = self._build_messages(user_text)
            response = self.claude_client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=500,
                system=self._build_system_prompt(),
                messages=messages
            )
            answer = response.content[0].text
            # Konuşma geçmişine ekle
            self.conversation_history.append({"role": "user", "content": user_text})
            self.conversation_history.append({"role": "assistant", "content": answer})
            return answer
        except Exception as e:
            logger.error(f"Claude API hatası: {e}")
            if USE_OFFLINE_FALLBACK and self.llama_model:
                logger.info("Offline modaya geçiliyor...")
                return self.chat_llama(user_text)
            return "Üzgünüm, şu an bağlantı sorunum var."

    def chat_llama(self, user_text: str) -> str:
        """Offline Llama ile sohbet"""
        if not self.llama_model:
            return "Offline model hazır değil."
        try:
            prompt = f"[INST] {self._build_system_prompt()}\n\n{user_text} [/INST]"
            response = self.llama_model(
                prompt,
                max_tokens=300,
                temperature=0.7,
                stop=["</s>", "[INST]"]
            )
            answer = response["choices"][0]["text"].strip()
            self.conversation_history.append({"role": "user", "content": user_text})
            self.conversation_history.append({"role": "assistant", "content": answer})
            return answer
        except Exception as e:
            logger.error(f"Llama hatası: {e}")
            return "Bir hata oluştu."

    def chat(self, user_text: str) -> str:
        """Ana sohbet fonksiyonu - online/offline otomatik seçim"""
        if self.claude_client:
            return self.chat_claude(user_text)
        elif self.llama_model:
            return self.chat_llama(user_text)
        else:
            return "Hem internet hem offline model hazır değil."

    def get_joke(self) -> str:
        """Günlük şaka al"""
        return self.chat("Bana kısa ve komik bir şaka yap. Tek cümle olsun.")

    def get_morning_greeting(self, email_summary: str = "") -> str:
        """Sabah selamlama mesajı"""
        prompt = "Bana kısa bir günaydın mesajı söyle."
        if email_summary:
            prompt += f" Bugünkü mail özetim: {email_summary}"
        return self.chat(prompt)

    def clear_history(self):
        """Konuşma geçmişini temizle"""
        self.conversation_history.clear()
