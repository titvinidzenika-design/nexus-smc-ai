import os
import time
import json
import logging
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

logging.basicConfig(level=logging.INFO)

USER_FILE = "users.json"

def load_users():
    if os.path.exists(USER_FILE):
        try:
            with open(USER_FILE, "r") as f:
                return set(json.load(f))
        except Exception as e:
            logging.error(f"Error loading users: {e}")
    return set()

def save_users(users):
    try:
        with open(USER_FILE, "w") as f:
            json.dump(list(users), f)
    except Exception as e:
        logging.error(f"Error saving users: {e}")

# ----- Health Check Server for Render & UptimeRobot -----
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Nexus Institutional SMC Engine is Live!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

    def log_message(self, format, *args):
        return

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

def keep_alive():
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "")
    while True:
        time.sleep(600)
        if render_url:
            try:
                requests.get(render_url, timeout=10)
            except Exception as e:
                logging.error(f"Keep-alive error: {e}")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

def send_telegram_message(chat_id, text):
    if not TELEGRAM_BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Error sending msg: {e}")

def fetch_latest_crypto_news():
    url = "https://cryptopanic.com/api/v1/posts/?auth_token=free&currencies=BTC&filter=important"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results:
                latest = results[0]
                title = latest.get("title", "")
                votes = latest.get("votes", {})
                bullish, bearish = votes.get("positive", 0), votes.get("negative", 0)
                
                sentiment = "⚪ ᲜᲔᲘᲢᲠᲐᲚᲣᲠᲘ"
                if bullish > bearish: sentiment = "🟢 ᲑᲣᲚᲘᲨᲘ"
                elif bearish > bullish: sentiment = "🔴 ᲑᲔᲐᲠᲘᲨᲘ"

                return f"📰 **Global News:** _{title}_\n💡 **Sentiment:** {sentiment}"
    except Exception as e:
        logging.error(f"News error: {e}")
    return "📰 **Global News:** ბაზარზე სტაბილური სიტუაციაა."

def fetch_binance_ohlcv(symbol="BTCUSDT", interval="15m", limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        res = requests.get(url, timeout=10)
        return res.json()
    except Exception as e:
        logging.error(f"Binance fetch error: {e}")
        return None

def calculate_atr(candles, period=14):
    if len(candles) < period + 1:
        return 100.0
    tr_list = []
    for i in range(1, len(candles)):
        high = float(candles[i][2])
        low = float(candles[i][3])
        prev_close = float(candles[i-1][4])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    return sum(tr_list[-period:]) / period

# ----- ADVANCED SMC INSTITUTIONAL ENGINE -----
def analyze_multi_timeframe(symbol_raw="BTCUSDT", symbol_
