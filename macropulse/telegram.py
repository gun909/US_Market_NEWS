from __future__ import annotations

import json
from urllib.request import Request, urlopen


def send_telegram(token: str, chat_id: str, text: str) -> None:
    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = Request(endpoint, data=payload, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=15) as response:
        if response.status >= 300:
            raise RuntimeError(f"Telegram returned HTTP {response.status}")

