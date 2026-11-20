import json
import os
import sys

import requests
from bs4 import BeautifulSoup

# --- Edit the labels if you like ------------------------------------------
WATCHES = {
    "Watch 1": "https://www.hmtwatches.in/product_overview?id=eyJpdiI6InM4UFpOUG0rZ2VJc3kwT09aS1ZQQkE9PSIsInZhbHVlIjoiNDdrZmhhYWZVaitLM3JQUTYzZ0lyQT09IiwibWFjIjoiMjlmNTlhODQwNjM0YmY3Y2M4YzNiMjc4ODVhZWYzZDhiNDAyZTVlMzM0N2E4ZTQzOTJkMDViYzI1YzliNTJkNSIsInRhZyI6IiJ9",
    "Watch 2": "https://www.hmtwatches.in/product_overview?id=eyJpdiI6Imx4ajREbVBqdEszcmFySWs2d2RWcnc9PSIsInZhbHVlIjoiZmFrODVWMDBFMFVPbzFYa1VyZnhLUT09IiwibWFjIjoiYTQ2YzQ1MWMxYmRmNjRkZmU3YmRiMWU1Y2Y4NDk0MDhkMTQxMjIyNTk5NDNkNjg2OGEzMjM2MjViMGRkMTExNyIsInRhZyI6IiJ9",
    "Watch 3": "https://www.hmtwatches.in/product_overview?id=eyJpdiI6Iiswb1drTE5WR0d1Sm9WN1pRdDZOdUE9PSIsInZhbHVlIjoiTHZSM0lZTDkwNzF3emJLSkRXUUxqQT09IiwibWFjIjoiYjI0MGJmM2I5ZGI1ODA4YWQzZmQ0YjMwZTUxZGEzY2JhMzdiMDE1YjAyYWI0MmQxNzg5YTEwNWNjYzQ3YTM0MyIsInRhZyI6IiJ9",
}

# If any of these phrases appear on the page, the watch is treated as unavailable.
BLOCKERS = ("coming soon", "out of stock", "sold out", "currently unavailable", "notify me")
# --------------------------------------------------------------------------

HOME = "https://www.hmtwatches.in/"
STATE_FILE = "state.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def notify(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": "true"},
        timeout=20,
    )
    r.raise_for_status()


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def check(session, url):
    """Return (blocker_phrases_found, context_snippet)."""
    r = session.get(url, timeout=30)
    r.raise_for_status()
    if "product_overview" not in r.url:
        raise RuntimeError(f"redirected away from product page to {r.url}")

    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ").split())
    lower = text.lower()

    hits = [b for b in BLOCKERS if b in lower]
    snippet = ""
    if hits:
        i = lower.find(hits[0])
        snippet = text[max(0, i - 80): i + 80]
    return hits, snippet


def main():
    if "--test" in sys.argv:
        notify("✅ HMT stock bot is connected and working.")
        print("Test message sent.")
        return

    state = load_state()
    session = requests.Session()
    session.headers.update(HEADERS)

    # Visit the homepage first so we pick up any cookies the site sets.
    try:
        session.get(HOME, timeout=30)
    except requests.RequestException as e:
        print(f"Homepage warm-up failed: {e}")

    errors = 0
    for name, url in WATCHES.items():
        try:
            hits, snippet = check(session, url)
        except Exception as e:
            errors += 1
            print(f"[{name}] ERROR: {e}")
            continue

        in_stock = not hits
        if in_stock:
            print(f"[{name}] POSSIBLY IN STOCK")
        else:
            print(f"[{name}] unavailable ({', '.join(hits)}) ... {snippet!r}")

        # Alert only on the change from unavailable -> available.
        if in_stock and not state.get(name):
            notify(f"🚨 HMT {name} may be IN STOCK!\n{url}")
        state[name] = in_stock

    save_state(state)
    if errors == len(WATCHES):
        sys.exit(1)  # makes the run fail so GitHub emails you


if __name__ == "__main__":
    main()
