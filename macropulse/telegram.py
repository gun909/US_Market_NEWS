from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def send_telegram(token: str, chat_id: str, text: str) -> None:
    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = Request(endpoint, data=payload, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=15) as response:
        if response.status >= 300:
            raise RuntimeError(f"Telegram returned HTTP {response.status}")


def fetch_telegram_updates(token: str, offset: int = 0) -> tuple[dict[str, Any], ...]:
    query = urlencode({"offset": offset, "timeout": 0, "allowed_updates": '["message"]'})
    endpoint = f"https://api.telegram.org/bot{token}/getUpdates?{query}"
    with urlopen(endpoint, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("ok"):
        raise RuntimeError("Telegram getUpdates failed")
    return tuple(payload.get("result", ()))


def split_telegram_text(text: str, limit: int = 3900) -> tuple[str, ...]:
    if len(text) <= limit:
        return (text,)
    chunks: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = block
    if current:
        chunks.append(current)
    return tuple(chunks)
