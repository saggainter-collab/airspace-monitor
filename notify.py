"""Telegram notifications."""
import html
import os
import time
import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
DRY_RUN = os.environ.get("DRY_RUN") == "1" or not (TOKEN and CHAT_ID)

MAX_LEN = 3900


def esc(s):
    return html.escape(str(s), quote=False)


def send(text):
    """Send an HTML-formatted message, split if too long."""
    chunks, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > MAX_LEN:
            chunks.append(cur)
            cur = ""
        cur += line + "\n"
    if cur.strip():
        chunks.append(cur)

    for chunk in chunks:
        if DRY_RUN:
            print("---- TELEGRAM (dry run) ----\n" + chunk)
            continue
        for attempt in range(3):
            try:
                r = requests.post(
                    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                    json={
                        "chat_id": CHAT_ID,
                        "text": chunk,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                    timeout=20,
                )
                if r.status_code == 200:
                    break
                if r.status_code == 429:
                    time.sleep(int(r.json().get("parameters", {}).get("retry_after", 5)))
                    continue
                print("Telegram error:", r.status_code, r.text[:300])
                break
            except requests.RequestException as e:
                print("Telegram exception:", e)
                time.sleep(3)
        time.sleep(1)
