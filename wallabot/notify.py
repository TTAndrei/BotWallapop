"""Avisos por Telegram (opcional). Configura TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from html import escape

from .models import Item


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id

    @classmethod
    def from_env(cls) -> "TelegramNotifier | None":
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        return cls(token, chat_id) if token and chat_id else None

    def send_item(self, search_name: str, item: Item) -> None:
        text = (
            f"<b>{escape(search_name)}</b>\n"
            f"{escape(item.title)}\n"
            f"💶 {escape(item.price_str())}  📍 {escape(item.city or '¿?')}"
            f"{'  📦 envío' if item.shipping else ''}\n"
            f"{escape(item.url)}"
        )
        self._call("sendMessage", {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"})

    def _call(self, method: str, payload: dict) -> None:
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        data = urllib.parse.urlencode(payload).encode()
        with urllib.request.urlopen(url, data=data, timeout=15) as response:
            result = json.loads(response.read().decode())
        if not result.get("ok"):
            raise RuntimeError(f"Telegram respondió: {result}")
