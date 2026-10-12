import os
import time
import json
import logging
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

logging.basicConfig(level=logging.INFO)

USER_FILE = "users.json"
STATS_FILE = "stats.json"
ACTIVE_TRADES_FILE = "active_trades.json"

def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading {filepath}: {e}")
    return default

def save_json(filepath, data):
    try:
        with open(filepath, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving {filepath}: {e}")

# ----- Health Check Server for Render & UptimeRobot -----
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Nexus 4H-1H-15M Pro Engine with Tracking & Stats is Live!")

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

def fetch_latest_crypto_news(symbol="BTC"):
    clean_sym = symbol.replace("USDT", "").replace("/USDT", "").split(" ")[0]
    if "PAXG" in clean_sym or "GOLD" in clean_sym:
        clean_sym = "BTC,SOL"
        
    url = f"https://cryptopanic.com/api/v1/posts/?auth_token=free&currencies={clean_sym}&filter=important"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict):
                results = data.get("results", [])
                if results and isinstance(results, list):
                    latest = results[0]
                    title = latest.get("title", "")
                    votes = latest.get("votes", {})
                    if not isinstance(votes, dict):
                        votes = {}
                    bullish = votes.get("positive", 0) or 0
                    bearish = votes.get("negative", 0) or 0
                    
                    sentiment = "⚪ ᲜᲔᲘᲢᲠᲐᲚᲣᲠᲘ"
                    if bullish > bearish: 
                        sentiment = "🟢 ᲑᲣᲚᲘᲨᲘ"
                    elif bearish > bullish: 
                        sentiment = "🔴 ᲑᲔᲐᲠᲘᲨᲘ"

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

# ----- ADVANCED 4H-1H-15M SMC PRO ENGINE (WITH FVG) -----
def analyze_multi_timeframe(symbol_raw="BTCUSDT", symbol_display="BTC/USDT"):
    candles_4h = fetch_binance_ohlcv(symbol=symbol_raw, interval="4h", limit=60)
    candles_1h = fetch_binance_ohlcv(symbol=symbol_raw, interval="1h", limit=60)
    candles_15m = fetch_binance_ohlcv(symbol=symbol_raw, interval="15m", limit=60)

    if not candles_4h or not candles_1h or not candles_15m:
        return None

    closes_4h = [float(c[4]) for c in candles_4h]
    highs_4h = [float(c[2]) for c in candles_4h]
    lows_4h = [float(c[3]) for c in candles_4h]
    
    ema_200_4h = sum(closes_4h[-50:]) / 50
    current_price = float(candles_15m[-1][4])

    htf_trend = "BULLISH" if current_price > ema_200_4h else "BEARISH"

    closes_1h = [float(c[4]) for c in candles_1h]

    closes_15m = [float(c[4]) for c in candles_15m]
    highs_15m = [float(c[2]) for c in candles_15m]
    lows_15m = [float(c[3]) for c in candles_15m]
    volumes_15m
