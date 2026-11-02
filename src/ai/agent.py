"""
ROBODİ - AI Sohbet Ajanı
Online: Claude API | Offline / yedek: Ollama (yerel Llama)
"""
import logging
import os
from collections import deque
from typing import Optional

logger = logging.getLogger("robodi.ai")

DEFAULT_SYSTEM_PROMPT = (
    "Sen ROBODİ'sin, Türkçe konuşan yardımsever bir masa robotusun. "
    "Kısa, net ve samimi yanıtlar ver; yanıtların sesli okunacak."
)


class AIAgent:
    """Çok turlu sohbet; Claude öncelikli, Ollama yedek."""

    def __init__(self, config: dict):
        self.provider      = config.get("provider", "claude")
        self.system_prompt = config.get("system_prompt", DEFAULT_SYSTEM_PROMPT).strip()
        self.max_tokens    = config.get("max_tokens", 1024)
        self.history       = deque(maxlen=config.get("history_size", 10) * 2)
        self.current_user: Optional[str] = None

        claude_cfg = config.get("claude", {})
        self.claude_model  = claude_cfg.get("model", "claude-opus-5-5")
        self.claude_effort = claude_cfg.get("effort", "low")

        ollama_cfg = config.get("ollama", {})
        self.ollama_url   = ollama_cfg.get("url", "http://localhost:11434")
        self.ollama_model = ollama_cfg.get("model", config.get("model", "llama3.2:3b"))
        self.temperature  = ollama_cfg.get("temperature", config.get("temperature", 0.7))

        self._claude = None
        if self.provider == "claude":
            self._init_claude()

    def _init_claude(self):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            logger.warning("ANTHROPIC_API_KEY yok, Claude devre dışı (Ollama kullanılacak).")
            return
        try:
            import anthropic
            self._claude = anthropic.AsyncAnthropic()
            logger.info(f"Claude hazır ({self.claude_model}).")
        except ImportError:
            logger.error("anthropic paketi bulunamadı: pip install anthropic")

    # ── Kullanıcı / geçmiş ──────────────────────────────────────

    def set_user(self, username: str, user_info: dict):
        self.current_user = user_info.get("name", username)
        self.history.clear()
        logger.info(f"AI aktif kullanıcı: {self.current_user}")

    def clear_history(self):
        self.history.clear()

    def _system(self) -> str:
        prompt = self.system_prompt
        if self.current_user:
            prompt += f"\nŞu anda konuştuğun kişi: {self.current_user}"
        return prompt

    # ── Sohbet ──────────────────────────────────────────────────

    async def chat(self, text: str) -> str:
        answer = None
        if self._claude:
            answer = await self._chat_claude(text)
        if answer is None:
            answer = await self._chat_ollama(text)
        if answer is None:
            return "Şu an düşünemiyorum, biraz sonra tekrar deneyin."

        self.history.append({"role": "user", "content": text})
        self.history.append({"role": "assistant", "content": answer})
        return answer

    async def _chat_claude(self, text: str) -> Optional[str]:
        import anthropic
        try:
            response = await self._claude.beta.messages.create(
                model=self.claude_model,
                max_tokens=self.max_tokens,
                system=self._system(),
                messages=[*self.history, {"role": "user", "content": text}],
                output_config={"effort": self.claude_effort},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIConnectionError:
            logger.warning("Claude'a ulaşılamadı, Ollama'ya geçiliyor.")
            return None
        except anthropic.APIStatusError as e:
            logger.error(f"Claude API hatası ({e.status_code}): {e.message}")
            return None

        if response.stop_reason == "refusal":
            logger.warning("Claude isteği reddetti.")
            return "Bu konuda yardımcı olamıyorum."

        answer = "".join(b.text for b in response.content if b.type == "text").strip()
        return answer or None

    async def _chat_ollama(self, text: str) -> Optional[str]:
        try:
            import httpx
            messages = [{"role": "system", "content": self._system()},
                        *self.history,
                        {"role": "user", "content": text}]
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": self.ollama_model,
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": self.temperature,
                                    "num_predict": self.max_tokens},
                    },
                )
                resp.raise_for_status()
                return resp.json().get("message", {}).get("content", "").strip() or None
        except Exception as e:
            logger.error(f"Ollama hatası: {e}")
            return None

    # ── Hazır istekler ──────────────────────────────────────────

    async def get_joke(self) -> str:
        return await self.chat("Bana kısa ve komik bir şaka yap. Tek cümle olsun.")

    async def get_morning_greeting(self, email_summary: str = "") -> str:
        prompt = "Bana kısa bir günaydın mesajı söyle."
        if email_summary:
            prompt += f" Bugünkü mail özetim: {email_summary}"
        return await self.chat(prompt)
